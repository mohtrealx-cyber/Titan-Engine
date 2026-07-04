import os
import time
import asyncio
import datetime
import requests # Brought in standard requests for Telegram
from bs4 import BeautifulSoup
import concurrent.futures
from curl_cffi import requests as tls_requests
import google.generativeai as genai

# ==============================================================================
# 1. CONFIGURATION & SECURITY
# ==============================================================================
# Hardcoded to guarantee delivery
TELEGRAM_TOKEN = "8970975457:AAEoqpJzuBIrYz672f71FvCWC3sEzLacRik"
TELEGRAM_CHAT_ID = "5876539862"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

ACTIVE_STRATEGY = "Titan LLM Reasoning"

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def get_dynamic_configs():
    today_date = datetime.datetime.now().strftime('%Y-%m-%d')
    cb = int(time.time()) 
    
    return {
        "Statarea": {"url": f"https://www.statarea.com/predictions/date/{today_date}/", "row_selector": "div", "row_class": "matchrow", "home_selector": "div", "home_class": "name", "home_index": 0, "away_selector": "div", "away_class": "name", "away_index": 1, "pick_selector": "div", "pick_class": "type1", "pick_index": 0},
        "PredictZ": {"url": f"https://www.predictz.com/predictions/today/?cb={cb}", "row_selector": "div", "row_class": "pttr", "home_selector": "div", "home_class": "pttmobh", "home_index": 0, "away_selector": "div", "away_class": "pttmoba", "away_index": 0, "pick_selector": "div", "pick_class": "ptoddsdesc", "pick_index": 0},
        "Vitibet": {"url": f"https://www.vitibet.com/index.php?clanek=quicktips&sekce=fotbal&lang=en&cb={cb}", "row_selector": "a", "row_class": "livescore-match-row", "home_selector": "span", "home_class": "livescore-team-name", "home_index": 0, "away_selector": "span", "away_class": "livescore-team-name", "away_index": 1, "pick_selector": "span", "pick_class": "tip-indicator-circle", "pick_index": 0}
    }

class TitanMasterEngine:
    def __init__(self, configs):
        self.configs = configs
        self.master_matrix = {}

    def normalize_prediction(self, raw_text):
        text = str(raw_text).strip().lower()
        matrix = {"1": ["1", "home", "home win"], "X": ["x", "draw"], "2": ["2", "away", "away win"], "OVER 1.5": ["o1.5", "over 1.5", "+1.5"], "OVER 2.5": ["o2.5", "over 2.5", "+2.5"], "UNDER 2.5": ["u2.5", "under 2.5", "-2.5"], "GG": ["gg", "btts", "yes"]}
        for tag, vars in matrix.items():
            if text in vars: return tag
        return None

    def clean_team_name(self, name): 
        return name.strip().title()

    def log_prediction_qa(self, site_name, home, away, raw_prediction):
        if not home or not away or not raw_prediction: return
        normalized_pick = self.normalize_prediction(raw_prediction)
        if not normalized_pick: return
        match_key = f"{self.clean_team_name(home)} vs {self.clean_team_name(away)}"
        if match_key not in self.master_matrix: self.master_matrix[match_key] = []
        self.master_matrix[match_key].append((site_name, normalized_pick))

    def fetch_and_scrape_sync(self, site_name, cfg):
        try:
            r = tls_requests.get(cfg["url"], impersonate="chrome120", timeout=20)
            if r.status_code != 200: return
            for row in BeautifulSoup(r.content, 'html.parser').find_all(cfg["row_selector"], class_=cfg["row_class"]):
                try: 
                    self.log_prediction_qa(
                        site_name, 
                        row.find_all(cfg["home_selector"], class_=cfg["home_class"])[cfg["home_index"]].text, 
                        row.find_all(cfg["away_selector"], class_=cfg["away_class"])[cfg["away_index"]].text, 
                        row.find_all(cfg["pick_selector"], class_=cfg["pick_class"])[cfg["pick_index"]].text
                    )
                except: continue
        except: return

    def analyze_with_llm(self, raw_match_data):
        if not GEMINI_API_KEY:
            return "⚠️ GEMINI_API_KEY is missing from environment. Cannot execute reasoning layer."

        prompt = f"""
        You are an elite football quantitative analyst specializing in risk mitigation.
        I am providing you with today's matches and consensus predictions from 3 automated scraping pipelines.
        
        Your instructions:
        1. Evaluate each fixture carefully.
        2. IMMEDIATELY REMOVE/DROP any highly volatile, risky, or unstable trap games.
        3. For the remaining matches, determine the ABSOLUTE SAFEST betting market option. Do not restrict yourself to standard 1X2. Safely expand the prediction to alternative markets: 'Over 1.5 Goals', 'Under 3.5 Goals', 'BTTS (GG/NO)', or 'Double Chance (1X/X2)' if it severely lowers risk.
        4. Provide a quick 1-sentence analytical reason for each decision.
        
        Scraped Input Data:
        {raw_match_data}
        
        Format your response beautifully for Telegram as a 'MEGA-TICKET'. Use crisp formatting and clear emojis. Do not abuse asterisks or complex headings.
        Expected Output Layout Structure:
        ⚽ Match Name ➔ [Safest Suggested Market]
        ↳ Reason: Short, grounded analysis sentence.
        """

        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"⚠️ LLM Analysis Failed: {str(e)}"

    def process_signals(self):
        match_summary = ""
        valid_matches_found = 0

        for match, listings in self.master_matrix.items():
            if len(listings) == 0: continue
            
            prediction_weights = {}
            for site, pick in listings:
                prediction_weights[pick] = prediction_weights.get(pick, 0) + 1

            top_pick = max(prediction_weights, key=prediction_weights.get)
            confidence_pct = (prediction_weights[top_pick] / len(listings)) * 100
            
            if confidence_pct >= 66:
                match_summary += f"- {match} | Algorithmic Picks: {top_pick} | Consensus: {confidence_pct:.0f}%\n"
                valid_matches_found += 1

        return match_summary, valid_matches_found

    def send_telegram_alert(self, msg):
        try:
            # Using standard requests to guarantee Telegram delivery
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"Failed to send Telegram message: {e}")

    async def run_pipeline(self):
        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            await asyncio.gather(*[loop.run_in_executor(pool, self.fetch_and_scrape_sync, n, c) for n, c in self.configs.items()])
        
        match_summary, count = self.process_signals()
        
        if count == 0: 
            self.send_telegram_alert("🛡️ TITAN LLM ENGINE: Scrape finalized. Zero high-consensus matches detected today. Capital preserved.")
            return
        
        llm_formatted_message = self.analyze_with_llm(match_summary)
        
        final_msg = f"🧠 **TITAN REASONING ENGINE AUTOMATOR** 🧠\n\n{llm_formatted_message}\n\n📊 Engine Strategy: {ACTIVE_STRATEGY}"
        self.send_telegram_alert(final_msg)

if __name__ == "__main__":
    live_configs = get_dynamic_configs()
    asyncio.run(TitanMasterEngine(live_configs).run_pipeline())
