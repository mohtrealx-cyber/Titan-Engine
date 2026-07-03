import os
import requests

# ==============================================================================
# TITAN ENGINE (LINE TRACKER VARIANT): STEAM & INEFFICIENCY SCANNER
# ==============================================================================
TELEGRAM_TOKEN = os.environ.get("MATRIX_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("MATRIX_TELEGRAM_CHAT_ID")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

class TitanLineTracker:
    def __init__(self):
        # The Sharp Anchor
        self.anchor_bookie = "pinnacle"
        # 5% Inefficiency Threshold
        self.edge_threshold = 0.05 
        self.steam_alerts = []

    def fetch_market_data(self):
        print("📡 TITAN VARIANT: Scanning Global Markets for Line Movement...")
        if not ODDS_API_KEY: 
            print("❌ CRITICAL: No API Key detected.")
            return []
            
        target_leagues = [
            "soccer_fifa_world_cup", 
            "soccer_brazil_campeonato", 
            "soccer_brazil_serie_b", 
            "soccer_usa_mls", 
            "soccer_japan_j_league"
        ]
        
        all_matches = []
        for league in target_leagues:
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/?apiKey={ODDS_API_KEY}&regions=eu,uk,us&markets=totals,h2h"
            try:
                r = requests.get(url, timeout=15)
                if r.status_code == 200:
                    all_matches.extend(r.json())
            except Exception as e:
                print(f"⚠️ Error pulling {league}: {e}")
        return all_matches

    def calculate_edge(self, outcome_name, bookmakers, market_key):
        pinnacle_price = None
        market_prices = []
        
        for bookie in bookmakers:
            bookie_key = bookie.get("key", "").lower()
            for mkt in bookie.get("markets", []):
                if mkt.get("key") == market_key:
                    for outcome in mkt.get("outcomes", []):
                        if outcome.get("name") == outcome_name:
                            if market_key == "totals" and outcome.get("point") != 2.5:
                                continue
                            price = float(outcome.get("price"))
                            if bookie_key == self.anchor_bookie:
                                pinnacle_price = price
                            else:
                                market_prices.append(price)
                                
        if pinnacle_price and len(market_prices) >= 3:
            market_avg = sum(market_prices) / len(market_prices)
            if pinnacle_price < market_avg:
                edge = (market_avg - pinnacle_price) / pinnacle_price
                if edge >= self.edge_threshold:
                    return pinnacle_price, market_avg, edge
        return None, None, None

    def process_titan_matrix(self):
        matches = self.fetch_market_data()
        if not matches: 
            print("🛑 No matches to process.")
            return

        for match in matches:
            home, away = match.get("home_team"), match.get("away_team")
            bookmakers = match.get("bookmakers", [])
            
            # 1. Scan for Home Win Steam
            pin_1, avg_1, edge_1 = self.calculate_edge(home, bookmakers, "h2h")
            if edge_1: 
                self.steam_alerts.append(f"🚨 **{home} (Win)**\n   ↳ Pin: {pin_1:.2f} | Market: {avg_1:.2f} | ⚡ Edge: {edge_1*100:.1f}%")

            # 2. Scan for Away Win Steam
            pin_2, avg_2, edge_2 = self.calculate_edge(away, bookmakers, "h2h")
            if edge_2: 
                self.steam_alerts.append(f"🚨 **{away} (Win)**\n   ↳ Pin: {pin_2:.2f} | Market: {avg_2:.2f} | ⚡ Edge: {edge_2*100:.1f}%")

            # 3. Scan for Over 2.5 Steam
            pin_O, avg_O, edge_O = self.calculate_edge("Over", bookmakers, "totals")
            if edge_O: 
                self.steam_alerts.append(f"🔥 **{home} vs {away} (Over 2.5)**\n   ↳ Pin: {pin_O:.2f} | Market: {avg_O:.2f} | ⚡ Edge: {edge_O*100:.1f}%")

    def dispatch_alerts(self):
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: 
            print("❌ Telegram credentials missing.")
            return
            
        msg = "⚡ **TITAN ENGINE: LINE TRACKER VARIANT** ⚡\n\n"
        if self.steam_alerts:
            msg += "📉 **SHARP STEAM DETECTED**\n\n"
            msg += "\n\n".join(self.steam_alerts[:15])
        else:
            msg += "No significant sharp line movement detected today. Market is efficient."

        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    engine = TitanLineTracker()
    engine.process_titan_matrix()
    engine.dispatch_alerts()
