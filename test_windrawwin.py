import requests
from bs4 import BeautifulSoup

def scrape_windrawwin():
    print("Fetching data from WinDrawWin...")
    
    # Target today's predictions
    url = "https://www.windrawwin.com/predictions/today/"
    
    # We must pass headers so the website thinks we are a normal Chrome browser, not a bot
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # 1. Fetch the HTML
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Failed to connect. Status code: {response.status_code}")
        return []

    # 2. Parse the HTML
    soup = BeautifulSoup(response.text, "html.parser")
    windrawwin_picks = []
    
    # Note: You will need to "Inspect Element" on the WinDrawWin website 
    # to find the exact class names for the rows and teams. 
    # I am using placeholder class names here.
    match_rows = soup.find_all("div", class_="match-row-class") 
    
    for row in match_rows:
        try:
            # Extract the raw text
            home_team = row.find("div", class_="home-team-class").text.strip()
            away_team = row.find("div", class_="away-team-class").text.strip()
            prediction_text = row.find("div", class_="prediction-class").text.strip()
            
            # WinDrawWin sometimes predicts exact scores (e.g., "2-1") or outputs "Home", "Away", "Draw"
            # We need to translate their text into our engine's standard 1, X, 2 format
            if "Home" in prediction_text or prediction_text == "1":
                pick = "1"
            elif "Away" in prediction_text or prediction_text == "2":
                pick = "2"
            elif "Draw" in prediction_text or prediction_text == "X":
                pick = "X"
            else:
                pick = "UNKNOWN" # For exact scorelines, you'd add logic to parse "2-1" into "1"
                
            # Only add valid predictions to our list
            if pick in ["1", "X", "2"]:
                windrawwin_picks.append({
                    "home": home_team,
                    "away": away_team,
                    "prediction": pick,
                    "source": "WinDrawWin"
                })
                
        except AttributeError:
            # If a row is missing data (like an ad or a header), skip it
            continue
            
    print(f"Successfully scraped {len(windrawwin_picks)} matches from WinDrawWin.")
    return windrawwin_picks

# Uncomment the line below to test the scraper on your machine
# print(scrape_windrawwin())
