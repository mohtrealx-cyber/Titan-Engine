import os
from curl_cffi import requests
from bs4 import BeautifulSoup
from difflib import SequenceMatcher
from collections import defaultdict

# ==============================================================================
# MATRIX V5: STEALTH MULTI-HUB CONSENSUS
# ==============================================================================
TELEGRAM_TOKEN = os.environ.get("MATRIX_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("MATRIX_TELEGRAM_CHAT_ID")

class ConsensusScraper:
    def __init__(self):
        # Chrome impersonation smashes through Cloudflare's 403 blocks
        self.session = requests.Session(impersonate="chrome")
        
        # Dictionaries to track how many sites predict the exact same match
        self.btts_counts = defaultdict(int)
        self.over25_counts = defaultdict(int)
        
    def normalize_name(self, name):
        """Strips out words that cause mismatching between sites."""
        return name.lower().replace(" fc", "").replace(" united", "").replace(" city", "").strip()

    def add_prediction(self, market, home, away):
        """Cross-references the match and adds a +1 to the consensus counter."""
        match_name = f"{self.normalize_name(home)} vs {self.normalize_name(away)}"
        target_dict = self.btts_counts if market == "btts" else self.over25_counts
        
        # Fuzzy matching ensures different spellings count as the exact same match
        matched_key = None
        for existing_match in target_dict.keys():
            if SequenceMatcher(None, match_name, existing_match).ratio() > 0.70:
                matched_key = existing_match
                break
                
        if matched_key:
            target_dict[matched_key] += 1
        else:
            target_dict[match_name] += 1

    def scrape_forebet(self):
        print("📡 Scraping Forebet with Stealth Browser...")
        try:
            # BTTS Market
            r = self.session.get("https://www.forebet.com/en/football-predictions/both-to-score", timeout=15)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                for row in soup.find_all('div', class_=['tr_0', 'tr_1']):
                    home = row.find('span', class_='homeTeam')
                    away = row.find('span', class_='awayTeam')
                    predict = row.find('div', class_='predict')
                    if home and away and predict and "yes" in predict.text.lower():
                        self.add_prediction("btts", home.text, away.text)
                        
            # Over 2.5 Market
            r2 = self.session.get("https://www.forebet.com/en/football-predictions/under-over-25-goals", timeout=15)
            if r2.status_code == 200:
                soup = BeautifulSoup(r2.text, 'html.parser')
                for row in soup.find_all('div', class_=['tr_0', 'tr_1']):
                    home = row.find('span', class_='homeTeam')
                    away = row.find('span', class_='awayTeam')
                    predict = row.find('div', class_='predict')
                    if home and away and predict and "over" in predict.text.lower():
                        self.add_prediction("over", home.text, away.text)
        except Exception as e:
            print(f"❌ Forebet Scrape Error: {e}")

    def scrape_predictz(self):
        print("📡 Scraping PredictZ with Stealth Browser...")
        try:
            # BTTS Market
            r = self.session.get("https://www.predictz.com/predictions/btts/", timeout=15)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                for div in soup.find_all('div', class_='pttr'):
                    teams = div.find('div', class_='ptcteams')
                    pred = div.find('div', class_='ptcpred')
                    if teams and pred and "yes" in pred.text.lower():
                        parts = teams.text.split(' v ')
                        if len(parts) == 2:
                            self.add_prediction("btts", parts[0], parts[1])
                            
            # Over 2.5 Market
            r2 = self.session.get("https://www.predictz.com/predictions/over-under-2-5/", timeout=15)
            if r2.status_code == 200:
                soup = BeautifulSoup(r2.text, 'html.parser')
                for div in soup.find_all('div', class_='pttr'):
                    teams = div.find('div', class_='ptcteams')
                    pred = div.find('div', class_='ptcpred')
                    if teams and pred and "over" in pred.text.lower():
                        parts = teams.text.split(' v ')
                        if len(parts) == 2:
                            self.add_prediction("over", parts[0], parts[1])
        except Exception as e:
            print(f"❌ PredictZ Scrape Error: {e}")

    def process_matrix(self):
        print("🚀 Launching Multi-Hub Scraper...")
        self.scrape_forebet()
        self.scrape_predictz()
        
    def dispatch_alerts(self):
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
            return
            
        msg = "🎯 **MATRIX V5: MULTI-HUB CONSENSUS** 🎯\n\n"
        
        # Extract matches that appeared on BOTH sites (Count >= 2)
        btts_locks = [match.title() for match, count in self.btts_counts.items() if count >= 2]
        over_locks = [match.title() for match, count in self.over25_counts.items() if count >= 2]
        
        if over_locks:
            msg += "📈 **2/2 SITES AGREE: OVER 2.5 GOALS**\n"
            msg += "\n".join([f"🔥 {m}" for m in over_locks[:15]]) + "\n\n"
            
        if btts_locks:
            msg += "⚔️ **2/2 SITES AGREE: BTTS YES**\n"
            msg += "\n".join([f"🔒 {m}" for m in btts_locks[:15]]) + "\n\n"

        if not over_locks and not btts_locks:
            msg += "No 2-site consensus found for alternative markets today."

        # Send payload to Telegram using standard requests
        import requests as standard_requests
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        standard_requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    engine = ConsensusScraper()
    engine.process_matrix()
    engine.dispatch_alerts()
