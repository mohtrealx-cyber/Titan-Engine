import os
import requests

# ==============================================================================
# MATRIX V3: GLOBAL ODDS CONSENSUS AGGREGATOR
# ==============================================================================
TELEGRAM_TOKEN = os.environ.get("MATRIX_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("MATRIX_TELEGRAM_CHAT_ID")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

class GlobalOddsMatrix:
    def __init__(self):
        self.over_25_consensus = []
        self.btts_consensus = []
        self.double_chance_consensus = []

    def fetch_global_markets(self):
        """Pulls H2H, Totals, and BTTS market liabilities from the global board."""
        if not ODDS_API_KEY: 
            print("❌ Error: ODDS_API_KEY is missing from environment variables.")
            return []
        
        # Requesting 3 distinct markets in a single API call to save bandwidth
        url = f"https://api.the-odds-api.com/v4/sports/upcoming/odds/?apiKey={ODDS_API_KEY}&regions=eu&markets=h2h,totals,btts"
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                return r.json()
            else:
                print(f"❌ API Error: {r.status_code}")
        except Exception as e:
            print(f"❌ Network Error: {e}")
        return []

    def process_matrix(self):
        print("🚀 Scanning Global Bookmaker Consensus for Alternative Markets...")
        matches = self.fetch_global_markets()

        for match in matches:
            sport = match.get("sport_key", "")
            if not sport.startswith("soccer"): 
                continue

            home = match.get("home_team")
            away = match.get("away_team")
            bookmakers = match.get("bookmakers", [])
            
            if not bookmakers: 
                continue
            
            over_2_5_prices = []
            btts_yes_prices = []
            home_win_prices = []
            draw_prices = []
            away_win_prices = []

            # Deep Scan: Aggregate all bookmaker odds for averaging
            for bookie in bookmakers:
                markets = bookie.get("markets", [])
                for mkt in markets:
                    if mkt.get("key") == "totals":
                        for outcome in mkt.get("outcomes", []):
                            if outcome.get("name") == "Over" and outcome.get("point") == 2.5:
                                over_2_5_prices.append(float(outcome.get("price")))
                    elif mkt.get("key") == "btts":
                        for outcome in mkt.get("outcomes", []):
                            if outcome.get("name") == "Yes":
                                btts_yes_prices.append(float(outcome.get("price")))
                    elif mkt.get("key") == "h2h":
                        for outcome in mkt.get("outcomes", []):
                            if outcome.get("name") == home:
                                home_win_prices.append(float(outcome.get("price")))
                            elif outcome.get("name") == away:
                                away_win_prices.append(float(outcome.get("price")))
                            elif outcome.get("name") == "Draw":
                                draw_prices.append(float(outcome.get("price")))

            # 1. OVER 2.5 CONSENSUS
            if over_2_5_prices and len(over_2_5_prices) >= 3:
                avg_over = sum(over_2_5_prices) / len(over_2_5_prices)
                if avg_over <= 1.75: # Market expects high goals
                    self.over_25_consensus.append(f"🔥 {home} vs {away} ➔ Over 2.5 Goals (Avg Odds: {avg_over:.2f})")

            # 2. BTTS YES CONSENSUS
            if btts_yes_prices and len(btts_yes_prices) >= 3:
                avg_btts = sum(btts_yes_prices) / len(btts_yes_prices)
                if avg_btts <= 1.80:
                    self.btts_consensus.append(f"⚔️ {home} vs {away} ➔ BTTS: Yes (Avg Odds: {avg_btts:.2f})")

            # 3. DOUBLE CHANCE CONSENSUS (Math calculation from 1X2 market)
            if home_win_prices and draw_prices and away_win_prices:
                avg_1 = sum(home_win_prices) / len(home_win_prices)
                avg_X = sum(draw_prices) / len(draw_prices)
                avg_2 = sum(away_win_prices) / len(away_win_prices)

                # Calculate the implied probability of a 1X or X2 outcome
                implied_1X = (1 / avg_1) + (1 / avg_X)
                implied_X2 = (1 / avg_2) + (1 / avg_X)

                # If the market gives 1X or X2 an 85% implied probability of happening, it's a lock.
                if implied_1X >= 0.85:
                    self.double_chance_consensus.append(f"🛡️ {home} or Draw (1X) ➔ (Implied Lock: {implied_1X*100:.1f}%)")
                elif implied_X2 >= 0.85:
                    self.double_chance_consensus.append(f"🛡️ {away} or Draw (X2) ➔ (Implied Lock: {implied_X2*100:.1f}%)")

    def dispatch_alerts(self):
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: 
            print("❌ Telegram credentials missing.")
            return
            
        msg = "🎯 **MATRIX V3: GLOBAL ODDS AGGREGATOR** 🎯\n\n"
        
        if self.double_chance_consensus:
            msg += "🛡️ **DOUBLE CHANCE LOCKS (1X / X2)**\n"
            msg += "\n".join(self.double_chance_consensus[:8]) + "\n\n"
        
        if self.over_25_consensus:
            msg += "📈 **MARKET CONSENSUS: OVER 2.5 GOALS**\n"
            msg += "\n".join(self.over_25_consensus[:8]) + "\n\n"
            
        if self.btts_consensus:
            msg += "⚔️ **MARKET CONSENSUS: BTTS YES**\n"
            msg += "\n".join(self.btts_consensus[:8]) + "\n\n"

        if msg == "🎯 **MATRIX V3: GLOBAL ODDS AGGREGATOR** 🎯\n\n":
            msg += "No market consensus found for alternative markets today."

        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    engine = GlobalOddsMatrix()
    engine.process_matrix()
    engine.dispatch_alerts()
