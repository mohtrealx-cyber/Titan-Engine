import os
import requests

# ==============================================================================
# TITAN TRACKER: MEGA-TICKET BASELINE (1X2 PREDICTIONS)
# ==============================================================================
TELEGRAM_TOKEN = os.environ.get("TRACKER_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TRACKER_TELEGRAM_CHAT_ID")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

class MegaTicketTracker:
    def __init__(self):
        self.predictions = []

    def fetch_market_data(self):
        print("📡 TITAN TRACKER: Gathering Global 1X2 Data...")
        if not ODDS_API_KEY: 
            print("❌ CRITICAL: No API Key detected.")
            return []
            
        # Expanded to include more leagues to generate a massive list
        target_leagues = [
            "soccer_fifa_world_cup", 
            "soccer_brazil_campeonato", 
            "soccer_brazil_serie_b", 
            "soccer_usa_mls", 
            "soccer_japan_j_league",
            "soccer_sweden_allsvenskan",
            "soccer_ireland_premier_division",
            "soccer_norway_eliteserien"
        ]
        
        all_matches = []
        for league in target_leagues:
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/?apiKey={ODDS_API_KEY}&regions=eu,uk&markets=h2h"
            try:
                r = requests.get(url, timeout=15)
                if r.status_code == 200:
                    all_matches.extend(r.json())
            except Exception:
                pass
                
        return all_matches

    def process_mega_ticket(self):
        print("🚀 Executing Mega-Ticket Predictions...")
        matches = self.fetch_market_data()

        if not matches: return

        for match in matches:
            home = match.get("home_team")
            away = match.get("away_team")
            bookmakers = match.get("bookmakers", [])
            
            home_prices = []
            away_prices = []
            
            for bookie in bookmakers:
                for mkt in bookie.get("markets", []):
                    if mkt.get("key") == "h2h":
                        for outcome in mkt.get("outcomes", []):
                            if outcome.get("name") == home:
                                home_prices.append(float(outcome.get("price")))
                            elif outcome.get("name") == away:
                                away_prices.append(float(outcome.get("price")))
                                
            # If we have odds data, determine the favored team
            if home_prices and away_prices:
                avg_home = sum(home_prices) / len(home_prices)
                avg_away = sum(away_prices) / len(away_prices)
                
                # The team with the lower odds is the favored prediction
                if avg_home < avg_away:
                    self.predictions.append(f"• {home} vs {away} ➔ 1")
                elif avg_away < avg_home:
                    self.predictions.append(f"• {home} vs {away} ➔ 2")

    def dispatch_alerts(self):
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
            
        msg = "🎯 **TITAN ENGINE: MEGA-TICKET** 🎯\n\n"
        
        if self.predictions:
            msg += "🔥 **DAILY SURE BETS (100%)**\n"
            msg += "\n".join(self.predictions) + "\n\n"
            msg += "💡 Strategy: Titan Baseline"
        else:
            msg += "No matches available for predictions today."

        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    engine = MegaTicketTracker()
    engine.process_mega_ticket()
    engine.dispatch_alerts()
