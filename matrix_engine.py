import os
import requests
from bs4 import BeautifulSoup
from difflib import SequenceMatcher

# ==============================================================================
# MATRIX V2: DIAGNOSTIC CONSENSUS ENGINE
# ==============================================================================
TELEGRAM_TOKEN = os.environ.get("MATRIX_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("MATRIX_TELEGRAM_CHAT_ID")

class AlternativeMarketMatrix:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5"
        }
        self.btts_consensus = []
        self.over_25_consensus = []

    def is_match(self, team_a, team_b):
        return SequenceMatcher(None, team_a.lower(), team_b.lower()).ratio() > 0.65

    def scrape_forebet(self, market):
        predictions = []
        url = "https://www.forebet.com/en/football-predictions/both-to-score" if market == "btts" else "https://www.forebet.com/en/football-predictions/under-over-25-goals"
        
        try:
            r = requests.get(url, headers=self.headers, timeout=15)
            print(f"📡 Forebet HTTP Status Code ({market}): {r.status_code}")
            
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                rows = soup.find_all('div', class_=['tr_0', 'tr_1'])
                print(f"📊 Forebet raw rows detected: {len(rows)}")
                
                for row in rows:
                    home = row.find('span', class_='homeTeam')
                    away = row.find('span', class_='awayTeam')
                    predict_box = row.find('div', class_='predict')
                    
                    if home and away and predict_box:
                        home_name = home.text.strip()
                        away_name = away.text.strip()
                        prediction = predict_box.text.strip()
                        
                        if market == "btts" and "yes" in prediction.lower():
                            predictions.append(f"{home_name} vs {away_name}")
                        elif market == "over" and "over" in prediction.lower():
                            predictions.append(f"{home_name} vs {away_name}")
        except Exception as e:
            print(f"❌ Forebet Scrape Error: {e}")
            
        print(f"✅ Forebet extracted {len(predictions)} matches for {market}")
        return predictions

    def scrape_predictz(self, market):
        predictions = []
        url = "https://www.predictz.com/predictions/btts/" if market == "btts" else "https://www.predictz.com/predictions/over-under-2-5/"
        
        try:
            r = requests.get(url, headers=self.headers, timeout=15)
            print(f"📡 PredictZ HTTP Status Code ({market}): {r.status_code}")
            
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                divs = soup.find_all('div', class_='pttr')
                print(f"📊 PredictZ raw elements detected: {len(divs)}")
                
                for div in divs:
                    teams = div.find('div', class_='ptcteams')
                    pred_div = div.find('div', class_='ptcpred')
                    
                    if teams and pred_div:
                        match_string = teams.text.strip()
                        prediction = pred_div.text.strip()
                        
                        if market == "btts" and "yes" in prediction.lower():
                            predictions.append(match_string.replace(" v ", " vs "))
                        elif market == "over" and "over" in prediction.lower():
                            predictions.append(match_string.replace(" v ", " vs "))
        except Exception as e:
            print(f"❌ PredictZ Scrape Error: {e}")
            
        print(f"✅ PredictZ extracted {len(predictions)} matches for {market}")
        return predictions

    def process_matrix(self):
        print("🚀 Starting Matrix Deep Scan...")
        
        forebet_btts = self.scrape_forebet("btts")
        predictz_btts = self.scrape_predictz("btts")
        
        for fb_match in forebet_btts:
            for pz_match in predictz_btts:
                if self.is_match(fb_match, pz_match):
                    self.btts_consensus.append(f"⚔️ {fb_match} ➔ BTTS: Yes")
                    break

        forebet_over = self.scrape_forebet("over")
        predictz_over = self.scrape_predictz("over")
        
        for fb_match in forebet_over:
            for pz_match in predictz_over:
                if self.is_match(fb_match, pz_match):
                    self.over_25_consensus.append(f"🔥 {fb_match} ➔ Over 2.5 Goals")
                    break
        
        print(f"📉 Final Matched Consensus - Over 2.5: {len(self.over_25_consensus)} | BTTS: {len(self.btts_consensus)}")

    def dispatch_alerts(self):
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: 
            return
            
        msg = "🎯 **MATRIX V2: CONSENSUS AGGREGATOR** 🎯\n\n"
        
        if self.over_25_consensus:
            msg += "📈 **FOREBET + PREDICTZ: OVER 2.5 GOALS**\n"
            msg += "\n".join(list(set(self.over_25_consensus))[:10]) + "\n\n"
            
        if self.btts_consensus:
            msg += "⚔️ **FOREBET + PREDICTZ: BTTS: YES**\n"
            msg += "\n".join(list(set(self.btts_consensus))[:10]) + "\n\n"

        if msg == "🎯 **MATRIX V2: CONSENSUS AGGREGATOR** 🎯\n\n":
            msg += "No consensus found across hubs for alternative markets today."

        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    engine = AlternativeMarketMatrix()
    engine.process_matrix()
    engine.dispatch_alerts()
