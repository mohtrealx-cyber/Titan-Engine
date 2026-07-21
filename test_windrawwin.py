import os
import sys
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from google import genai
from google.genai import types

# --- 1. SETUP & VALIDATE KEYS ---
SCRAPER_API_KEY = os.environ.get("SCRAPER_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not SCRAPER_API_KEY or not GEMINI_API_KEY:
    print("ERROR: Missing API Keys.")
    print("Ensure SCRAPER_API_KEY and GEMINI_API_KEY are set in GitHub Secrets.")
    sys.exit(1)

# --- 2. RAW EXTRACTION ---
print("========================================")
print("  STARTING TITAN ENGINE RAW EXTRACTION")
print("========================================")

target_url = "https://www.windrawwin.com/predictions/today/"
proxy_url = f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={target_url}"
raw_matches = []

try:
    print("Sending request via ScraperAPI proxy...")
    response = requests.get(proxy_url, timeout=60)
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "lxml")
        match_rows = soup.find_all("div", class_=lambda c: c and ("wtrow" in c or "wttr" in c))
        seen_urls = set()

        for row in match_rows:
            link = row.find("a", href=lambda h: h and "/tips/" in h and "-v-" in h)
            if link:
                url = link['href']
                if url in seen_urls: continue
                seen_urls.add(url)
                
                teams_str = link.get_text(strip=True)
                if " v " in teams_str:
                    home_team, away_team = teams_str.split(" v ", 1)
                else:
                    home_team, away_team = "Unknown", "Unknown"

                raw_text_block = " ".join(row.stripped_strings)
                raw_matches.append({
                    "Home": home_team.strip(),
                    "Away": away_team.strip(),
                    "Raw_Data_Block": raw_text_block
                })
        print(f"Successfully extracted {len(raw_matches)} isolated match blocks.")
    else:
        print(f"Proxy request failed: {response.status_code} - {response.text}")
        sys.exit(1)

except Exception as e:
    print(f"Extraction Error: {e}")
    sys.exit(1)


# --- 3. LLM PARSING ---
print("\n========================================")
print("  STARTING TITAN ENGINE LLM PARSER")
print("========================================")

if not raw_matches:
    print("No matches to parse. Exiting.")
    sys.exit(0)

client = genai.Client(api_key=GEMINI_API_KEY)

print(f"Sending batch of {len(raw_matches)} to the LLM for parsing...\n")

system_prompt = """
You are a sports data extraction engine. 
I will provide a JSON array of football matches. Each match contains a 'Raw_Data_Block' of unstructured text.
Your job is to extract the betting prediction and odds, and return a JSON array of objects following this exact schema:
[
  {
    "Home": "Home Team Name",
    "Away": "Away Team Name",
    "Prediction": "1" for Home Win, "X" for Draw, "2" for Away Win,
    "Correct_Score": "e.g., 1-1 or 2-0",
    "Stake": "Small, Medium, or Large",
    "Odds_1": "Convert fractional home odds to decimal float (e.g., 13/10 = 2.30)",
    "Odds_X": "Convert fractional draw odds to decimal float",
    "Odds_2": "Convert fractional away odds to decimal float"
  }
]
Extract the odds immediately following the '1 X 2' text in the block.
"""

prompt = system_prompt + "\n\nRaw Match Data:\n" + json.dumps(raw_matches, indent=2)

try:
    response = client.models.generate_content(
        model='gemini-3.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        )
    )
    
    parsed_data = json.loads(response.text)
    
    print("--- LLM PARSING SUCCESSFUL ---")
    
    # Create a data directory if it doesn't exist
    os.makedirs("data", exist_ok=True)
    
    # Generate today's date for the filename
    today_str = datetime.now().strftime("%Y-%m-%d")
    output_filename = f"data/predictions_windrawwin_{today_str}.json"
    
    # Save the timestamped daily file
    with open(output_filename, "w") as f:
        json.dump(parsed_data, f, indent=4)
        
    # Also save a 'latest' file for easy overriding access
    with open("data/latest_windrawwin.json", "w") as f:
        json.dump(parsed_data, f, indent=4)
        
    print(f"\nSaved structured data to {output_filename}")
    
except Exception as e:
    print(f"Error during LLM parsing: {e}")
    sys.exit(1)
