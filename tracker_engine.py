import os
import csv
import datetime
import requests

# ==============================================================================
# 1. STRICT ISOLATION CONFIGURATION
# ==============================================================================
TELEGRAM_TOKEN = os.environ.get("TRACKER_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TRACKER_TELEGRAM_CHAT_ID")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

ACTIVE_STRATEGY = "Line Movement Tracker"
BASELINE_FILE = "odds_baseline_tracker.csv"
MOVEMENT_THRESHOLD_PCT = 7.0  # Flags an alert if odds drop by 7% or more

def fetch_live_market_odds():
    """Fetches all upcoming football matches across major global markets."""
    if not ODDS_API_KEY:
        print("Missing Odds API Key.")
        return []
    
    # Requesting Head-to-Head (h2h) lines from European/Global bookmakers
    url = f"https://api.the-odds-api.com/v4/sports/upcoming/odds/?apiKey={ODDS_API_KEY}&regions=eu&markets=h2h"
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"API Fetch Error: {e}")
    return []

def load_stored_baselines():
    """Loads previously recorded opening lines into memory."""
    baselines = {}
    if os.path.exists(BASELINE_FILE):
        with open(BASELINE_FILE, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)  # Skip header row
            for row in reader:
                if len(row) >= 5:
                    match_id, home_team, away_team, outcome_type, opening_odds = row[0], row[1], row[2], row[3], float(row[4])
                    baselines[f"{match_id}_{outcome_type}"] = {
                        "home": home_team,
                        "away": away_team,
                        "opening_odds": opening_odds
                    }
    return baselines

def update_baseline_database(current_records):
    """Saves updated opening and current lines back to persistent storage."""
    with open(BASELINE_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Match_ID", "Home_Team", "Away_Team", "Outcome_Type", "Opening_Odds", "Last_Checked"])
        for uid, data in current_records.items():
            match_id, outcome_type = uid.split("_", 1)
            writer.writerow([match_id, data["home"], data["away"], outcome_type, data["opening_odds"], datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')])

def send_isolated_alert(message):
    """Dispatches real-time alerts exclusively to the Line Tracker channel."""
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        try:
            requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=10)
        except Exception as e:
            print(f"Telegram Delivery Failure: {e}")

def execute_tracking_pipeline():
    print("Initializing Line Movement Scanner...")
    live_data = fetch_live_market_odds()
    if not live_data:
        print("No live market data fetched. Exiting pipeline.")
        return
        
    stored_baselines = load_stored_baselines()
    updated_records = {}
    alerts_triggered = []

    for fixture in live_data:
        # Strictly isolate football/soccer fixtures
        sport = fixture.get("sport_key", "")
        if not sport.startswith("soccer"):
            continue
            
        match_id = fixture.get("id")
        home_team = fixture.get("home_team")
        away_team = fixture.get("away_team")
        bookmakers = fixture.get("bookmakers", [])
        
        if not bookmakers:
            continue
            
        # Extract 1X2 market prices from the anchor bookmaker
        markets = bookmakers[0].get("markets", [])
        if not markets:
            continue
            
        outcomes = markets[0].get("outcomes", [])
        for selection in outcomes:
            name = selection.get("name")
            current_price = float(selection.get("price"))
            
            # Map name to outcome type (1 = Home, X = Draw, 2 = Away)
            if name == home_team:
                outcome_type = "1"
            elif name == away_team:
                outcome_type = "2"
            else:
                outcome_type = "X"
                
            unique_key = f"{match_id}_{outcome_type}"
            
            # If match is seen for the first time, establish current price as the opening baseline
            if unique_key not in stored_baselines:
                updated_records[unique_key] = {
                    "home": home_team,
                    "away": away_team,
                    "opening_odds": current_price
                }
            else:
                # Retrieve the established opening line
                opening_price = stored_baselines[unique_key]["opening_odds"]
                updated_records[unique_key] = stored_baselines[unique_key]
                
                # Calculate movement velocity
                if current_price < opening_price:
                    drop_pct = ((opening_price - current_price) / opening_price) * 100
                    
                    if drop_pct >= MOVEMENT_THRESHOLD_PCT:
                        label = "HOME WIN" if outcome_type == "1" else "AWAY WIN" if outcome_type == "2" else "DRAW"
                        alert_msg = (
                            f"📉 *SHARP MONEY DETECTION* 📉\n\n"
                            f"🏆 *League:* {sport.replace('soccer_', '').upper().replace('_', ' ')}\n"
                            f"⚔️ *Match:* {home_team} vs {away_team}\n"
                            f"🎯 *Target Market:* {label}\n\n"
                            f"📊 *Opening Line:* `{opening_price:.2f}`\n"
                            f"🔥 *Current Line:* `{current_price:.2f}`\n"
                            f"🚨 *Market Drop Velocity:* `-{drop_pct:.1f}%`\n\n"
                            f"⚠️ *Action:* Line crashing rapidly. Heavy syndicate or smart volume moving inside the bookmaker."
                        )
                        alerts_triggered.append(alert_msg)

    # Commit state changes to the repository tracking layer
    update_baseline_database(updated_records)
    
    if alerts_triggered:
        print(f"Triggering {len(alerts_triggered)} market alerts...")
        for alert in alerts_triggered:
            send_isolated_alert(alert)
    else:
        print("Market baseline updated. No sharp velocity anomalies detected.")

if __name__ == "__main__":
    execute_tracking_pipeline()
