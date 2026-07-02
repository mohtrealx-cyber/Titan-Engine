# ==============================================================================
# MODULE G: LIVE UNDERSTAT xG SCRAPER (V5.0 UNIVERSAL PAYLOAD HUNTER)
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
            
        # V5 UNIVERSAL HUNTER: Extract EVERY piece of encrypted JSON hidden on the page.
        hidden_payloads = re.findall(r"JSON\.parse\('([^']+)'\)", response.text)
        
        if not hidden_payloads:
            print("[-] Security block. Cloudflare completely stripped the payloads.")
            return None
            
        for payload in hidden_payloads:
            decoded_string = payload.encode('utf-8').decode('unicode_escape')
            try:
                database = json.loads(decoded_string)
                
                # Identify the correct database: A list of matches containing 'xG'
                if isinstance(database, list) and len(database) > 0 and 'xG' in database[0]:
                    
                    # Filter out future matches that haven't been played yet
                    completed_matches = [m for m in database if m.get('isResult') == True]
                    
                    if completed_matches:
                        latest_match = completed_matches[-1]
                        side_identifier = latest_match['side'] # 'h' or 'a'
                        raw_xg = float(latest_match['xG'][side_identifier])
                        
                        print(f"[+] DATA EXTRACTED! {team_name}'s latest match xG: {raw_xg:.2f}\n")
                        return raw_xg
            except:
                continue
                
        print("[-] Payloads found, but none contained the match history database.")
                
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
