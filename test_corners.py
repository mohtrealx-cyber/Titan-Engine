import os
from collections import Counter
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

def analyze_html_structure(soup):
    print("🔍 Running structural analysis on HTML...\n")
    
    # 1. Quality Assurance check: is the data actually in the static HTML?
    page_text = soup.get_text(separator=' ', strip=True)
    print(f"Total visible text length: {len(page_text)} characters.")
    print(f"Data present test ('Average'): {'Average' in page_text}")
    print(f"Data present test ('Chelsea'): {'Chelsea' in page_text}\n")
    
    # 2. Find the most common recurring <div> classes (our potential dataset rows)
    print("📊 Top 5 most common <div> structures on the page:")
    div_classes = []
    for div in soup.find_all('div'):
        cls = div.get('class')
        if cls:
            div_classes.append(" ".join(cls))
            
    top_classes = Counter(div_classes).most_common(5)
    
    for cls_name, count in top_classes:
        print(f"\n--- Class: '{cls_name}' (Appears {count} times) ---")
        
        # Grab the first instance of this exact class combination
        for div in soup.find_all('div'):
            if " ".join(div.get('class', [])) == cls_name:
                snippet = div.text.replace('\n', ' ').strip()
                print(f"Snippet: {snippet[:150]}...")
                break

if __name__ == "__main__":
    test_url = "https://www.windrawwin.com/statistics/corners/"
    soup = fetch_corner_data(test_url)
    
    if soup:
        analyze_html_structure(soup)
