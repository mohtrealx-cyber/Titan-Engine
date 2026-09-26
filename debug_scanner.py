import os
import requests
from bs4 import BeautifulSoup

SCRAPER_API_KEY = os.environ.get("SCRAPER_API_KEY")
url = "https://www.windrawwin.com/predictions/today/"

print("🔍 Starting WinDrawWin Diagnostic Scan...")
proxy_url = f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={url}&premium=true&render=true"

try:
    r = requests.get(proxy_url, timeout=60)
    print(f"📡 Status Code: {r.status_code}")
    
    soup = BeautifulSoup(r.text, 'html.parser')
    title = soup.find('title')
    print(f"🏷️ Page Title: {title.text if title else 'NO TITLE FOUND'}")
    
    text_lower = r.text.lower()
    challenge_markers = ["just a moment", "cloudflare", "turnstile", "security check", "captcha", "attention required", "cookie"]
    
    detected = [m for m in challenge_markers if m in text_lower]
    if detected:
        print(f"🛑 WARNING: ScraperAPI hit a wall. Detected keywords: {detected}")
    else:
        print("✅ No obvious CAPTCHA or Cookie walls detected.")
        
    print("\n--- FIRST 2500 CHARACTERS OF HTML RESPONSE ---")
    print(r.text[:2500])
    print("\n----------------------------------------------")
    
except Exception as e:
    print(f"❌ Error: {e}")
