import requests
from bs4 import BeautifulSoup

def fetch_corner_data(url):
    print(f"Attempting to scrape: {url}")
    
    # We need a User-Agent so the site doesn't immediately block us as a bot
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            print("✅ Successfully connected to WinDrawWin!")
            soup = BeautifulSoup(response.text, 'html.parser')
            # Next step: We will hunt for the specific table rows here
            return soup
        else:
            print(f"❌ Failed to connect. Status Code: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Error occurred: {e}")
        return None

if __name__ == "__main__":
    # We will test with WinDrawWin's main corner statistics page
    test_url = "https://www.windrawwin.com/statistics/corners/"
    soup = fetch_corner_data(test_url)
    
    if soup:
        print("Ready to start extracting data!")
