import os
import requests
from datetime import datetime, timedelta

# ==============================================================================
# TITAN TRACKER: DUAL-TIER SIEVE (GOLD & STANDARD)
# ==============================================================================
TELEGRAM_TOKEN = os.environ.get("TRACKER_TRACKER_TELEGRAM_TOKEN") if os.environ.get("TRACKER_TRACKER_TELEGRAM_TOKEN") else os.environ.get("TRACKER_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TRACKER_TRACKER_TELEGRAM_CHAT_ID") if os.environ.get("TRACKER_TRACKER_TELEGRAM_CHAT_ID") else os.environ.get("TRACKER_TELEGRAM_CHAT_ID")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

class DualTierSieve:
    def __init__(self):
        self.anchor_bookie = "pinnacle"
        self.gold_preds = []
        self.std_preds = []
        self.system_stake = "100 KES" 

    def fetch_market_data(self):
        if not ODDS_API_KEY: return []
        target_leagues = [
            "soccer_fifa_world_cup", "soccer_brazil_campeonato", "soccer_brazil_serie_b", 
            "soccer_usa_mls", "soccer_japan_j_league", "soccer_sweden_allsvenskan",
            "soccer_ireland_premier_division", "soccer_norway_eliteserien"
        ]
        all_matches = []
        for league in target_leagues:
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/?apiKey={ODDS_API_KEY}&regions=eu,uk,us&markets=h2h"
            try:
                r = requests.get(url, timeout=15)
                if r.status_code == 200:
                    all_matches.extend(r.json())
            except Exception: pass
        return all_matches

    def process_matrix(self):
        matches = self.fetch_market_data()
        if not matches: return

        now, limit = datetime.utcnow(), datetime.utcnow() + timedelta(hours=48)

        for match in matches:
            home, away = match.get("home_team"), match.get("away_team")
            time_str = match.get("commence_time", "")
            try:
                dt = datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%SZ")
                if dt < now or dt > limit: continue
                fmt_time = dt.strftime("%d %b, %H:%M")
            except: continue 

            bookmakers = match.get("bookmakers", [])
            home_prices, away_prices, draw_prices = [], [], []
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
                avg_home, avg_away, avg_draw = sum(home_prices)/len(home_prices), sum(away_prices)/len(away_prices), sum(draw_prices)/len(draw_prices)
                
                if avg_home < avg_away:
                    fav, avg_fav, pin_fav, sym = home, avg_home, pin_home, "1"
                else:
                    fav, avg_fav, pin_fav, sym = away, avg_away, pin_away, "2"
                
                # GOLD TIER (Strict)
                if avg_fav <= 1.45 and avg_draw >= 4.20 and (not pin_fav or pin_fav <= avg_fav):
                    self.gold_preds.append(f"📅 **{fmt_time}**\n• {home} vs {away} ➔ {sym} `[Stake: {self.system_stake}]`\n\n")
                
                # STANDARD TIER (Relaxed)
                elif avg_fav <= 1.65 and avg_draw >= 3.80 and (not pin_fav or pin_fav <= avg_fav):
                    self.std_preds.append(f"📅 **{fmt_time}**\n• {home} vs {away} ➔ {sym} `[Stake: {self.system_stake}]`\n\n")

    def dispatch_alerts(self):
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
            
        msg = "🎯 **TITAN ENGINE: DUAL-TIER CORE** 🎯\n\n"
        if self.gold_preds:
            msg += f"💎 **GOLD-TIER ({len(self.gold_preds)})**\n" + "".join(self.gold_preds)
        if self.std_preds:
            msg += f"🥈 **STANDARD-TIER ({len(self.std_preds)})**\n" + "".join(self.std_preds)
        
        if not self.gold_preds and not self.std_preds:
            msg += "No actionable matches found for the next 48 hours."
        else:
            msg += "\n📊 **BANKROLL:** 100 KES/match | 💡 Titan Sieve Active"

        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    engine = DualTierSieve()
    engine.process_matrix()
    engine.dispatch_alerts()
