# ==============================================================================
# MODULE G: LIVE UNDERSTAT xG SCRAPER (V4.0 SMART EXTRACTION)
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
            
        # V4 SMART EXTRACTION: Ignores spacing/tabs and targets the single-quote wrapper
        match = re.search(r"var\s+datesData.*?JSON\.parse\('([^']+)'\)", response.text, re.DOTALL)
        
        if match:
            # Capture the raw string and decode it into JSON
            raw_encrypted_string = match.group(1)
            decoded_string = raw_encrypted_string.encode('utf-8').decode('unicode_escape')
            match_database = json.loads(decoded_string)
            
            # Isolate the most recent completed match
            latest_match = match_database[-1]
            side_identifier = latest_match['side'] # 'h' or 'a'
            raw_xg = float(latest_match['xG'][side_identifier])
            
            print(f"[+] DATA EXTRACTED! {team_name}'s latest match xG: {raw_xg:.2f}\n")
            return raw_xg
            
        else:
            print(f"[-] Extraction failed. Running diagnostic scanner...")
            # If the regex misses, print exactly what the code looks like around the target variable
            if "datesData" in response.text:
                debug_chunk = response.text.split("datesData")[1][:100]
                print(f"    [Diagnostic] Found the variable, but the structure is:")
                print(f"    datesData{debug_chunk}\n")
            else:
                print(f"    [Diagnostic] The 'datesData' variable is completely missing from the HTML.\n")
                
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
