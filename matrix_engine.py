import os
import requests
import datetime
from difflib import SequenceMatcher
from understatapi import UnderstatClient

# ==============================================================================
# 1. STRICT MATRIX ISOLATION CONFIGURATION
# ==============================================================================
TELEGRAM_TOKEN = os.environ.get("MATRIX_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("MATRIX_TELEGRAM_CHAT_ID")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

class GoalMatrixEngine:
    def __init__(self):
        self.safe_over_1_5 = []
        self.value_over_2_5 = []
        self.btts_locks = []

    def get_active_season(self):
        now = datetime.datetime.now()
        return str(now.year - 1) if now.month < 8 else str(now.year)

    def is_similar_name(self, name_a, name_b):
        return SequenceMatcher(None, name_a.lower(), name_b.lower()).ratio() > 0.70

    def get_team_xg(self, team_name, season):
        """Fetches the actual Expected Goals (xG) data to validate the bookies' fear."""
        formatted_name = team_name.replace(" ", "_")
        try:
            with UnderstatClient() as understat:
                match_data = understat.team(team=formatted_name).get_match_data(season=season)
                completed = [m for m in match_data if m.get('isResult') == True]
                if completed:
                    last = completed[-1]
                    if last['h']['title'].lower() == team_name.lower():
                        return float(last['xG']['h'])
                    return float(last['xG']['a'])
        except:
            pass
        return None

    def fetch_goal_markets(self):
        """Pulls global Totals and BTTS market liabilities."""
        if not ODDS_API_KEY: 
            return []
        
        url = f"https://api.the-odds-api.com/v4/sports/upcoming/odds/?apiKey={ODDS_API_KEY}&regions=eu&markets=totals,btts"
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                return r.json()
        except: 
            pass
        return []

    def process_matrix(self):
        print("Scanning Global Goal Markets...")
        matches = self.fetch_goal_markets()
        season = self.get_active_season()

        for match in matches:
            sport = match.get("sport_key", "")
            if not sport.startswith("soccer"): 
                continue

            home = match.get("home_team")
            away = match.get("away_team")
            bookmakers = match.get("bookmakers", [])
            
            if not bookmakers: 
                continue
            
            best_over_2_5 = 999.0
            best_btts_yes = 999.0

            # DEEP SCAN: Iterate through every bookmaker to find the lowest (safest) odds
            for bookie in bookmakers:
                markets = bookie.get("markets", [])
                for mkt in markets:
                    if mkt.get("key") == "totals":
                        for outcome in mkt.get("outcomes", []):
                            if outcome.get("name") == "Over" and outcome.get("point") == 2.5:
                                price = float(outcome.get("price"))
                                if price < best_over_2_5: 
                                    best_over_2_5 = price
                    elif mkt.get("key") == "btts":
                        for outcome in mkt.get("outcomes", []):
                            if outcome.get("name") == "Yes":
                                price = float(outcome.get("price"))
                                if price < best_btts_yes: 
                                    best_btts_yes = price

            # FILTER 1: Safest Accumulator (Over 1.5)
            # Threshold raised to 1.80 for deep comparison market coverage
            if best_over_2_5 != 999.0 and best_over_2_5 <= 1.80:
                self.safe_over_1_5.append(f"🔒 {home} vs {away}")
                
                # FILTER 2: High Yield (Over 2.5 backed by pure xG Math)
                h_xg = self.get_team_xg(home, season)
                a_xg = self.get_team_xg(away, season)
                if h_xg and a_xg and (h_xg + a_xg >= 2.8):
                    self.value_over_2_5.append(f"🔥 {home} vs {away} ➔ Over 2.5 (xG: {h_xg+a_xg:.2f} | Best Odds: {best_over_2_5})")

            # FILTER 3: The BTTS Locks
            # Threshold raised to 1.95 for knockout stage coverage
            if best_btts_yes != 999.0 and best_btts_yes <= 1.95:
                self.btts_locks.append(f"⚔️ {home} vs {away} ➔ BTTS: Yes (Best Odds: {best_btts_yes})")

    def dispatch_alerts(self):
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: 
            return
        
        msg = "⚽ **THE GOAL-LINE MATRIX** ⚽\n\n"
        
        if self.safe_over_1_5:
            msg += "🛡️ **SAFEST ACCUMULATOR (OVER 1.5)**\n"
            msg += "\n".join(self.safe_over_1_5[:8]) + "\n\n" 
            
        if self.value_over_2_5:
            msg += "📈 **HIGH YIELD (OVER 2.5 + xG BACKED)**\n"
            msg += "\n".join(self.value_over_2_5[:5]) + "\n\n"
            
        if self.btts_locks:
            msg += "🎯 **BTTS HOTSPOTS**\n"
            msg += "\n".join(self.btts_locks[:5]) + "\n\n"

        if msg == "⚽ **THE GOAL-LINE MATRIX** ⚽\n\n":
            msg += "No high-confidence goal markets detected today."

        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    engine = GoalMatrixEngine()
    engine.process_matrix()
    engine.dispatch_alerts()
