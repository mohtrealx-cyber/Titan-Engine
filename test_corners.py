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
    debug_text = "No debug data found."
    
    rows = soup.find_all('div', class_=lambda c: c and ('statln1' in c or 'statln2' in c))
    first_valid_row_found = False
    
    for i, row in enumerate(rows):
        cols = list(row.stripped_strings)
        
        # Capture the raw array of the very first valid row for Telegram
        if not first_valid_row_found and len(cols) > 3:
            debug_text = f"🛠️ <b>RAW ARRAY:</b>\n<code>{cols}</code>"
            first_valid_row_found = True
            
        team_name = None
        stats = []
        
        for col in cols:
            try:
                val = float(col)
                if team_name is not None:
                    stats.append(val)
            except ValueError:
                if len(stats) == 0 and len(col) > 2 and "Stats" not in col:
                    team_name = col
                    
        if team_name and len(stats) >= 1:
            avg_corners = stats[-1] 
            
            if avg_corners < 25.0 and team_name not in corner_data:
                corner_data[team_name] = avg_corners

    return corner_data, debug_text

def send_telegram_alert(message):
    print("📲 Attempting to send Telegram notification...")
    
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
            print("✅ Telegram message sent successfully!")
        else:
            print(f"❌ Failed to send Telegram message: {res.text}")
    except Exception as e:
        print(f"❌ Telegram Error: {e}")

if __name__ == "__main__":
    test_url = "https://www.windrawwin.com/statistics/corners/"
    soup = fetch_corner_data(test_url)
    
    if soup:
        stats, debug_text = extract_corner_stats(soup)
        
        if stats:
            sorted_stats = sorted(stats.items(), key=lambda item: item[1], reverse=True)
            
            # Attach the raw array to the top of the Telegram message
            msg = f"{debug_text}\n\n📈 <b>TOP 10 TEAMS BY AVERAGE CORNERS</b>\n\n"
            
            for index, (team, corners) in enumerate(sorted_stats[:10]):
                line = f"{index + 1}. {team}: {corners}"
                msg += f"{line}\n"
            
            send_telegram_alert(msg)
        else:
            print("⚠️ No valid corner stats could be parsed.")
