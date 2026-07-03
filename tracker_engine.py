import os
import requests

# ==============================================================================
# TITAN TRACKER: TRIPLE-LAYER QUANTITATIVE MATRIX (BEST OF THE BEST)
# ==============================================================================
TELEGRAM_TOKEN = os.environ.get("TRACKER_TRACKER_TELEGRAM_TOKEN") if os.environ.get("TRACKER_TRACKER_TELEGRAM_TOKEN") else os.environ.get("TRACKER_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TRACKER_TRACKER_TELEGRAM_CHAT_ID") if os.environ.get("TRACKER_TRACKER_TELEGRAM_CHAT_ID") else os.environ.get("TRACKER_TELEGRAM_CHAT_ID")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

class GoldTierSieve:
    def __init__(self):
        self.anchor_bookie = "pinnacle"
        self.gold_predictions = []

    def fetch_market_data(self):
        print("📡 TITAN TRACKER: Compiling Massive Global Board...")
        if not ODDS_API_KEY: 
            print("❌ CRITICAL: No API Key detected.")
            return []
            
        # Expanded league footprint to capture maximum global volume
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
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/?apiKey={ODDS_API_KEY}&regions=eu,uk,us&markets=h2h"
            try:
                r = requests.get(url, timeout=15)
                if r.status_code == 200:
                    all_matches.extend(r.json())
            except Exception:
                pass
                
        return all_matches

    def process_gold_matrix(self):
        print("🚀 Running Triple-Layer Sieve Calculations...")
        matches = self.fetch_market_data()

        if not matches: 
            print("🛑 Matrix halted: No raw data pulled.")
            return

        for match in matches:
            home = match.get("home_team")
            away = match.get("away_team")
            bookmakers = match.get("bookmakers", [])
            
            home_prices = []
            away_prices = []
            draw_prices = []
            
            pin_home, pin_away = None, None
            
            for bookie in bookmakers:
                bookie_key = bookie.get("key", "").lower()
                for mkt in bookie.get("markets", []):
                    if mkt.get("key") == "h2h":
                        for outcome in mkt.get("outcomes", []):
                            price = float(outcome.get("price"))
                            
                            if outcome.get("name") == home:
                                home_prices.append(price)
                                if bookie_key == self.anchor_bookie: pin_home = price
                            elif outcome.get("name") == away:
                                away_prices.append(price)
                                if bookie_key == self.anchor_bookie: pin_away = price
                            elif outcome.get("name") == "Draw":
                                draw_prices.append(price)

            if home_prices and away_prices and draw_prices:
                avg_home = sum(home_prices) / len(home_prices)
                avg_away = sum(away_prices) / len(away_prices)
                avg_draw = sum(draw_prices) / len(draw_prices)
                
                # Identify which side the market is backing as the favorite
                if avg_home < avg_away:
                    fav_team = home
                    avg_fav_odds = avg_home
                    pin_fav_odds = pin_home
                    prediction_symbol = "1"
                else:
                    fav_team = away
                    avg_fav_odds = avg_away
                    pin_fav_odds = pin_away
                    prediction_symbol = "2"
                
                # === THE TRIPLE-LAYER FILTRATION PIPELINE ===
                
                # Layer 1: Strictly enforce the raw win probability floor
                if avg_fav_odds > 1.45:
                    continue
                    
                # Layer 2: Draw Suppression Check (Eliminates low-scoring trap profiles)
                if avg_draw < 4.20:
                    continue
                    
                # Layer 3: Sharp Convexity Cross-Check (Pinnacle must confirm or beat public price)
                if pin_fav_odds and pin_fav_odds > avg_fav_odds:
                    continue
                
                # Match successfully cleared all filters -> Gold Tier Status Locked
                self.gold_predictions.append(f"• {home} vs {away} ➔ {prediction_symbol}")

    def dispatch_alerts(self):
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: 
            print("❌ Telegram credentials missing.")
            return
            
        msg = "🎯 **TITAN ENGINE: ELITE CORE** 🎯\n\n"
        
        if self.gold_predictions:
            msg += f"💎 **GOLD-TIER SELECTIONS ({len(self.gold_predictions)} SECURED)**\n"
            msg += "*(Filtered using Implied Probability Floors, Draw Suppression, & Sharp Convexity)*\n\n"
            msg += "\n".join(self.gold_predictions) + "\n\n"
            msg += "💡 Strategy: Titan High-Confidence Sieve"
        else:
            msg += "No matches cleared the Triple-Layer validation checks today. Sieve remained perfectly tight."

        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    engine = GoldTierSieve()
    engine.process_gold_matrix()
    engine.dispatch_alerts()
