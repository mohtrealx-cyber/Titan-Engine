import os
import requests

# ==============================================================================
# TITAN TRACKER: ELITE CORE (WITH SYSTEMATIC FLAT STAKING SELECTIONS)
# ==============================================================================
TELEGRAM_TOKEN = os.environ.get("TRACKER_TRACKER_TELEGRAM_TOKEN") if os.environ.get("TRACKER_TRACKER_TELEGRAM_TOKEN") else os.environ.get("TRACKER_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TRACKER_TRACKER_TELEGRAM_CHAT_ID") if os.environ.get("TRACKER_TRACKER_TELEGRAM_CHAT_ID") else os.environ.get("TRACKER_TELEGRAM_CHAT_ID")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

class GoldTierStakingSieve:
    def __init__(self):
        self.anchor_bookie = "pinnacle"
        self.gold_predictions = []
        # Enforcing a strict 1-Unit constant allocations across all selections
        self.system_stake = "1.0 Unit" 

    def fetch_market_data(self):
        print("📡 TITAN TRACKER: Fetching high-volume global markets...")
        if not ODDS_API_KEY: 
            print("❌ CRITICAL: No API Key detected.")
            return []
            
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
        print("🚀 Running Triple-Layer Sieve & Allocating Fixed Stakes...")
        matches = self.fetch_market_data()

        if not matches: return

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
                
                # Triple-Layer Sieve Pipelines
                if avg_fav_odds > 1.45: continue
                if avg_draw < 4.20: continue
                if pin_fav_odds and pin_fav_odds > avg_fav_odds: continue
                
                # Append prediction with structural flat stake tracking label
                self.gold_predictions.append(f"• {home} vs {away} ➔ {prediction_symbol} `[Allocated Stake: {self.system_stake}]`")

    def dispatch_alerts(self):
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
            
        msg = "🎯 **TITAN ENGINE: ELITE CORE** 🎯\n\n"
        
        if self.gold_predictions:
            msg += f"💎 **GOLD-TIER SELECTIONS ({len(self.gold_predictions)} SECURED)**\n"
            msg += "*(Filtered: Probability Floors, Draw Suppression & Sharp Convexity)*\n\n"
            msg += "\n".join(self.gold_predictions) + "\n\n"
            msg += "📊 **BANKROLL ALLOCATION SYSTEM**\n"
            msg += "↳ Plan: Flat Unit Sizing\n"
            msg += f"↳ Target Risk: {self.system_stake} per selection consistently.\n\n"
            msg += "💡 Strategy: Titan High-Confidence Sieve"
        else:
            msg += "No matches cleared the Triple-Layer validation checks today. Sieve remained perfectly tight."

        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    engine = GoldTierStakingSieve()
    engine.process_gold_matrix()
    engine.dispatch_alerts()
