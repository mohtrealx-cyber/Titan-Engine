import os
from bs4 import BeautifulSoup
from curl_cffi import requests as tls_requests

def fetch_corner_data(url):
    print(f"Attempting to scrape: {url}")
    
    # Pulling your API key directly from your GitHub secrets just like the main engine
    SCRAPER_API_KEY = os.environ.get("SCRAPER_API_KEY")
    
    try:
        if SCRAPER_API_KEY:
            print("🛡️ Using ScraperAPI to bypass security...")
            proxy_url = f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={url}"
            response = tls_requests.get(proxy_url, timeout=60)
        else:
            print("🥸 No ScraperAPI key found, attempting Chrome browser impersonation...")
            response = tls_requests.get(url, impersonate="chrome120", timeout=20)
        
        if response.status_code == 200:
            print("✅ Successfully bypassed security and connected to WinDrawWin!")
            soup = BeautifulSoup(response.text, 'html.parser')
            return soup
        else:
            print(f"❌ Failed to connect. Status Code: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Error occurred: {e}")
        return None

if __name__ == "__main__":
    test_url = "https://www.windrawwin.com/statistics/corners/"
    soup = fetch_corner_data(test_url)
    
    if soup:
        print("Ready to start extracting data! The door is open.")
