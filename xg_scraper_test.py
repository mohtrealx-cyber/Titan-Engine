# ==============================================================================
# MODULE G: LIVE UNDERSTAT xG SCRAPER (V3.0 BRUTE FORCE SPLIT)
# ==============================================================================
import json
from curl_cffi import requests as tls_requests

def scrape_real_xg(team_name, understat_url):
    print(f"[*] Establishing secure connection to Understat for: {team_name}...")
    
    try:
        response = tls_requests.get(understat_url, impersonate="chrome120", timeout=15)
        
        if response.status_code != 200:
            print(f"[-] Connection rejected. Status: {response.status_code}")
            return None
            
        # V3 BRUTE FORCE: Ignore Regex entirely. Just chop the string exactly where the data starts.
        start_marker = "var datesData = JSON.parse('"
        end_marker = "');"
        
        if start_marker in response.text:
            # Chop off everything before the marker, then chop off everything after the closing marker
            raw_encrypted_string = response.text.split(start_marker)[1].split(end_marker)[0]
            
            # Decode the hexadecimal escapes into standard JSON
            decoded_string = raw_encrypted_string.encode('utf-8').decode('unicode_escape')
            match_database = json.loads(decoded_string)
            
            # Isolate the most recent completed match to get their current form
            latest_match = match_database[-1]
            side_identifier = latest_match['side'] # 'h' or 'a'
            raw_xg = float(latest_match['xG'][side_identifier])
            
            print(f"[+] DATA EXTRACTED! {team_name}'s latest match xG: {raw_xg:.2f}\n")
            return raw_xg
        else:
            print(f"[-] Split failed. Could not find the start_marker in the HTML.")
            
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
