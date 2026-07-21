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
            print("✅ Connected to WinDrawWin!")
            return BeautifulSoup(response.text, 'html.parser')
        else:
            print(f"❌ Failed to connect. Status Code: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def extract_corner_stats(soup):
    print("🔍 Searching for corner statistics...")
    corner_data = {}
    
    try:
        # The stats are usually in a table with the class 'wt' (WinDrawWin Table)
        stats_table = soup.find('table', class_='wt')
        
        if not stats_table:
            print("❌ Could not find the main statistics table on the page.")
            return None
            
        rows = stats_table.find_all('tr')
        print(f"Found {len(rows)} rows of data. Extracting...")
        
        for row in rows:
            cols = row.find_all('td')
            # A valid stats row usually has at least 3 columns (Rank, Team, Corners)
            if len(cols) >= 3:
                # The team name is usually in the second column
                team_name = cols[1].text.strip()
                # The total average corners is usually in the last column
                avg_corners = cols[-1].text.strip()
                
                # Make sure the corners value is actually a number
                try:
                    corner_data[team_name] = float(avg_corners)
                except ValueError:
                    continue # Skip headers or rows with weird data
                    
        return corner_data
        
    except Exception as e:
        print(f"❌ Error parsing HTML: {e}")
        return None

if __name__ == "__main__":
    test_url = "https://www.windrawwin.com/statistics/corners/"
    soup = fetch_corner_data(test_url)
    
    if soup:
        stats = extract_corner_stats(soup)
        
        if stats:
            print("\n📈 TOP 10 TEAMS BY AVERAGE CORNERS PER GAME:")
            print("-" * 40)
            
            # Sort the dictionary by highest corners first
            sorted_stats = sorted(stats.items(), key=lambda item: item[1], reverse=True)
            
            for index, (team, corners) in enumerate(sorted_stats[:10]):
                print(f"{index + 1}. {team}: {corners} corners")
            
            print("-" * 40)
