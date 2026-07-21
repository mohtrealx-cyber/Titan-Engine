import sys
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

print("========================================")
print("  STARTING WINDRAWWIN SCRAPER TEST     ")
print("========================================")

# WinDrawWin predictions page
url = "https://www.windrawwin.com/predictions/today/"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

try:
    print(f"Fetching URL: {url}")
    # Using curl_cffi to bypass Cloudflare protection
    response = cffi_requests.get(url, headers=headers, impersonate="chrome120", timeout=20)
    
    print(f"HTTP Status Code: {response.status_code}")
    print(f"Downloaded HTML Length: {len(response.text)} characters")

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "lxml")
        
        # Look for match rows on WinDrawWin
        # WinDrawWin typically groups games in table rows or specific containers
        rows = soup.find_all("tr", class_=lambda x: x and ("wttr" in x or "wtrow" in x or "wtbr" in x))
        
        if not rows:
            # Fallback check for general table rows if class names changed
            rows = soup.find_all("tr")

        print(f"Total potential match rows detected: {len(rows)}")
        print("----------------------------------------")
        
        # Print a small snippet of the page text to verify content
        page_title = soup.title.string.strip() if soup.title else "No Title Found"
        print(f"Page Title: {page_title}")
        
    else:
        print(f"Failed to fetch page. Status code: {response.status_code}")

except Exception as e:
    print(f"AN ERROR OCCURRED: {e}")

print("========================================")
print("  TEST SCRIPT COMPLETED                 ")
print("========================================")
