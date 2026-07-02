# ==============================================================================
# MODULE G: LIVE UNDERSTAT xG SCRAPER
# ==============================================================================
import re
import json
from curl_cffi import requests as tls_requests

def scrape_real_xg(team_name, understat_url):
    """
    Bypasses the Understat front-end and uses Regex to extract the 
    hidden JSON database containing pure Expected Goals (xG) metrics.
    """
    print(f"[*] Establishing secure connection to Understat for: {team_name}...")
    
    try:
        # We use chrome120 impersonation to bypass bot-blockers
        response = tls_requests.get(understat_url, impersonate="chrome120", timeout=15)
        
        if response.status_code != 200:
            print(f"[-] Connection rejected. Status: {response.status_code}")
            return None
            
        # The data is hidden in a JavaScript variable.
        # We use a Regular Expression (Regex) to hunt down the exact JSON string.
        json_hunt = re.search(r"var datesData\s*=\s*JSON\.parse\('(.*?)'\);", response.text)
        
        if json_hunt:
            # Decode the encrypted string and convert it into a Python dictionary
            decoded_string = json_hunt.group(1).encode('utf-8').decode('unicode_escape')
            match_database = json.loads(decoded_string)
            
            # Isolate the most recent completed match to get their current form
            latest_match = match_database[-1]
            
            # The JSON labels the team as "h" (home) or "a" (away) for that match
            side_identifier = latest_match['side']
            raw_xg = float(latest_match['xG'][side_identifier])
            
            print(f"[+] DATA EXTRACTED! {team_name}'s latest match xG: {raw_xg:.2f}\n")
            return raw_xg
            
    except Exception as e:
        print(f"[-] Critical Scraping Error: {e}")
        
    return None

# ==============================================================================
# SIMULATION SEQUENCE
# ==============================================================================
if __name__ == "__main__":
    print("=== INITIATING PHASE 3: LIVE xG EXTRACTION ===\n")
    
    # Test 1: Chelsea's actual data page
    chelsea_url = "https://understat.com/team/Chelsea/2023"
    scrape_real_xg("Chelsea", chelsea_url)
    
    # Test 2: Liverpool's actual data page
    liverpool_url = "https://understat.com/team/Liverpool/2023"
    scrape_real_xg("Liverpool", liverpool_url)
