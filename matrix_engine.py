import os
import requests

# ==============================================================================
# MATRIX V4: TRUE GLOBAL TARGETING
# ==============================================================================
TELEGRAM_TOKEN = os.environ.get("MATRIX_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("MATRIX_TELEGRAM_CHAT_ID")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

class GlobalOddsMatrix:
    def __init__(self):
        self.over_25_consensus = []
        self.btts_consensus = []
        self.double_chance_consensus = []
        
        # Targeting specific high-liquidity active leagues to bypass the 8-game limit
        self.target_leagues = [
            "soccer_fifa_world_cup",
            "soccer_brazil_campeonato",
            "soccer_brazil_serie_b",
            "soccer_usa_mls",
            "soccer_japan_j_league"
        ]

    def fetch_league_markets(self, sport_key):
        """Pulls H2H, Totals, and BTTS market liabilities for a specific league."""
        if not ODDS_API_KEY: 
            return []
        
        url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/?apiKey={ODDS_API_KEY}®ions=eu&markets=h2h,totals,btts"
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return []

    def process_matrix(self):
        print("🚀 Scanning Global Bookmaker Consensus for Alternative Markets...")
        
        for league in self.target_leagues:
            print(f"📡 Scanning {league}...")
            matches = self.fetch_league_markets(league)

            for match in matches:
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
                # Requires at least 2 bookmakers offering odds to confirm consensus
                if over_2_5_prices and len(over_2_5_prices) >= 2:
                    avg_over = sum(over_2_5_prices) / len(over_2_5_prices)
                    if avg_over <= 1.75: 
                        self.over_25_consensus.append(f"🔥 {home} vs {away} ➔ Over 2.5 Goals (Avg: {avg_over:.2f})")

                # 2. BTTS YES CONSENSUS
                if btts_yes_prices and len(btts_yes_prices) >= 2:
                    avg_btts = sum(btts_yes_prices) / len(btts_yes_prices)
                    if avg_btts <= 1.80:
                        self.btts_consensus.append(f"⚔️ {home} vs {away} ➔ BTTS: Yes (Avg: {avg_btts:.2f})")

                # 3. DOUBLE CHANCE CONSENSUS 
                if home_win_prices and draw_prices and away_win_prices:
                    avg_1 = sum(home_win_prices) / len(home_win_prices)
                    avg_X = sum(draw_prices) / len(draw_prices)
                    avg_2 = sum(away_win_prices) / len(away_win_prices)

                    implied_1X = (1 / avg_1) + (1 / avg_X)
                    implied_X2 = (1 / avg_2) + (1 / avg_X)

                    if implied_1X >= 0.85:
                        self.double_chance_consensus.append(f"🛡️ {home} or Draw (1X) ➔ (Lock: {implied_1X*100:.1f}%)")
                    elif implied_X2 >= 0.85:
                        self.double_chance_consensus.append(f"🛡️ {away} or Draw (X2) ➔ (Lock: {implied_X2*100:.1f}%)")

    def dispatch_alerts(self):
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: 
            return
            
        msg = "🎯 **MATRIX V4: TRUE GLOBAL AGGREGATOR** 🎯\n\n"
        
        if self.double_chance_consensus:
            msg += "🛡️ **DOUBLE CHANCE LOCKS (1X / X2)**\n"
            msg += "\n".join(self.double_chance_consensus[:8]) + "\n\n"
        
        if self.over_25_consensus:
            msg += "📈 **MARKET CONSENSUS: OVER 2.5 GOALS**\n"
            msg += "\n".join(self.over_25_consensus[:8]) + "\n\n"
            
        if self.btts_consensus:
            msg += "⚔️ **MARKET CONSENSUS: BTTS YES**\n"
            msg += "\n".join(self.btts_consensus[:8]) + "\n\n"

        if msg == "🎯 **MATRIX V4: TRUE GLOBAL AGGREGATOR** 🎯\n\n":
            msg += "No market consensus found for alternative markets today."

        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    engine = GlobalOddsMatrix()
    engine.process_matrix()
    engine.dispatch_alerts()
