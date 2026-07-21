import sys
import cloudscraper
from bs4 import BeautifulSoup

print("========================================")
print("  STARTING WINDRAWWIN SCRAPER (CLOUDSCRAPER) ")
print("========================================")

url = "https://www.windrawwin.com/predictions/today/"

try:
    print(f"Initializing cloudscraper and fetching URL: {url}")
    
    # Create a scraper instance that mimics a Windows Chrome browser
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )
    
    # Increase timeout to give Cloudflare time to process the JS challenge
    response = scraper.get(url, timeout=30)
    
    print(f"HTTP Status Code: {response.status_code}")
    print(f"Downloaded HTML Length: {len(response.text)} characters")

    # 200 means Cloudflare let us through
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "lxml")
        
        page_title = soup.title.string.strip() if soup.title else "No Title Found"
        print(f"Page Title: {page_title}")
        print("----------------------------------------")
        
        # Look for match rows on WinDrawWin
        rows = soup.find_all("tr", class_=lambda x: x and ("wttr" in x or "wtrow" in x or "wtbr" in x))
        
        if not rows:
            # Fallback check for general table rows if class names changed
            rows = soup.find_all("tr")

        print(f"Total potential match rows detected: {len(rows)}")
        
        # Print the first 3 matches as a sample to verify it worked
        print("Sample data from first 3 rows:")
        for i, row in enumerate(rows[:3]):
            # Clean string outside the f-string to prevent backslash syntax errors in Python < 3.12
            cleaned_row_text = row.text.strip().replace('\n', ' | ')[:100]
            print(f"Row {i+1}: {cleaned_row_text}...")
            
    else:
        print(f"Failed to bypass Cloudflare. Status code: {response.status_code}")

except Exception as e:
    print(f"AN ERROR OCCURRED: {e}")

print("========================================")
print("  TEST SCRIPT COMPLETED                 ")
print("========================================")
