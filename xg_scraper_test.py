# ==============================================================================
# MODULE G: LIVE UNDERSTAT xG SCRAPER (V6.0 CLOUD PROXY BYPASS)
# ==============================================================================
import os
import re
import json
import requests

ZENROWS_API_KEY = os.environ.get("ZENROWS_API_KEY")

def scrape_real_xg(team_name, understat_url):
    print(f"[*] Dispatching ZenRows Proxy to render JS for: {team_name}...")
    
    if not ZENROWS_API_KEY:
        print("[-] Error: ZenRows API Key missing from GitHub Secrets.")
        return None
        
    proxy_url = "https://api.zenrows.com/v1/"
    
    # We command the proxy to fully render the JavaScript before returning the HTML
    params = {
        "url": understat_url,
        "apikey": ZENROWS_API_KEY,
        "js_render": "true", 
        "premium_proxy": "true"
    }
    
    try:
        response = requests.get(proxy_url, params=params, timeout=45)
        
        if response.status_code != 200:
            print(f"[-] Proxy rejected. Status: {response.status_code}")
            return None
            
        # Now that the JS is rendered, the V5 Universal Hunter will easily find the payload
        hidden_payloads = re.findall(r"JSON\.parse\('([^']+)'\)", response.text)
        
        if not hidden_payloads:
            print("[-] Payload missing. The proxy loaded the page, but the data did not render.")
            return None
            
        for payload in hidden_payloads:
            decoded_string = payload.encode('utf-8').decode('unicode_escape')
            try:
                database = json.loads(decoded_string)
                
                if isinstance(database, list) and len(database) > 0 and 'xG' in database[0]:
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
