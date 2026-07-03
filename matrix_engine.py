import os
import requests

# ==============================================================================
# MATRIX V7: THE SHARP BOOKIE SYNDICATE ENGINE
# ==============================================================================
TELEGRAM_TOKEN = os.environ.get("MATRIX_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("MATRIX_TELEGRAM_CHAT_ID")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

class SharpMatrixEngine:
    def __init__(self):
        # We exclusively track the most ruthless, accurate bookmakers on earth.
        self.sharp_bookies = [
            "pinnacle", "bet365", "unibet", "matchbook", 
            "betfair_ex_eu", "betonlineag", "williamhill"
        ]
        self.over_25_consensus = []
        self.btts_consensus = []

    def fetch_sharp_markets(self):
        print("📡 Pinging Global API for Sharp Syndicate Data...")
        if not ODDS_API_KEY: 
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
            # We request 'eu' and 'uk' regions to ensure we catch our target bookies
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/?apiKey={ODDS_API_KEY}&regions=eu,uk&markets=totals,btts"
            try:
                r = requests.get(url, timeout=15)
                if r.status_code == 200:
                    all_matches.extend(r.json())
            except Exception as e:
                print(f"❌ API Error on {league}: {e}")
                
        return all_matches

    def process_matrix(self):
        print("🚀 Executing V7 Sharp Bookie Consensus...")
        matches = self.fetch_sharp_markets()

        for match in matches:
            home = match.get("home_team")
            away = match.get("away_team")
            bookmakers = match.get("bookmakers", [])
            
            sharp_over_votes = 0
            sharp_btts_votes = 0
            
            total_sharps_for_over = 0
            total_sharps_for_btts = 0

            for bookie in bookmakers:
                bookie_key = bookie.get("key", "").lower()
                
                # Ignore public/soft bookies. Only the sharp money matters.
                if bookie_key not in self.sharp_bookies:
                    continue

                for mkt in bookie.get("markets", []):
                    if mkt.get("key") == "totals":
                        total_sharps_for_over += 1
                        for outcome in mkt.get("outcomes", []):
                            if outcome.get("name") == "Over" and outcome.get("point") == 2.5:
                                # A sharp bookie dropping Over 2.5 to 1.75 or below is a consensus vote
                                if float(outcome.get("price")) <= 1.75:
                                    sharp_over_votes += 1
                                    
                    elif mkt.get("key") == "btts":
                        total_sharps_for_btts += 1
                        for outcome in mkt.get("outcomes", []):
                            if outcome.get("name") == "Yes":
                                # A sharp bookie dropping BTTS to 1.80 or below is a consensus vote
                                if float(outcome.get("price")) <= 1.80:
                                    sharp_btts_votes += 1

            # The 2-Vote Math: If at least 2 sharp bookies agree the odds should be heavily slashed
            if sharp_over_votes >= 2:
                self.over_25_consensus.append(f"🔥 {home} vs {away} ➔ Over 2.5 (Sharp Votes: {sharp_over_votes}/{total_sharps_for_over})")
                
            if sharp_btts_votes >= 2:
                self.btts_consensus.append(f"⚔️ {home} vs {away} ➔ BTTS: Yes (Sharp Votes: {sharp_btts_votes}/{total_sharps_for_btts})")

    def dispatch_alerts(self):
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: 
            return
            
        msg = "🎯 **MATRIX V7: SHARP MONEY SYNDICATE** 🎯\n\n"
        
        if self.over_25_consensus:
            msg += "📈 **SHARP CONSENSUS: OVER 2.5 GOALS**\n"
            msg += "\n".join(self.over_25_consensus[:15]) + "\n\n"
            
        if self.btts_consensus:
            msg += "⚔️ **SHARP CONSENSUS: BTTS YES**\n"
            msg += "\n".join(self.btts_consensus[:15]) + "\n\n"

        if not self.over_25_consensus and not self.btts_consensus:
            msg += "No sharp money consensus detected in the global market today."

        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    engine = SharpMatrixEngine()
    engine.process_matrix()
    engine.dispatch_alerts()
