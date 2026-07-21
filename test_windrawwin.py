import os
import sys
import requests
from bs4 import BeautifulSoup

print("========================================")
print("  STARTING WINDRAWWIN MAIN TABLE DIAGNOSTIC")
print("========================================")

API_KEY = os.environ.get("SCRAPER_API_KEY")

if not API_KEY:
    print("ERROR: SCRAPER_API_KEY environment variable not found!")
    sys.exit(1)

target_url = "https://www.windrawwin.com/predictions/today/"
proxy_url = f"http://api.scraperapi.com?api_key={API_KEY}&url={target_url}&render=true"

try:
    print("Sending request via ScraperAPI proxy...")
    response = requests.get(proxy_url, timeout=60)
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "lxml")
        
        # Target the rows
        rows = soup.find_all("tr", class_=lambda x: x and ("wttr" in x or "wtrow" in x or "wtbr" in x))
        if not rows:
            rows = soup.find_all("tr")

        print(f"Total potential match rows detected: {len(rows)}")
        print("\n--- EXTRACTING RAW HTML FROM MAIN TABLE ---")
        
        main_table_count = 0
        for i, row in enumerate(rows):
            cells = row.find_all('td')
            
            # Skip the promoted rows that have the 'btnstsm' class
            if not row.find('a', class_='btnstsm') and len(cells) >= 3:
                print(f"\n========== MAIN TABLE ROW HTML ==========")
                print(row.prettify())
                main_table_count += 1
                
                # We just need 3 examples to see the pattern
                if main_table_count >= 3:
                    break
                    
    else:
        print(f"Proxy request failed with status: {response.status_code}")

except Exception as e:
    print(f"AN ERROR OCCURRED: {e}")

print("\n========================================")
print("  DIAGNOSTIC COMPLETED")
print("========================================")
