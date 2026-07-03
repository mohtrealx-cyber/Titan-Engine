import os
import requests
from curl_cffi import requests as cffi_requests
from bs4 import BeautifulSoup
from difflib import SequenceMatcher
from collections import defaultdict

# ==============================================================================
# MATRIX V6: ENSEMBLE VOTING ENGINE (2-out-of-3)
# ==============================================================================
TELEGRAM_TOKEN = os.environ.get("MATRIX_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("MATRIX_TELEGRAM_CHAT_ID")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

class SyndicateVotingEngine:
    def __init__(self):
        self.session = cffi_requests.Session(impersonate="chrome")
        # Tracks how many "Votes" a match receives from the 3 Hubs
        self.btts_votes = defaultdict(int)
        self.over25_votes = defaultdict(int)
        
    def normalize_name(self, name):
        """Strips useless words so cross-referencing between APIs and scrapers is bulletproof."""
        return name.lower().replace(" fc", "").replace(" united", "").replace(" national football team", "").replace(" men's", "").strip()

    def cast_vote(self, market, home, away):
        """Casts a +1 Vote for a specific match market."""
        match_name = f"{self.normalize_name(home).title()} vs {self.normalize_name(away).title()}"
        target_dict = self.btts_votes if market == "btts" else self.over25_votes
        
        matched_key = None
        for existing_match in target_dict.keys():
            if SequenceMatcher(None, match_name.lower(), existing_match.lower()).ratio() > 0.65:
                matched_key = existing_match
                break
                
        if matched_key:
            target_dict[matched_key] += 1
        else:
            target_dict[match_name] += 1

    def scrape_forebet(self):
        print("📡 Voter 1: Asking Forebet...")
        try:
            r = self.session.get("https://www.forebet.com/en/football-predictions/under-over-25-goals", timeout=15)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                for row in soup.find_all('div', class_=['tr_0', 'tr_1']):
                    home, away, predict = row.find('span', class_='homeTeam'), row.find('span', class_='awayTeam'), row.find('div', class_='predict')
                    if home and away and predict and "over" in predict.text.lower():
                        self.cast_vote("over", home.text, away.text)
                        
            r2 = self.session.get("https://www.forebet.com/en/football-predictions/both-to-score", timeout=15)
            if r2.status_code == 200:
                soup = BeautifulSoup(r2.text, 'html.parser')
                for row in soup.find_all('div', class_=['tr_0', 'tr_1']):
                    home, away, predict = row.find('span', class_='homeTeam'), row.find('span', class_='awayTeam'), row.find('div', class_='predict')
                    if home and away and predict and "yes" in predict.text.lower():
                        self.cast_vote("btts", home.text, away.text)
        except Exception as e:
            print(f"Forebet Error: {e}")

    def scrape_predictz(self):
        print("📡 Voter 2: Asking PredictZ...")
        try:
            r = self.session.get("https://www.predictz.com/predictions/over-under-2-5/", timeout=15)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                for div in soup.find_all('div', class_='pttr'):
                    teams, pred = div.find('div', class_='ptcteams'), div.find('div', class_='ptcpred')
                    if teams and pred and "over" in pred.text.lower():
                        parts = teams.text.split(' v ')
                        if len(parts) == 2:
                            self.cast_vote("over", parts[0], parts[1])
                            
            r2 = self.session.get("https://www.predictz.com/predictions/btts/", timeout=15)
            if r2.status_code == 200:
                soup = BeautifulSoup(r2.text, 'html.parser')
                for div in soup.find_all('div', class_='pttr'):
                    teams, pred = div.find('div', class_='ptcteams'), div.find('div', class_='ptcpred')
                    if teams and pred and "yes" in pred.text.lower():
                        parts = teams.text.split(' v ')
                        if len(parts) == 2:
                            self.cast_vote("btts", parts[0], parts[1])
        except Exception as e:
            print(f"PredictZ Error: {e}")

    def fetch_odds_api(self):
        print("📡 Voter 3: Asking the Smart Money (Global Odds API)...")
        if not ODDS_API_KEY: return
        target_leagues = ["soccer_fifa_world_cup", "soccer_brazil_campeonato", "soccer_brazil_serie_b", "soccer_usa_mls", "soccer_japan_j_league"]
        for league in target_leagues:
            try:
                url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/?apiKey={ODDS_API_KEY}&regions=eu&markets=totals,btts"
                r = requests.get(url, timeout=10)
                if r.status_code == 200:
                    for match in r.json():
                        home, away = match.get("home_team"), match.get("away_team")
                        over_prices, btts_prices = [], []
                        for bookie in match.get("bookmakers", []):
                            for mkt in bookie.get("markets", []):
                                if mkt.get("key") == "totals":
                                    for outcome in mkt.get("outcomes", []):
                                        if outcome.get("name") == "Over" and outcome.get("point") == 2.5: over_prices.append(float(outcome.get("price")))
                                elif mkt.get("key") == "btts":
                                    for outcome in mkt.get("outcomes", []):
                                        if outcome.get("name") == "Yes": btts_prices.append(float(outcome.get("price")))
                        
                        # If the global bookies price it under 1.75, the API casts a vote
                        if over_prices and (sum(over_prices)/len(over_prices)) <= 1.75:
                            self.cast_vote("over", home, away)
                        if btts_prices and (sum(btts_prices)/len(btts_prices)) <= 1.80:
                            self.cast_vote("btts", home, away)
            except Exception as e:
                print(f"API Error: {e}")

    def process_matrix(self):
        print("🚀 Launching V6 Ensemble Voting Engine...")
        self.scrape_forebet()
        self.scrape_predictz()
        self.fetch_odds_api()
        
    def dispatch_alerts(self):
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
            
        msg = "🎯 **MATRIX V6: ENSEMBLE VOTING ENGINE** 🎯\n\n"
        
        # We only need 2 out of 3 votes to publish the lock!
        over_locks = [m for m, votes in self.over25_votes.items() if votes >= 2]
        btts_locks = [m for m, votes in self.btts_votes.items() if votes >= 2]
        
        if over_locks:
            msg += "📈 **2+ VOTES SECURED: OVER 2.5 GOALS**\n"
            msg += "\n".join([f"🔥 {m}" for m in over_locks[:15]]) + "\n\n"
            
        if btts_locks:
            msg += "⚔️ **2+ VOTES SECURED: BTTS YES**\n"
            msg += "\n".join([f"🔒 {m}" for m in btts_locks[:15]]) + "\n\n"

        if not over_locks and not btts_locks:
            msg += "No 2-vote consensus found across the network today."

        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    engine = SyndicateVotingEngine()
    engine.process_matrix()
    engine.dispatch_alerts()
