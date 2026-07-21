import os
import sys
import requests
from bs4 import BeautifulSoup

print("========================================")
print("  STARTING WINDRAWWIN SCRAPER (SCRAPERAPI)")
print("========================================")

# Grabs SCRAPER_API_KEY (with underscore)
API_KEY = os.environ.get("SCRAPER_API_KEY")

if not API_KEY:
    print("ERROR: SCRAPER_API_KEY environment variable not found!")
    sys.exit(1)

target_url = "https://www.windrawwin.com/predictions/today/"
proxy_url = f"http://api.scraperapi.com?api_key={API_KEY}&url={target_url}&render=true"

try:
    print("Sending request via ScraperAPI proxy...")
    # ScraperAPI can take up to 60 seconds to rotate proxies and render JS
    response = requests.get(proxy_url, timeout=60)
    
    print(f"HTTP Status Code: {response.status_code}")
    print(f"Downloaded HTML Length: {len(response.text)} characters")

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "lxml")
        
        page_title = soup.title.string.strip() if soup.title else "No Title Found"
        print(f"Page Title: {page_title}")
        print("----------------------------------------")
        
        # Look for WinDrawWin's specific row classes, fallback to all table rows
        rows = soup.find_all("tr", class_=lambda x: x and ("wttr" in x or "wtrow" in x or "wtbr" in x))
        if not rows:
            rows = soup.find_all("tr")

        print(f"Total potential match rows detected: {len(rows)}")
        
        if rows:
            print("Sample data from first 10 rows:")
            for i, row in enumerate(rows[:10]):
                # Extract text from each individual cell (<td> or <th>) and ignore empty ones
                columns = [td.get_text(separator=" ", strip=True) for td in row.find_all(['td', 'th'])]
                
                # Join the columns with a pipe symbol for clean readability
                if columns:
                    cleaned_row = " | ".join(filter(None, columns))
                    print(f"Row {i + 1}: {cleaned_row}")
    else:
        print(f"Proxy request failed with status: {response.status_code}")

except Exception as e:
    print(f"AN ERROR OCCURRED: {e}")

print("========================================")
print("  TEST SCRIPT COMPLETED                 ")
print("========================================")
