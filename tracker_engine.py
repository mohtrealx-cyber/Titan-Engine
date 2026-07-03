import os
import requests

# ==============================================================================
# TITAN TRACKER VARIANT: CROSS-MARKET ANTI-TRAP VALIDATION
# ==============================================================================
TELEGRAM_TOKEN = os.environ.get("TRACKER_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TRACKER_TELEGRAM_CHAT_ID")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

class TitanCrossMarketValidator:
    def __init__(self):
        self.anchor_bookie = "pinnacle"
        self.edge_threshold = 0.04 # 4% steam trigger
        self.steam_alerts = []

    def fetch_market_data(self):
        print("📡 TITAN VALIDATOR: Scanning Global Markets...")
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
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/?apiKey={ODDS_API_KEY}®ions=eu,uk,us&markets=totals,h2h"
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
        if not matches: return

        for match in matches:
            home, away = match.get("home_team"), match.get("away_team")
            bookmakers = match.get("bookmakers", [])
            
            # --- 1. EXTRACT VALIDATION BASELINES (The "Other Reference" Check) ---
            under_prices = []
            draw_prices = []
            
            for bookie in bookmakers:
                for mkt in bookie.get("markets", []):
                    if mkt.get("key") == "totals":
                        for outcome in mkt.get("outcomes", []):
                            if outcome.get("name") == "Under" and outcome.get("point") == 2.5:
                                under_prices.append(float(outcome.get("price")))
                    elif mkt.get("key") == "h2h":
                        for outcome in mkt.get("outcomes", []):
                            if outcome.get("name") == "Draw":
                                draw_prices.append(float(outcome.get("price")))
                                
            avg_under_price = sum(under_prices)/len(under_prices) if under_prices else 0
            avg_draw_price = sum(draw_prices)/len(draw_prices) if draw_prices else 0

            # --- 2. EXECUTE THE ENGINE & ANTI-TRAP FILTER ---
            
            # HOME WIN STEAM CHECK
            pin_1, avg_1, edge_1 = self.calculate_edge(home, bookmakers, "h2h")
            if edge_1:
                # FILTER: If Under 2.5 odds are extremely low (<= 1.65), it means a defensive 
                # match. A 0-0 or 1-1 trap is highly likely. Reject the Win prediction.
                if avg_under_price and avg_under_price <= 1.65:
                    print(f"🛑 TRAP AVOIDED: {home} (Defensive match script detected)")
                else:
                    self.steam_alerts.append(f"🟢 **{home} (Win)**\n   ↳ Pin: {pin_1:.2f} | Edge: {edge_1*100:.1f}%\n   *(🛡️ Verified: Offensive Match Script)*")

            # AWAY WIN STEAM CHECK
            pin_2, avg_2, edge_2 = self.calculate_edge(away, bookmakers, "h2h")
            if edge_2:
                if avg_under_price and avg_under_price <= 1.65:
                    print(f"🛑 TRAP AVOIDED: {away} (Defensive match script detected)")
                else:
                    self.steam_alerts.append(f"🟢 **{away} (Win)**\n   ↳ Pin: {pin_2:.2f} | Edge: {edge_2*100:.1f}%\n   *(🛡️ Verified: Offensive Match Script)*")

            # OVER 2.5 STEAM CHECK
            pin_O, avg_O, edge_O = self.calculate_edge("Over", bookmakers, "totals")
            if edge_O:
                # FILTER: If Draw odds are heavily favored (<= 3.20), it implies two evenly matched 
                # teams playing a slow, tactical battle. A 1-1 trap is likely. Reject Over 2.5.
                if avg_draw_price and avg_draw_price <= 3.20:
                    print(f"🛑 TRAP AVOIDED: {home} vs {away} (Tactical draw script detected)")
                else:
                    self.steam_alerts.append(f"🔥 **{home} vs {away} (Over 2.5)**\n   ↳ Pin: {pin_O:.2f} | Edge: {edge_O*100:.1f}%\n   *(🛡️ Verified: Anti-Draw script passed)*")

    def dispatch_alerts(self):
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
            
        msg = "⚡ **TITAN TRACKER: CROSS-MARKET VALIDATION** ⚡\n\n"
        if self.steam_alerts:
            msg += "🛡️ **SHARP STEAM + ANTI-TRAP VERIFIED**\n"
            msg += "*(Predictions dynamically filtered against conflicting market data)*\n\n"
            msg += "\n\n".join(self.steam_alerts[:15])
        else:
            msg += "No verified high-confidence steam today. All line movements flagged as potential traps."

        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    engine = TitanCrossMarketValidator()
    engine.process_titan_matrix()
    engine.dispatch_alerts()
