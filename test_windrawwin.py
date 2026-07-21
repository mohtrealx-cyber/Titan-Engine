import os
import sys
import json
import requests
from bs4 import BeautifulSoup

print("========================================")
print("  STARTING RAW DATA EXTRACTION (PRE-LLM)")
print("========================================")

API_KEY = os.environ.get("SCRAPER_API_KEY")

if not API_KEY:
    print("ERROR: SCRAPER_API_KEY environment variable not found!")
    sys.exit(1)

target_url = "https://www.windrawwin.com/predictions/today/"
proxy_url = f"http://api.scraperapi.com?api_key={API_KEY}&url={target_url}&render=true"

try:
    print("Sending request via ScraperAPI proxy...")
    response = requests.get(proxy_url, timeout=60)
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "lxml")
        
        # Target the rows
        rows = soup.find_all("tr", class_=lambda x: x and ("wttr" in x or "wtrow" in x or "wtbr" in x))
        if not rows:
            rows = soup.find_all("tr")

        raw_matches = []

        for row in rows:
            cells = row.find_all('td')
            
            # Make sure the row has enough columns and contains the odds button
            if len(cells) >= 4:
                odds_btn = row.find('a', class_='btnstsm')
                
                if odds_btn:
                    # Jackpot! Pull directly from the hidden HTML attributes
                    home_team = odds_btn.get('data-home', 'Unknown')
                    away_team = odds_btn.get('data-away', 'Unknown')
                    decimal_odds = odds_btn.get('data-odds', 'N/A')
                    
                    # The messy prediction text we want to feed the LLM
                    raw_prediction = cells[2].get_text(strip=True)
                    
                    # Skip if there's no actual prediction text
                    if not raw_prediction:
                        continue

                    raw_matches.append({
                        "Home": home_team,
                        "Away": away_team,
                        "Raw_Prediction": raw_prediction,
                        "Decimal_Odds": decimal_odds
                    })

        print(f"\nSuccessfully extracted {len(raw_matches)} raw matches.")
        
        if raw_matches:
            print("\nSample of data ready for the LLM:\n")
            for i, match in enumerate(raw_matches[:5]):
                print(f"Row {i + 1}: {match}")

        # Save to JSON so the LLM script can read it
        output_filename = "windrawwin_raw_for_llm.json"
        with open(output_filename, "w") as f:
            json.dump(raw_matches, f, indent=4)
        print(f"\nRaw data successfully saved to {output_filename}")

    else:
        print(f"Proxy request failed with status: {response.status_code}")

except Exception as e:
    print(f"AN ERROR OCCURRED: {e}")
