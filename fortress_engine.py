import os
import time
import asyncio
import datetime
import requests
from bs4 import BeautifulSoup
import concurrent.futures
from curl_cffi import requests as tls_requests
import google.generativeai as genai

# ==============================================================================
# 1. CONFIGURATION & SECURITY
# ==============================================================================
TELEGRAM_TOKEN = "8970975457:AAEoqpJzuBIrYz672f71FvCWC3sEzLacRik"
TELEGRAM_CHAT_ID = "5876539862"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

print("--- SYSTEM DIAGNOSTICS ---")
print(f"Bot Token Loaded: {'YES' if TELEGRAM_TOKEN else 'NO'}")
print(f"Chat ID Loaded: {'YES' if TELEGRAM_CHAT_ID else 'NO'}")
print(f"Gemini API Key Loaded: {'YES' if GEMINI_API_KEY else 'NO'}")
print("--------------------------\n")

ACTIVE_STRATEGY = "Titan Multi-Agent Debate Engine"

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
            return "⚠️ GEMINI_API_KEY is missing from environment."

        prompt = f"""
        You are the Master Arbitrator overseeing a quantitative debate between two elite football AI models.
        I am providing you with today's Top 30 safest matches, scraped from consensus algorithms.
        
        THE DEBATE PROTOCOL (Execute this internally, do not output your reasoning):
        1. PERSONA 1 (The Value Hunter) internally reviews the list and selects matches with high probability for goal markets (Over 1.5/2.5, BTTS).
        2. PERSONA 2 (The Risk Manager) internally reviews the list and selects matches strictly for absolute mathematical safety (Double Chance 1X/X2, Under Totals).
        3. THE ARBITRATOR (You) must cross-reference both internal lists. You are only allowed to pass a match if both the Value Hunter and Risk Manager agree on a compromised, mathematically flawless market for it.
        
        STRICT RULES:
        - TARGET QUOTA: You must filter these 30 matches down to EXACTLY 8 to 10 of the absolute best matches that survive the debate. Do not provide fewer than 8 or more than 10.
        - DIVERSIFY MARKETS: Do not just output Double Chance. Find the best possible market for the surviving matches.
        - CRITICAL OUTPUT RULE: DO NOT provide any explanations, reasoning, or debate dialogue. I only want the raw final predictions.

        Scraped Input Data (Top 30):
        {raw_match_data}
        
        Format your response beautifully for Telegram. Do not abuse asterisks.
        Expected Output Layout Structure:
        ⚽ Match Name ➔ [Safest Suggested Market]
        """

        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"⚠️ LLM Analysis Failed: {str(e)}"

    def process_signals(self):
        valid_matches = []

        for match, listings in self.master_matrix.items():
            if len(listings) == 0: continue
            
            prediction_weights = {}
            for site, pick in listings:
                prediction_weights[pick] = prediction_weights.get(pick, 0) + 1

            top_pick = max(prediction_weights, key=prediction_weights.get)
            confidence_pct = (prediction_weights[top_pick] / len(listings)) * 100
            
            if confidence_pct >= 66:
                valid_matches.append({
                    "match": match,
                    "pick": top_pick,
                    "confidence": confidence_pct
                })

        # Sort mathematically to find the absolute strongest 30 matches for the AI to debate
        valid_matches = sorted(valid_matches, key=lambda x: x["confidence"], reverse=True)[:30]
        
        match_summary = ""
        for v in valid_matches:
            match_summary += f"- {v['match']} | Algorithmic Pick: {v['pick']} | Consensus: {v['confidence']:.0f}%\n"

        return match_summary, len(valid_matches)

    def send_telegram_alert(self, msg):
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
            print("ERROR: Missing Telegram Tokens. Cannot send.")
            return

        print("Attempting to push message to Telegram API...")
        
        max_length = 4000
        parts = [msg[i:i+max_length] for i in range(0, len(msg), max_length)]
        
        try:
            for index, part in enumerate(parts):
                url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
                payload = {"chat_id": TELEGRAM_CHAT_ID, "text": part}
                response = requests.post(url, json=payload, timeout=10)
                
                print(f"Message Chunk {index+1}/{len(parts)} Status: {response.status_code}")
                if response.status_code != 200:
                    print(f"Telegram API Error Data: {response.text}")
                    
            print("✅ Payload successfully delivered to Telegram!")
        except Exception as e:
            print(f"Failed to send Telegram message: {e}")

    async def run_pipeline(self):
        print("Starting Scrapers...")
        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            await asyncio.gather(*[loop.run_in_executor(pool, self.fetch_and_scrape_sync, n, c) for n, c in self.configs.items()])
        
        match_summary, count = self.process_signals()
        print(f"Scrape Complete. Top {count} matches passed to Multi-Agent Debate.")
        
        if count == 0: 
            self.send_telegram_alert("🛡️ TITAN LLM ENGINE: Scrape finalized. Zero high-consensus matches detected today. Capital preserved.")
            return
        
        print("Executing Multi-Agent LLM Debate...")
        llm_formatted_message = self.analyze_with_llm(match_summary)
        
        final_msg = f"🧠 **TITAN MULTI-AGENT DEBATE ENGINE** 🧠\n\n{llm_formatted_message}\n\n📊 Strategy: {ACTIVE_STRATEGY}"
        self.send_telegram_alert(final_msg)

if __name__ == "__main__":
    live_configs = get_dynamic_configs()
    asyncio.run(TitanMasterEngine(live_configs).run_pipeline())
