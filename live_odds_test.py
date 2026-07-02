# ==============================================================================
# MODULE E: LIVE ODDS API INGESTION (UNIT TEST)
# ==============================================================================
import json

def fetch_live_bookmaker_odds(home_team, away_team):
    """
    Simulates bypassing the bookmaker's front-end website to query their 
    hidden backend JSON API directly for live decimal odds.
    """
    print(f"[*] Connecting to bookmaker API to scan markets for: {home_team} vs {away_team}...")
    
    # --------------------------------------------------------------------------
    # THE MOCK API RESPONSE
    # In production, this block is replaced by a tls_requests.get() call to the 
    # exact URL the bookmaker uses to populate their frontend (e.g., an Odds-API).
    # We use a mock database here to ensure the parsing logic works without 
    # triggering anti-bot security during testing.
    # --------------------------------------------------------------------------
    mock_api_database = {
        "data": [
            {
                "home_team": "Spain",
                "away_team": "Austria",
                "markets": {
                    "1X2": {"1": 1.95, "X": 3.40, "2": 3.80}
                }
            },
            {
                "home_team": "Chelsea",
                "away_team": "Arsenal",
                "markets": {
                    "1X2": {"1": 1.15, "X": 6.50, "2": 15.00}
                }
            }
        ]
    }

    # --------------------------------------------------------------------------
    # THE PARSING LOGIC (Extracting the specific decimal)
    # --------------------------------------------------------------------------
    for match in mock_api_database["data"]:
        # We check if the team names from our scraper match the bookmaker's database
        if home_team.lower() in match["home_team"].lower():
            
            # Navigate the JSON tree: Match -> Markets -> 1X2 -> Home Win ("1")
            home_win_odds = match["markets"]["1X2"]["1"]
            
            print(f"[+] MATCH FOUND! Live Odds for {home_team} to win: {home_win_odds}\n")
            return home_win_odds
            
    print(f"[-] NO MARKETS FOUND for {home_team}. Match may be unlisted or suspended.\n")
    return None

# ==============================================================================
# SIMULATION SEQUENCE
# ==============================================================================
if __name__ == "__main__":
    print("=== INITIATING ODDS INGESTION TEST ===\n")
    
    # Test 1: A match that exists in the system
    odds_1 = fetch_live_bookmaker_odds("Spain", "Austria")
    
    # Test 2: A match that exists in the system
    odds_2 = fetch_live_bookmaker_odds("Chelsea", "Arsenal")
    
    # Test 3: A match the bookmaker hasn't listed yet
    odds_3 = fetch_live_bookmaker_odds("Real Madrid", "Barcelona")
