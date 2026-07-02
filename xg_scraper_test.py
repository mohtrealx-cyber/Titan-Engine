# ==============================================================================
# MODULE G: LIVE UNDERSTAT xG SCRAPER (V2.1 REGEX UPGRADE)
# ==============================================================================
import re
import json
from curl_cffi import requests as tls_requests

def scrape_real_xg(team_name, understat_url):
    print(f"[*] Establishing secure connection to Understat for: {team_name}...")
    
    try:
        response = tls_requests.get(understat_url, impersonate="chrome120", timeout=15)
        
        if response.status_code != 200:
            print(f"[-] Connection rejected. Status: {response.status_code}")
            return None
            
        # V2 REGEX: More aggressive search pattern to catch the JSON no matter how Understat spaces it
        json_hunt = re.search(r"var datesData\s*=\s*JSON\.parse\(\s*['\"]([^'\"]+)['\"]\s*\)", response.text)
        
        if json_hunt:
            decoded_string = json_hunt.group(1).encode('utf-8').decode('unicode_escape')
            match_database = json.loads(decoded_string)
            
            # Isolate the most recent completed match to get their current form
            latest_match = match_database[-1]
            side_identifier = latest_match['side'] # 'h' or 'a'
            raw_xg = float(latest_match['xG'][side_identifier])
            
            print(f"[+] DATA EXTRACTED! {team_name}'s latest match xG: {raw_xg:.2f}\n")
            return raw_xg
        else:
            # The Debug Trap: If it fails, print exactly what the server returned
            print(f"[-] Regex failed to locate datesData. Cloudflare may have triggered.")
            print(f"    Page Snippet: {response.text[:250].strip()}...\n")
            
    except Exception as e:
        print(f"[-] Critical Scraping Error: {e}\n")
        
    return None

# ==============================================================================
# SIMULATION SEQUENCE
# ==============================================================================
if __name__ == "__main__":
    print("=== INITIATING PHASE 3: LIVE xG EXTRACTION ===\n")
    
    chelsea_url = "https://understat.com/team/Chelsea/2023"
    scrape_real_xg("Chelsea", chelsea_url)
    
    liverpool_url = "https://understat.com/team/Liverpool/2023"
    scrape_real_xg("Liverpool", liverpool_url)
