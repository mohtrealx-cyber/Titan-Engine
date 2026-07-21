import os
import sys
import requests
from bs4 import BeautifulSoup

print("========================================")
print("  STARTING LINK-BASED DIAGNOSTIC")
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
        
        # Look for the actual match links instead of table rows
        match_links = soup.find_all("a", href=lambda h: h and "/tips/" in h and "-v-" in h)
        
        print(f"Total match links detected: {len(match_links)}")
        print("\n--- EXTRACTING HTML SURROUNDING MATCH LINKS ---")
        
        # The first few are the banner. Let's check matches #10 and #50
        for idx in [10, 50]:
            if idx < len(match_links):
                print(f"\n========== STRUCTURE AROUND MATCH {idx} ==========")
                
                # Climb up two levels to grab the whole row/container
                container = match_links[idx].find_parent().find_parent()
                
                if container:
                    # Print the HTML (capped at 1500 chars to avoid massive text walls)
                    print(container.prettify()[:1500])
                else:
                    print("Could not find a parent container.")
                    
    else:
        print(f"Proxy request failed with status: {response.status_code}")

except Exception as e:
    print(f"AN ERROR OCCURRED: {e}")

print("\n========================================")
print("  DIAGNOSTIC COMPLETED")
print("========================================")
