import os
import sys
import json
import requests
from bs4 import BeautifulSoup

print("========================================")
print("  STARTING WINDRAWWIN SCRAPER (SCRAPERAPI)")
print("========================================")

# Helper function to convert fractional odds to decimal, handling "Evs"
def fraction_to_decimal(fraction_str):
    try:
        val = fraction_str.strip().lower()
        if val == "evs":
            return 2.00
        if '/' in val:
            num, den = val.split('/')
            return round((float(num) / float(den)) + 1.0, 2)
        return float(val)
    except Exception:
        return fraction_str

# Grabs SCRAPER_API_KEY (with underscore)
API_KEY = os.environ.get("SCRAPER_API_KEY")

if not API_KEY:
    print("ERROR: SCRAPER_API_KEY environment variable not found!")
    sys.exit(1)

target_url = "https://www.windrawwin.com/predictions/today/"
proxy_url = f"http://api.scraperapi.com?api_key={API_KEY}&url={target_url}&render=true"

try:
    print("Sending request via ScraperAPI proxy...")
    response = requests.get(proxy_url, timeout=60)
    
    print(f"HTTP Status Code: {response.status_code}")
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "lxml")
        
        page_title = soup.title.string.strip() if soup.title else "No Title Found"
        print(f"Page Title: {page_title}")
        print("----------------------------------------")
        
        # Look for WinDrawWin's specific row classes, fallback to all table rows
        rows = soup.find_all("tr", class_=lambda x: x and ("wttr" in x or "wtrow" in x or "wtbr" in x))
        if not rows:
            rows = soup.find_all("tr")

        print(f"Total potential match rows detected: {len(rows)}")
        
        parsed_matches = []

        if rows:
            for row in rows:
                columns = [td.get_text(separator=" ", strip=True) for td in row.find_all(['td', 'th'])]
                columns = [col for col in columns if col] # Filter empty cells
                
                if not columns:
                    continue

                is_single_col_match = False
                is_multi_col_match = False
                v_index = None

                # 1. Structure Check: Acca Banners vs Main Tables
                match_col = next((col for col in columns if " v " in col), None)
                
                if match_col:
                    is_single_col_match = True
                else:
                    # Look for standalone "v" or "-" which separates teams in the main tables
                    for i, col in enumerate(columns):
                        if col.strip().lower() == "v" or col.strip() == "-":
                            v_index = i
                            is_multi_col_match = True
                            break

                if not is_single_col_match and not is_multi_col_match:
                    continue # Skip irrelevant rows (headers, ads, handicap sub-markets)

                # 2. Extract Data Based on Structure
                if is_single_col_match:
                    home_team, away_team = match_col.split(" v ", 1)
                    match_idx = columns.index(match_col)
                    prediction = columns[match_idx + 1] if len(columns) > match_idx + 1 else "Unknown"
                    odds = columns[match_idx + 2] if len(columns) > match_idx + 2 else "N/A"
                    
                elif is_multi_col_match:
                    # Ensure indices won't throw out of bounds errors
                    if v_index >= 1 and v_index + 1 < len(columns):
                        home_team = columns[v_index - 1]
                        away_team = columns[v_index + 1]
                        prediction = columns[v_index + 2] if len(columns) > v_index + 2 else "Unknown"
                        
                        # The odds column floats depending on if a "Stake" column exists. 
                        # Searching backwards to find the first valid odds format.
                        odds = "N/A"
                        for col in reversed(columns[v_index+2:]):
                            if "/" in col or col.lower() == "evs" or (col.replace('.', '', 1).isdigit() and len(col) < 6):
                                odds = col
                                break
                    else:
                        continue

                # 3. Classify the Market Type
                pred_upper = prediction.upper()
                market = "1X2 (Match Winner)" # Default fallback
                
                if "BTTS" in pred_upper or "BOTH TEAMS TO SCORE" in pred_upper:
                    if "WIN" in pred_upper or "DRAW" in pred_upper:
                        market = "Result & BTTS"
                    else:
                        market = "BTTS"
                elif "OVER" in pred_upper or "UNDER" in pred_upper:
                    market = "Over/Under Goals"
                elif "-" in prediction and prediction.replace("-", "").isdigit():
                    market = "Correct Score"
                
                # 4. Structure the output
                match_data = {
                    "Home": home_team.strip(),
                    "Away": away_team.strip(),
                    "Market": market,
                    "Prediction": prediction.strip(),
                    "Odds_Fractional": odds.strip(),
                    "Odds_Decimal": fraction_to_decimal(odds.strip())
                }
                
                parsed_matches.append(match_data)
                
            print(f"\nSuccessfully extracted and categorized {len(parsed_matches)} matches.")
            if parsed_matches:
                print("Sample data from first 10 rows:\n")
                for i, match in enumerate(parsed_matches[:10]):
                    print(f"Row {i + 1}: {match}")

            # 5. Export to JSON
            output_filename = "windrawwin_predictions.json"
            with open(output_filename, "w") as f:
                json.dump(parsed_matches, f, indent=4)
            print(f"\nData successfully saved to {output_filename}")

    else:
        print(f"Proxy request failed with status: {response.status_code}")

except Exception as e:
    print(f"AN ERROR OCCURRED: {e}")

print("========================================")
print("  TEST SCRIPT COMPLETED                 ")
print("========================================")
