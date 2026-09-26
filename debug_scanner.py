import os
import requests
from bs4 import BeautifulSoup
import re

SCRAPER_API_KEY = os.environ.get("SCRAPER_API_KEY")
url = "https://www.predictz.com/predictions/today/"

print("🔍 Starting PredictZ Deep-Scan X-Ray...")
proxy_url = f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={url}&premium=true&render=true&country_code=uk"

try:
    r = requests.get(proxy_url, timeout=75)
    print(f"📡 Status Code: {r.status_code}")
    
    soup = BeautifulSoup(r.text, 'html.parser')
    body = soup.find('body')
    
    if body:
        print("\n--- HUNTING FOR PREDICTZ CSS CLASSES ---")
        divs = body.find_all('div', class_=True)
        
        class_counts = {}
        for div in divs:
            for c in div.get('class', []):
                class_counts[c] = class_counts.get(c, 0) + 1
                
        # Sort and print the top 20 most used CSS classes
        sorted_classes = sorted(class_counts.items(), key=lambda x: x[1], reverse=True)
        print("Top 20 most frequent CSS classes on the page:")
        for c, count in sorted_classes[:20]:
            print(f" - {c}: {count} times")

        print("\n--- RAW HTML SNIPPET ---")
        clean_text = re.sub(r'\s+', ' ', body.get_text())
        print(clean_text[500:2000]) 
    else:
        print("❌ Could not find a <body> tag.")
        
    print("\n----------------------------------------------")
    
except Exception as e:
    print(f"❌ Error: {e}")
