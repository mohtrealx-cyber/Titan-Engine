import os
import sys
import json
import requests
from bs4 import BeautifulSoup

print("========================================")
print("  STARTING TITAN ENGINE RAW EXTRACTION (V2)")
print("========================================")

API_KEY = os.environ.get("SCRAPER_API_KEY")

if not API_KEY:
    print("ERROR: SCRAPER_API_KEY environment variable not found!")
    sys.exit(1)

target_url = "https://www.windrawwin.com/predictions/today/"
proxy_url = f"http://api.scraperapi.com?api_key={API_KEY}&url={target_url}"

try:
    print("Sending request via ScraperAPI proxy...")
    response = requests.get(proxy_url, timeout=60)
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "lxml")
        
        # Target the row containers directly instead of climbing the DOM
        # WinDrawWin heavily uses 'wtrow' for standard rows and 'wttr' for others
        match_rows = soup.find_all("div", class_=lambda c: c and ("wtrow" in c or "wttr" in c))
        
        raw_matches = []
        seen_urls = set()

        for row in match_rows:
            # Look for the match link INSIDE this specific row container
            link = row.find("a", href=lambda h: h and "/tips/" in h and "-v-" in h)
            
            if link:
                url = link['href']
                
                # Skip duplicate listings
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                
                # Extract teams
                teams_str = link.get_text(strip=True)
                if " v " in teams_str:
                    home_team, away_team = teams_str.split(" v ", 1)
                else:
                    home_team, away_team = "Unknown", "Unknown"

                # Grab ONLY the text inside this specific row container
                raw_text_block = " ".join(row.stripped_strings)
                
                raw_matches.append({
                    "Home": home_team.strip(),
                    "Away": away_team.strip(),
                    "Raw_Data_Block": raw_text_block
                })

        print(f"\nSuccessfully extracted {len(raw_matches)} isolated match blocks.")
        
        if raw_matches:
            print("\nSample of data ready for the LLM:\n")
            for i, match in enumerate(raw_matches[:3]):
                print(f"Row {i + 1}: {match}\n")

        # Export for the LLM parser
        output_filename = "windrawwin_ready_for_llm.json"
        with open(output_filename, "w") as f:
            json.dump(raw_matches, f, indent=4)
        print(f"Data successfully saved to {output_filename}")

    else:
        print(f"Proxy request failed with status: {response.status_code} - {response.text}")

except Exception as e:
    print(f"AN ERROR OCCURRED: {e}")
