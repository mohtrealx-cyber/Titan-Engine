import os
import sys
import requests
from bs4 import BeautifulSoup

print("========================================")
print("  STARTING WINDRAWWIN SCRAPER (SCRAPERAPI)")
print("========================================")

# Grabs SCRAPER_API_KEY (with underscore)
API_KEY = os.environ.get("SCRAPER_API_KEY")

if not API_KEY:
    print("ERROR: SCRAPER_API_KEY environment variable not found!")
    sys.exit(1)

target_url = "https://www.windrawwin.com/predictions/today/"
proxy_url = f"http://api.scraperapi.com?api_key={API_KEY}&url={target_url}&render=true"

try:
    print("Sending request via ScraperAPI proxy...")
    # ScraperAPI can take up to 60 seconds to rotate proxies and render JS
    response = requests.get(proxy_url, timeout=60)
    
    print(f"HTTP Status Code: {response.status_code}")
    print(f"Downloaded HTML Length: {len(response.text)} characters")

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
                # Extract text from each individual cell (<td> or <th>) and ignore empty ones
                columns = [td.get_text(separator=" ", strip=True) for td in row.find_all(['td', 'th'])]
                
                # Filter out empty cells
                columns = [col for col in columns if col]
                if not columns:
                    continue

                # 1. Identify the match column by looking for the " v " separator
                match_col = next((col for col in columns if " v " in col), None)
                if not match_col:
                    continue # Skip non-match rows (like headers or ads)

                home_team, away_team = match_col.split(" v ", 1)
                match_idx = columns.index(match_col)
                
                # 2. Extract Prediction and Odds
                prediction = columns[match_idx + 1] if len(columns) > match_idx + 1 else "Unknown"
                odds = columns[match_idx + 2] if len(columns) > match_idx + 2 else "N/A"

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
                
                # 4. Structure the output
                match_data = {
                    "Home": home_team.strip(),
                    "Away": away_team.strip(),
                    "Market": market,
                    "Prediction": prediction.strip(),
                    "Odds": odds.strip()
                }
                
                parsed_matches.append(match_data)
                
            print(f"\nSuccessfully extracted and categorized {len(parsed_matches)} matches.")
            print("Sample data from first 10 rows:\n")
            
            for i, match in enumerate(parsed_matches[:10]):
                print(f"Row {i + 1}: {match}")

    else:
        print(f"Proxy request failed with status: {response.status_code}")

except Exception as e:
    print(f"AN ERROR OCCURRED: {e}")

print("========================================")
print("  TEST SCRIPT COMPLETED                 ")
print("========================================")
