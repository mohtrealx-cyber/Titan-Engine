import os
import requests
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
    print("🔍 Extracting data from responsive divs...")
    corner_data = {}
    
    # WinDrawWin uses 'statln1' and 'statln2' for alternating rows instead of <tr>
    rows = soup.find_all('div', class_=lambda c: c and ('statln1' in c or 'statln2' in c))
    print(f"Found {len(rows)} potential data rows.")
    
    for i, row in enumerate(rows):
        cols = list(row.stripped_strings)
        
        team_name = None
        stats = []
        
        for col in cols:
            try:
                val = float(col)
                if team_name is not None:
                    stats.append(val)
            except ValueError:
                # The last string before the numbers start is typically the team name
                if len(stats) == 0 and len(col) > 2 and "Stats" not in col:
                    team_name = col
                    
        # If we successfully parsed at least 1 number
        if team_name and len(stats) >= 1:
            # Print the raw array of the first row just to verify our targeting
            if i == 0:
                print(f"🛠️ Debug - First Row Raw Stats Array: {stats}")
                
            # The final number in the sequence is the actual Average Corners per Game
            avg_corners = stats[-1] 
            corner_data[team_name] = avg_corners

    return corner_data

def send_telegram_alert(message):
    print("📲 Attempting to send Telegram notification...")
    
    # Fallback to QUANT_ tokens if TELEGRAM_ tokens aren't explicitly passed
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("QUANT_TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID") or os.environ.get("QUANT_TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        print("⚠️ Telegram credentials not found in secrets. Skipping message.")
        return
        
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
        res = requests.post(url, json=payload)
        
        if res.status_code == 200:
            print("✅ Telegram message sent successfully to your DM!")
        else:
            print(f"❌ Failed to send Telegram message: {res.text}")
    except Exception as e:
        print(f"❌ Telegram Error: {e}")

if __name__ == "__main__":
    test_url = "https://www.windrawwin.com/statistics/corners/"
    soup = fetch_corner_data(test_url)
    
    if soup:
        stats = extract_corner_stats(soup)
        
        if stats:
            # Sort the dictionary by highest corners first
            sorted_stats = sorted(stats.items(), key=lambda item: item[1], reverse=True)
            
            msg = "📈 <b>TOP 10 TEAMS BY AVERAGE CORNERS</b>\n\n"
            print("\n📈 TOP 10 TEAMS BY AVERAGE CORNERS:")
            print("-" * 40)
            
            for index, (team, corners) in enumerate(sorted_stats[:10]):
                line = f"{index + 1}. {team}: {corners}"
                print(line)
                msg += f"{line}\n"
            
            print("-" * 40)
            
            # Send the scraped data directly to Telegram
            send_telegram_alert(msg)
        else:
            print("⚠️ No valid corner stats could be parsed.")
