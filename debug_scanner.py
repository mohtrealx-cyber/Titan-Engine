import os
import requests
from bs4 import BeautifulSoup
import re

SCRAPER_API_KEY = os.environ.get("SCRAPER_API_KEY")
url = "https://www.windrawwin.com/predictions/today/"

print("🔍 Starting Deep-Scan on WinDrawWin Body...")
proxy_url = f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={url}&premium=true&render=true&country_code=uk"

try:
    r = requests.get(proxy_url, timeout=75)
    print(f"📡 Status Code: {r.status_code}")
    
    soup = BeautifulSoup(r.text, 'html.parser')
    
    # Let's find any div that contains the word "Moldova" or "Slovakia" (since we know they play today)
    # Or just grab the first 10 divs inside the body that have text!
    print("\n--- EXTRACTING ACTUAL MATCH ROW CLASSES ---")
    
    # Try finding teams by looking for 'vs' or common match layouts
    body = soup.find('body')
    if body:
        # Let's just find ALL classes used on DIVs inside the main container to see what they renamed them to
        divs_with_classes = body.find_all('div', class_=True)
        
        found_classes = set()
        for div in divs_with_classes:
            classes = div.get('class', [])
            for c in classes:
                if 'row' in c.lower() or 'team' in c.lower() or 'match' in c.lower() or 'pt' in c.lower() or 'wt' in c.lower():
                    found_classes.add(c)
        
        print("CSS Classes containing row/team/wt/pt:")
        print(found_classes)
        
        print("\n--- SAMPLE TEXT FROM THE PAGE TO PROVE MATCHES LOADED ---")
        # Print a chunk of actual visible text to see if matches exist
        clean_text = re.sub(r'\s+', ' ', body.get_text())
        print(clean_text[1000:3000]) # Print text from the middle of the page
    else:
        print("❌ Could not find a <body> tag. They might be blocking the HTML completely.")

    print("\n----------------------------------------------")
    
except Exception as e:
    print(f"❌ Error: {e}")
