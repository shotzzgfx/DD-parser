from curl_cffi import requests

url = "https://www.doordash.com/store/the-heights-deli-&-bottle-shop-los-angeles-2501711/2506402/"

headers = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "accept-language": "en-GB,en;q=0.5",
    "priority": "u=0, i",
    "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Brave";v="146"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "sec-gpc": "1",
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
}

response = requests.get(
    url,
    headers=headers,
    ja3="771,4865-4866-4867-49195-49199-49196-49200-52393-52392-49171-49172-156-157-47-53,10-5-18-43-16-51-0-65037-23-35-65281-27-11-17613-13-45,4588-29-23-24,0"
)

open('resp.txt', 'w').write(response.text)