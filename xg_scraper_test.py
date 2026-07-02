# ==============================================================================
# MODULE G: LIVE UNDERSTAT xG SCRAPER (V7.0 NATIVE AJAX API)
# ==============================================================================
from understatapi import UnderstatClient

def scrape_real_xg(team_name, season="2023"):
    print(f"[*] Accessing hidden AJAX endpoints for: {team_name}...")
    
    # Format the team name for the API (e.g., "Manchester United" -> "Manchester_United")
    formatted_name = team_name.replace(" ", "_")
    
    try:
        with UnderstatClient() as understat:
            # Query their database directly, completely bypassing the HTML frontend
            match_data = understat.team(team=formatted_name).get_match_data(season=season)
            
            # Filter for matches that have actually been played
            completed_matches = [m for m in match_data if m.get('isResult') == True]
            
            if completed_matches:
                latest_match = completed_matches[-1]
                
                # Determine if our target team played Home ('h') or Away ('a')
                if latest_match['h']['title'].lower() == team_name.lower():
                    raw_xg = float(latest_match['xG']['h'])
                else:
                    raw_xg = float(latest_match['xG']['a'])
                
                print(f"[+] DATA EXTRACTED! {team_name}'s latest match xG: {raw_xg:.2f}\n")
                return raw_xg
            else:
                print("[-] No completed matches found for this season.")
                
    except Exception as e:
        print(f"[-] Critical API Error: {e}\n")
        
    return None

# ==============================================================================
# SIMULATION SEQUENCE
# ==============================================================================
if __name__ == "__main__":
    print("=== INITIATING PHASE 3: LIVE xG EXTRACTION ===\n")
    
    scrape_real_xg("Chelsea", "2023")
    scrape_real_xg("Liverpool", "2023")
