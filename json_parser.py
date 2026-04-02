import json
import re
from html import unescape
from typing import Any


def decode_html(text: str) -> str:
    if text is None:
        return None
    return unescape(str(text))


def extract_json_from_html(html_content: str) -> list[dict]:
    json_objects = []
    pattern = r'<script type="application/ld\+json">(\{.*?\})</script>'
    matches = re.findall(pattern, html_content, re.DOTALL)
    for match in matches:
        try:
            json_obj = json.loads(match)
            json_objects.append(json_obj)
        except json.JSONDecodeError as e:
            print(f"[-] Failed to parse JSON object: {e}")
            continue
    return json_objects


def parse_restaurant_data(json_objects: list[dict]) -> dict:
    result = {
        "restaurant": None,
        "menu": None,
        "reviews": [],
        "aggregate_rating": None,
        "organization": None
    }
    for obj in json_objects:
        obj_type = obj.get("@type")
        if obj_type == "Restaurant":
            result["restaurant"] = parse_restaurant_info(obj)
            if "hasMenu" in obj:
                result["menu"] = parse_menu(obj["hasMenu"])
            if "review" in obj:
                result["reviews"] = parse_reviews(obj["review"])
            if "aggregateRating" in obj:
                result["aggregate_rating"] = obj["aggregateRating"]
        elif obj_type == "Menu":
            if result["menu"] is None:
                result["menu"] = parse_menu(obj)
        elif obj_type == "Organization":
            result["organization"] = obj
    return result


def parse_restaurant_info(obj: dict) -> dict:
    return {
        "name": decode_html(obj.get("name")),
        "address": decode_html(obj.get("address", {}).get("streetAddress")),
        "address_locality": decode_html(obj.get("address", {}).get("addressLocality")),
        "address_region": decode_html(obj.get("address", {}).get("addressRegion")),
        "address_country": decode_html(obj.get("address", {}).get("addressCountry")),
        "latitude": obj.get("geo", {}).get("latitude"),
        "longitude": obj.get("geo", {}).get("longitude"),
        "price_range": obj.get("priceRange"),
        "cuisine_types": [decode_html(c) for c in obj.get("servesCuisine", [])],
        "images": obj.get("image", [])
    }


def parse_menu(menu_obj: dict) -> dict:
    menu = {
        "categories": []
    }
    has_menu_section = menu_obj.get("hasMenuSection", [])
    if has_menu_section and isinstance(has_menu_section, list):
        if len(has_menu_section) > 0 and isinstance(has_menu_section[0], list):
            has_menu_section = has_menu_section[0]
    for section in has_menu_section:
        if not isinstance(section, dict):
            continue
        category = {
            "name": section.get("name"),
            "items": []
        }
        menu_items = section.get("hasMenuItem", [])
        for item in menu_items:
            menu_item = parse_menu_item(item)
            category["items"].append(menu_item)
        menu["categories"].append(category)
    return menu


def parse_menu_item(item: dict) -> dict:
    offers = item.get("offers", {})
    price_raw = offers.get("price", "")
    price_value = None
    currency = "USD"
    if price_raw:
        price_str = str(price_raw).replace("$", "").strip()
        if price_str:
            try:
                price_value = float(price_str)
            except ValueError:
                price_value = None
    return {
        "name": decode_html(item.get("name")),
        "description": decode_html(item.get("description")),
        "price_raw": decode_html(price_raw) if price_raw else None,
        "price_value": price_value,
        "currency": currency,
        "type": item.get("@type")
    }


def parse_reviews(reviews: list) -> list[dict]:
    parsed_reviews = []
    for review in reviews:
        rating = review.get("reviewRating", {})
        author = review.get("author", {})
        parsed_reviews.append({
            "author": author.get("name"),
            "rating": rating.get("ratingValue"),
            "best_rating": rating.get("bestRating"),
            "worst_rating": rating.get("worstRating"),
            "review_body": review.get("reviewBody"),
            "publisher": review.get("publisher")
        })
    return parsed_reviews


def generate_summary(data: dict) -> str:
    lines = []
    lines.append("[!] DOORDASH RESTAURANT DATA SUMMARY")
    if data.get("restaurant"):
        r = data["restaurant"]
        lines.append(f"\n[+] Restaurant: {r.get('name', 'Unknown')}")
        lines.append(f"    Address: {r.get('address', '')}, {r.get('address_locality', '')}, {r.get('address_region', '')}")
        lines.append(f"    Coordinates: {r.get('latitude', '')}, {r.get('longitude', '')}")
        lines.append(f"    Price Range: {r.get('price_range', '')}")
        lines.append(f"    Cuisine: {', '.join(r.get('cuisine_types', []))}")
    if data.get("aggregate_rating"):
        rating = data["aggregate_rating"]
        lines.append(f"\n[+] Rating: {rating.get('ratingValue', 'N/A')}/5 ({rating.get('reviewCount', 0)} reviews)")
    if data.get("menu"):
        menu = data["menu"]
        lines.append(f"\n[+] MENU ({len(menu['categories'])} categories)")
        total_items = 0
        for category in menu["categories"]:
            lines.append(f"\n    [*] {category['name']} ({len(category['items'])} items)")
            total_items += len(category['items'])
            for item in category['items'][:3]:
                price = item.get('price_raw', 'N/A')
                lines.append(f"        - {item['name']}: {price}")
            if len(category['items']) > 3:
                lines.append(f"        ... and {len(category['items']) - 3} more items")
        lines.append(f"\n    [+] Total Menu Items: {total_items}")
    if data.get("reviews"):
        lines.append(f"\n[!] REVIEWS ({len(data['reviews'])} total)")
        for review in data["reviews"][:2]:
            lines.append(f"    [+] {review['rating']}/5 - {review['author']}")
            body = review.get('review_body', '')
            if body:
                preview = body[:100] + "..." if len(body) > 100 else body
                lines.append(f"        \"{preview}\"")
    return "\n".join(lines)


def main():
    import sys
    html_file = "resp.txt"
    if len(sys.argv) > 1:
        html_file = sys.argv[1]
    print(f"[*] Reading {html_file}...")
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    print("[*] Extracting JSON-LD data...")
    json_objects = extract_json_from_html(html_content)
    print(f"[+] Found {len(json_objects)} JSON-LD objects")
    print("[*] Parsing restaurant data...")
    data = parse_restaurant_data(json_objects)
    output_file = "parsed_data.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[+] Full data saved to {output_file}")
    print("\n" + generate_summary(data))
    return data


if __name__ == "__main__":
    main()
