import re
import json
from html import unescape
from typing import Any, Optional
from bs4 import BeautifulSoup, Tag


def decode_html(text: str) -> str:
    if text is None:
        return None
    return unescape(str(text))


class DoorDashHTMLParser:
    def __init__(self, html_content: str):
        self.html = html_content
        self.soup = BeautifulSoup(html_content, 'html.parser')
        self.data = {
            "meta": {},
            "restaurant": {},
            "menu": {"categories": []},
            "links": [],
            "scripts": [],
            "raw_text_sections": []
        }
    
    def parse_all(self) -> dict:
        self.parse_meta_tags()
        self.parse_open_graph()
        self.parse_json_ld()
        self.parse_store_info()
        self.parse_navigation()
        self.parse_footer_links()
        self.extract_all_text()
        self.parse_data_attributes()
        return self.data
    
    def parse_meta_tags(self) -> None:
        meta_data = {}
        for meta in self.soup.find_all('meta'):
            name = meta.get('name') or meta.get('property') or meta.get('charset')
            content = meta.get('content')
            if name:
                meta_data[name] = content
            if meta.get('charset'):
                meta_data['charset'] = meta.get('charset')
        viewport = self.soup.find('meta', {'name': 'viewport'})
        if viewport:
            meta_data['viewport'] = viewport.get('content')
        self.data['meta'] = meta_data
    
    def parse_open_graph(self) -> None:
        og_data = {}
        for meta in self.soup.find_all('meta'):
            prop = meta.get('property', '')
            if prop.startswith('og:'):
                og_data[prop[3:]] = meta.get('content')
            elif meta.get('name', '').startswith('twitter:'):
                og_data[f"twitter_{meta.get('name')[8:]}"] = meta.get('content')
        if og_data:
            self.data['meta']['open_graph'] = og_data
    
    def parse_json_ld(self) -> None:
        json_objects = []
        for script in self.soup.find_all('script', {'type': 'application/ld+json'}):
            try:
                if script.string:
                    json_obj = json.loads(script.string)
                    json_objects.append(json_obj)
            except (json.JSONDecodeError, TypeError):
                continue
        for obj in json_objects:
            obj_type = obj.get('@type')
            if obj_type == 'Restaurant':
                self.data['restaurant'] = {
                    'name': decode_html(obj.get('name')),
                    'address': decode_html(obj.get('address', {}).get('streetAddress')),
                    'address_locality': decode_html(obj.get('address', {}).get('addressLocality')),
                    'address_region': decode_html(obj.get('address', {}).get('addressRegion')),
                    'address_country': decode_html(obj.get('address', {}).get('addressCountry')),
                    'latitude': obj.get('geo', {}).get('latitude'),
                    'longitude': obj.get('geo', {}).get('longitude'),
                    'price_range': obj.get('priceRange'),
                    'cuisine_types': [decode_html(c) for c in obj.get('servesCuisine', [])],
                    'images': obj.get('image', []),
                    'from_json_ld': True
                }
                if 'aggregateRating' in obj:
                    self.data['restaurant']['aggregate_rating'] = obj['aggregateRating']
                if 'review' in obj:
                    self.data['restaurant']['reviews'] = obj['review']
                if 'hasMenu' in obj:
                    self._parse_menu_from_json_ld(obj['hasMenu'])
            elif obj_type == 'Organization':
                self.data['organization'] = obj
    
    def _parse_menu_from_json_ld(self, menu_obj: dict) -> None:
        categories = []
        has_menu_section = menu_obj.get('hasMenuSection', [])
        if has_menu_section and isinstance(has_menu_section, list):
            if len(has_menu_section) > 0 and isinstance(has_menu_section[0], list):
                has_menu_section = has_menu_section[0]
        for section in has_menu_section:
            if not isinstance(section, dict):
                continue
            category = {
                'name': decode_html(section.get('name')),
                'items': [],
                'from_json_ld': True
            }
            for item in section.get('hasMenuItem', []):
                offers = item.get('offers', {})
                price_raw = offers.get('price', '')
                price_value = None
                if price_raw:
                    price_str = str(price_raw).replace('$', '').strip()
                    if price_str:
                        try:
                            price_value = float(price_str)
                        except ValueError:
                            pass
                category['items'].append({
                    'name': decode_html(item.get('name')),
                    'description': decode_html(item.get('description')),
                    'price_raw': decode_html(price_raw) if price_raw else None,
                    'price_value': price_value,
                    'currency': 'USD'
                })
            categories.append(category)
        self.data['menu']['categories'] = categories
    
    def parse_store_info(self) -> None:
        store_info = {}
        store_sections = self.soup.find_all('div', {'data-testid': 'storeInfo'})
        for section in store_sections:
            text = section.get_text(strip=True, separator=' ')
            if text:
                store_info['text_content'] = text
            title = section.find(['h1', 'h2', 'h3'])
            if title:
                store_info['title'] = title.get_text(strip=True)
        main = self.soup.find('main')
        if main:
            h1 = main.find('h1')
            if h1:
                store_info['h1_name'] = h1.get_text(strip=True)
        if store_info:
            self.data['restaurant']['html_extracted'] = store_info
    
    def parse_navigation(self) -> None:
        nav_data = {
            'side_nav': [],
            'header': {},
            'breadcrumbs': []
        }
        side_nav = self.soup.find('nav', {'data-testid': 'side-nav'})
        if side_nav:
            for item in side_nav.find_all(['a', 'button'], class_=lambda x: x and 'FrameElement' in str(x)):
                text = item.get_text(strip=True)
                href = item.get('href')
                if text:
                    nav_data['side_nav'].append({
                        'text': text,
                        'href': href
                    })
        header = self.soup.find('header', {'data-testid': 'Header'})
        if header:
            addr_btn = header.find('button', {'data-testid': 'addressTextButton'})
            if addr_btn:
                nav_data['header']['address_text'] = addr_btn.get_text(strip=True)
            cart_btn = header.find('button', {'data-testid': 'OrderCartIconButton'})
            if cart_btn:
                nav_data['header']['cart_count'] = cart_btn.get_text(strip=True)
        self.data['navigation'] = nav_data
    
    def parse_footer_links(self) -> None:
        footer = self.soup.find('footer', {'data-testid': 'Footer'})
        if not footer:
            return
        footer_data = {
            'trending_restaurants': [],
            'top_dishes': [],
            'trending_categories': [],
            'nearby_cities': []
        }
        sections = footer.find_all('div', class_=lambda x: x and 'euoYHq' in str(x))
        for section in sections:
            h2 = section.find('h2')
            if not h2:
                continue
            section_title = h2.get_text(strip=True)
            links = []
            for link in section.find_all('a', href=True):
                text = link.get_text(strip=True)
                href = link.get('href')
                if text and href:
                    links.append({'text': text, 'href': href})
            if 'Trending Restaurants' in section_title:
                footer_data['trending_restaurants'] = links
            elif 'Top Dishes' in section_title:
                footer_data['top_dishes'] = links
            elif 'Trending Categories' in section_title or 'Top Dishes Near Me' in section_title:
                footer_data['trending_categories'] = links
            elif 'Cities' in section_title or 'nearby' in section_title.lower():
                footer_data['nearby_cities'] = links
        self.data['footer'] = footer_data
    
    def extract_all_text(self) -> None:
        main = self.soup.find('main')
        if main:
            text = main.get_text(separator='\n', strip=True)
            text = re.sub(r'\n\s*\n', '\n\n', text)
            self.data['raw_text_sections'].append({
                'source': 'main_content',
                'text': text[:50000]
            })
        headings = []
        for i in range(1, 7):
            for h in self.soup.find_all(f'h{i}'):
                text = h.get_text(strip=True)
                if text:
                    headings.append({
                        'level': i,
                        'text': text
                    })
        self.data['headings'] = headings
    
    def parse_data_attributes(self) -> None:
        data_attrs = {}
        for elem in self.soup.find_all(attrs={'data-testid': True}):
            testid = elem.get('data-testid')
            if testid and testid not in data_attrs:
                data_attrs[testid] = {
                    'text': elem.get_text(strip=True)[:200],
                    'attributes': {}
                }
                for attr, value in elem.attrs.items():
                    if attr.startswith('data-'):
                        data_attrs[testid]['attributes'][attr] = value
        self.data['data_attributes'] = data_attrs
    
    def parse_links(self) -> None:
        links = []
        for a in self.soup.find_all('a', href=True):
            links.append({
                'text': a.get_text(strip=True),
                'href': a.get('href'),
                'target': a.get('target'),
                'rel': a.get('rel')
            })
        self.data['links'] = links
    
    def parse_scripts(self) -> None:
        scripts = []
        for script in self.soup.find_all('script'):
            src = script.get('src')
            script_type = script.get('type')
            script_info = {
                'src': src,
                'type': script_type,
                'id': script.get('id')
            }
            if not src and script.string:
                content = script.string.strip()
                script_info['inline_length'] = len(content)
                if script_type == 'application/ld+json':
                    script_info['is_json_ld'] = True
            scripts.append(script_info)
        self.data['scripts'] = scripts
    
    def get_summary(self) -> str:
        lines = []
        lines.append("[!] DOORDASH HTML PARSER SUMMARY")
        if 'meta' in self.data:
            meta = self.data['meta']
            lines.append(f"\n[!] Title: {meta.get('title', 'N/A')}")
            lines.append(f"    Description: {meta.get('description', 'N/A')[:100]}...")
        if 'restaurant' in self.data and self.data['restaurant']:
            r = self.data['restaurant']
            lines.append(f"\n[+] Restaurant: {r.get('name', 'Unknown')}")
            if r.get('from_json_ld'):
                lines.append("    (from JSON-LD)")
            if r.get('html_extracted'):
                lines.append("    (additional HTML data extracted)")
        if 'menu' in self.data and self.data['menu'].get('categories'):
            menu = self.data['menu']
            total_items = sum(len(cat.get('items', [])) for cat in menu['categories'])
            lines.append(f"\n[+] Menu: {len(menu['categories'])} categories, {total_items} items")
        if 'navigation' in self.data:
            nav = self.data['navigation']
            if nav.get('side_nav'):
                lines.append(f"\n[+] Side Nav: {len(nav['side_nav'])} items")
        if 'footer' in self.data:
            footer = self.data['footer']
            lines.append(f"\n[+] Footer Links:")
            for key, items in footer.items():
                if items:
                    lines.append(f"    - {key}: {len(items)} links")
        if 'data_attributes' in self.data:
            lines.append(f"\n[+] Data Attributes: {len(self.data['data_attributes'])} elements with data-testid")
        if 'headings' in self.data:
            lines.append(f"\n[+] Headings: {len(self.data['headings'])} total")
        return "\n".join(lines)


def main():
    import sys
    html_file = "resp.txt"
    if len(sys.argv) > 1:
        html_file = sys.argv[1]
    print(f"[*] Reading {html_file}...")
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    print("[*] Parsing HTML structure...")
    parser = DoorDashHTMLParser(html_content)
    data = parser.parse_all()
    parser.parse_links()
    parser.parse_scripts()
    output_file = "parsed_html_data.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json_data = data.copy()
        if 'raw_text_sections' in json_data:
            for section in json_data['raw_text_sections']:
                if len(section.get('text', '')) > 1000:
                    section['text'] = section['text'][:1000] + "... [truncated]"
        json.dump(json_data, f, indent=2, ensure_ascii=False, default=str)
    print(f"[+] Full data saved to {output_file}")
    print("\n" + parser.get_summary())
    return data


if __name__ == "__main__":
    main()
