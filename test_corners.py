import os
from bs4 import BeautifulSoup
from curl_cffi import requests as tls_requests

def fetch_corner_data(url):
    print(f"Attempting to scrape: {url}")
    SCRAPER_API_KEY = os.environ.get("SCRAPER_API_KEY")
    
    try:
        if SCRAPER_API_KEY:
            proxy_url = f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={url}"
            response = tls_requests.get(proxy_url, timeout=60)
        else:
            response = tls_requests.get(url, impersonate="chrome120", timeout=20)
        
        if response.status_code == 200:
            print("✅ Connected!")
            return BeautifulSoup(response.text, 'html.parser')
        else:
            print(f"❌ Failed to connect. Status Code: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def extract_corner_stats(soup):
    print("🔍 Diagnosing HTML structure...")
    
    # 1. Print the title to see if we hit a CAPTCHA/Cloudflare block
    title = soup.title.text.strip() if soup.title else "No Title Found"
    print(f"📄 Page Title: {title}")
    
    # 2. Find all tables to see what classes they actually use
    tables = soup.find_all('table')
    print(f"📊 Found {len(tables)} tables on the page.")
    
    for i, table in enumerate(tables):
        classes = table.get('class', ['No Class'])
        print(f"--- Table {i+1} | Class: {classes} ---")
        
        # Print a small snippet of the table's text to see if it holds team names
        snippet = table.text.replace('\n', ' ').strip()[:150]
        print(f"Snippet: {snippet}...\n")
        
    return None

if __name__ == "__main__":
    test_url = "https://www.windrawwin.com/statistics/corners/"
    soup = fetch_corner_data(test_url)
    
    if soup:
        extract_corner_stats(soup)
