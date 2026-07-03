import os
import requests

# ==============================================================================
# MATRIX V7.3: SHARP SYNDICATE (OVER 2.5 & DOUBLE CHANCE)
# ==============================================================================
TELEGRAM_TOKEN = os.environ.get("MATRIX_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("MATRIX_TELEGRAM_CHAT_ID")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

class SharpMatrixEngine:
    def __init__(self):
        self.sharp_bookies = [
            "pinnacle", "bet365", "unibet", "matchbook", 
            "betfair_ex_eu", "betonlineag", "williamhill"
        ]
        self.over_25_consensus = []
        self.double_chance_consensus = []

    def fetch_sharp_markets(self):
        print("📡 Pinging Global API for Sharp Syndicate Data...")
        if not ODDS_API_KEY: 
            print("❌ CRITICAL: No API Key detected in environment variables.")
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
            # Swapped 'btts' for 'h2h' to completely bypass the 422 Invalid Market block
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/?apiKey={ODDS_API_KEY}&regions=eu,uk&markets=totals,h2h"
            try:
                r = requests.get(url, timeout=15)
                if r.status_code == 200:
                    data = r.json()
                    print(f"✅ {league}: Successfully pulled {len(data)} matches.")
                    all_matches.extend(data)
                else:
                    print(f"⚠️ API ERROR on {league}: HTTP {r.status_code} - {r.text}")
            except Exception as e:
                print(f"❌ NETWORK ERROR on {league}: {e}")
                
        print(f"🔍 Total matches successfully pulled into the Matrix: {len(all_matches)}")
        return all_matches

    def process_matrix(self):
        print("🚀 Executing V7.3 Sharp Bookie Consensus...")
        matches = self.fetch_sharp_markets()

        if not matches:
            print("🛑 Matrix halted: No matches available to process.")
            return

        for match in matches:
            home = match.get("home_team")
            away = match.get("away_team")
            bookmakers = match.get("bookmakers", [])
            
            sharp_over_votes = 0
            total_sharps_for_over = 0
            over_prices = []
            
            home_win_prices = []
            draw_prices = []
            away_win_prices = []

            for bookie in bookmakers:
                if bookie.get("key", "").lower() not in self.sharp_bookies:
                    continue

                for mkt in bookie.get("markets", []):
                    if mkt.get("key") == "totals":
                        for outcome in mkt.get("outcomes", []):
                            if outcome.get("name") == "Over" and outcome.get("point") == 2.5:
                                price = float(outcome.get("price"))
                                over_prices.append(price)
                                total_sharps_for_over += 1
                                if price <= 1.75:
                                    sharp_over_votes += 1
                                    
                    elif mkt.get("key") == "h2h":
                        for outcome in mkt.get("outcomes", []):
                            if outcome.get("name") == home:
                                home_win_prices.append(float(outcome.get("price")))
                            elif outcome.get("name") == away:
                                away_win_prices.append(float(outcome.get("price")))
                            elif outcome.get("name") == "Draw":
                                draw_prices.append(float(outcome.get("price")))

            # Print diagnostic radar for Over 2.5
            if over_prices:
                avg_over = sum(over_prices)/len(over_prices)
                print(f"📊 {home} vs {away} | Sharp Avg Over 2.5: {avg_over:.2f}")

            # Over 2.5 Math
            if sharp_over_votes >= 2:
                self.over_25_consensus.append(f"🔥 {home} vs {away} ➔ Over 2.5 (Sharp Votes: {sharp_over_votes}/{total_sharps_for_over})")
                
            # Double Chance Math
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
            
        msg = "🎯 **MATRIX V7.3: SHARP MONEY SYNDICATE** 🎯\n\n"
        
        if self.double_chance_consensus:
            msg += "🛡️ **SHARP CONSENSUS: DOUBLE CHANCE (1X / X2)**\n"
            msg += "\n".join(self.double_chance_consensus[:15]) + "\n\n"
            
        if self.over_25_consensus:
            msg += "📈 **SHARP CONSENSUS: OVER 2.5 GOALS**\n"
            msg += "\n".join(self.over_25_consensus[:15]) + "\n\n"

        if not self.over_25_consensus and not self.double_chance_consensus:
            msg += "No sharp money consensus detected in the global market today."

        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    engine = SharpMatrixEngine()
    engine.process_matrix()
    engine.dispatch_alerts()
