import os
import sys
import json
import requests
from bs4 import BeautifulSoup

print("========================================")
print("  STARTING TITAN ENGINE RAW EXTRACTION")
print("========================================")

API_KEY = os.environ.get("SCRAPER_API_KEY")

if not API_KEY:
    print("ERROR: SCRAPER_API_KEY environment variable not found!")
    sys.exit(1)

target_url = "https://www.windrawwin.com/predictions/today/"

# Keeping render=true OFF to prevent ScraperAPI 500 timeouts
proxy_url = f"http://api.scraperapi.com?api_key={API_KEY}&url={target_url}"

try:
    print("Sending request via ScraperAPI proxy...")
    response = requests.get(proxy_url, timeout=60)
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "lxml")
        
        # Target the anchors directly - this is the most stable element on the page
        match_links = soup.find_all("a", href=lambda h: h and "/tips/" in h and "-v-" in h)
        
        raw_matches = []
        seen_urls = set()

        for link in match_links:
            url = link['href']
            
            # Skip duplicates (WDW sometimes lists a match twice)
            if url in seen_urls:
                continue
            seen_urls.add(url)
            
            # Extract teams
            teams_str = link.get_text(strip=True)
            if " v " in teams_str:
                home_team, away_team = teams_str.split(" v ", 1)
            else:
                home_team, away_team = "Unknown", "Unknown"

            # Climb up the DOM to the parent row container
            # Usually it's a div with 'wtrow' or 'wttr', but we fall back to climbing 3 levels up
            row_container = link.find_parent('div', class_=lambda c: c and ('wtrow' in c or 'wttr' in c))
            
            if not row_container:
                row_container = link.find_parent().find_parent().find_parent()
            
            if row_container:
                # Grab ALL text inside this row, strip out the messy newlines, and space it out
                raw_text_block = " ".join(row_container.stripped_strings)
                
                raw_matches.append({
                    "Home": home_team.strip(),
                    "Away": away_team.strip(),
                    "Raw_Data_Block": raw_text_block
                })

        print(f"\nSuccessfully extracted {len(raw_matches)} match blocks.")
        
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
