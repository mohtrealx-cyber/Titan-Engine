import os
import requests
from bs4 import BeautifulSoup
from difflib import SequenceMatcher

# ==============================================================================
# 1. MATRIX V2 CONFIGURATION (ALTERNATIVE MARKET AGGREGATOR)
# ==============================================================================
TELEGRAM_TOKEN = os.environ.get("MATRIX_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("MATRIX_TELEGRAM_CHAT_ID")

class AlternativeMarketMatrix:
    def __init__(self):
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        self.btts_consensus = []
        self.over_25_consensus = []
        self.double_chance_consensus = []

    def is_match(self, team_a, team_b):
        """Cross-references team names between different website formats."""
        return SequenceMatcher(None, team_a.lower(), team_b.lower()).ratio() > 0.70

    def scrape_prediction_hub(self, market_type):
        """
        Placeholder parser. In a live environment, this requests the specific 
        HTML tables from the selected prediction websites for the targeted market.
        """
        predictions = []
        # Example structural layout for scraping:
        # url = "https://www.example-prediction-site.com/btts-tips"
        # response = requests.get(url, headers=self.headers)
        # soup = BeautifulSoup(response.text, 'html.parser')
        # for row in soup.find_all('tr', class_='prediction-row'):
        #     predictions.append("Home Team vs Away Team")
        return predictions

    def process_matrix(self):
        print("Scraping Prediction Hubs for Alternative Markets...")
        
        # 1. Fetch raw lists from Hub A and Hub B for BTTS
        hub_a_btts = self.scrape_prediction_hub("btts")
        hub_b_btts = self.scrape_prediction_hub("btts")
        
        # Find Consensus: Matches that appear on both sites for BTTS
        for match_a in hub_a_btts:
            for match_b in hub_b_btts:
                if self.is_match(match_a, match_b):
                    self.btts_consensus.append(f"⚔️ {match_a} ➔ BTTS: Yes")
                    break

        # 2. Fetch raw lists from Hub A and Hub B for Over 2.5
        hub_a_over = self.scrape_prediction_hub("over_2_5")
        hub_b_over = self.scrape_prediction_hub("over_2_5")
        
        # Find Consensus: Matches that appear on both sites for Over 2.5
        for match_a in hub_a_over:
            for match_b in hub_b_over:
                if self.is_match(match_a, match_b):
                    self.over_25_consensus.append(f"🔥 {match_a} ➔ Over 2.5 Goals")
                    break

        # 3. Double Chance (1X / X2) Logic can be added here following the same structure

    def dispatch_alerts(self):
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: 
            return
            
        msg = "🎯 **ALTERNATIVE MARKET MATRIX** 🎯\n\n"
        
        if self.over_25_consensus:
            msg += "📈 **CONSENSUS OVER 2.5 GOALS**\n"
            msg += "\n".join(set(self.over_25_consensus[:8])) + "\n\n"
            
        if self.btts_consensus:
            msg += "⚔️ **CONSENSUS BTTS: YES**\n"
            msg += "\n".join(set(self.btts_consensus[:8])) + "\n\n"
            
        if self.double_chance_consensus:
            msg += "🛡️ **CONSENSUS DOUBLE CHANCE (1X/X2)**\n"
            msg += "\n".join(set(self.double_chance_consensus[:8])) + "\n\n"

        if msg == "🎯 **ALTERNATIVE MARKET MATRIX** 🎯\n\n":
            msg += "No consensus found across hubs for alternative markets today."

        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    engine = AlternativeMarketMatrix()
    engine.process_matrix()
    engine.dispatch_alerts()
