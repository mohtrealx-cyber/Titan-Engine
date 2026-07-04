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
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

print("--- SYSTEM DIAGNOSTICS ---")
print(f"Bot Token Loaded: {'YES' if TELEGRAM_TOKEN else 'NO'}")
print(f"Chat ID Loaded: {'YES' if TELEGRAM_CHAT_ID else 'NO'}")
print(f"Gemini API Key Loaded: {'YES' if GEMINI_API_KEY else 'NO'}")
print(f"Groq API Key Loaded: {'YES' if GROQ_API_KEY else 'NO'}")
print("--------------------------\n")

ACTIVE_STRATEGY = "Cross-Model Consensus (Gemini vs Llama 3)"

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

    def ask_gemini(self, data):
        """Generates Model A's independent picks."""
        prompt = f"Analyze these football matches. Pick the 10 absolute safest matches to bet on, prioritizing Over/Under, BTTS, or Double Chance. Format exactly as 'Match Name - Market'. No other text.\n\nData:\n{data}"
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            return model.generate_content(prompt).text
        except Exception as e:
            return ""

    def ask_llama3(self, data):
        """Generates Model B's independent picks via Groq API."""
        if not GROQ_API_KEY: return ""
        prompt = f"Analyze these football matches. Pick the 10 absolute safest matches to bet on, prioritizing Over/Under, BTTS, or Double Chance. Format exactly as 'Match Name - Market'. No other text.\n\nData:\n{data}"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": "llama3-70b-8192",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2
        }
        try:
            r = requests.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=15)
            return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return ""

    def execute_consensus_arbitrator(self, list_a, list_b):
        """Forces the final intersection of both AI models."""
        prompt = f"""
        You are the Final Arbitrator. I am giving you two lists of betting predictions generated by two independent AI models.
        
        List A (Gemini):
        {list_a}
        
        List B (Llama 3):
        {list_b}
        
        YOUR INSTRUCTIONS:
        1. Compare the lists. Extract ONLY the matches that appear on BOTH lists where they agree on the general market direction.
        2. If they disagree on a match, discard it immediately.
        3. Format the surviving consensus matches beautifully for Telegram. Use clear emojis.
        4. CRITICAL: Provide ZERO explanations or intro text. Just the final agreed raw predictions.
        
        Format:
        ⚽ Match Name ➔ [Agreed Market]
        """
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            return model.generate_content(prompt).text
        except Exception as e:
            return "⚠️ Arbitrator Engine Failed."

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
                valid_matches.append({"match": match, "pick": top_pick, "confidence": confidence_pct})

        valid_matches = sorted(valid_matches, key=lambda x: x["confidence"], reverse=True)[:30]
        match_summary = ""
        for v in valid_matches:
            match_summary += f"- {v['match']} | Consensus: {v['pick']}\n"
        return match_summary, len(valid_matches)

    def send_telegram_alert(self, msg):
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
        print("Attempting to push message to Telegram API...")
        try:
            for index, part in enumerate([msg[i:i+4000] for i in range(0, len(msg), 4000)]):
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": TELEGRAM_CHAT_ID, "text": part}, timeout=10)
        except Exception as e:
            print(f"Failed to send Telegram message: {e}")

    async def run_pipeline(self):
        print("Starting Scrapers...")
        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            await asyncio.gather(*[loop.run_in_executor(pool, self.fetch_and_scrape_sync, n, c) for n, c in self.configs.items()])
        
        match_summary, count = self.process_signals()
        if count == 0: 
            self.send_telegram_alert("🛡️ TITAN: Scrape finalized. Zero matches detected.")
            return
            
        print("Model A (Gemini) processing...")
        gemini_picks = self.ask_gemini(match_summary)
        
        print("Model B (Llama 3) processing...")
        llama_picks = self.ask_llama3(match_summary)
        
        print("Executing Final Arbitrator Protocol...")
        final_ticket = self.execute_consensus_arbitrator(gemini_picks, llama_picks)
        
        final_msg = f"🧠 **TITAN CROSS-MODEL CONSENSUS ENGINE** 🧠\n\n{final_ticket}\n\n📊 Strategy: {ACTIVE_STRATEGY}"
        self.send_telegram_alert(final_msg)

if __name__ == "__main__":
    live_configs = get_dynamic_configs()
    asyncio.run(TitanMasterEngine(live_configs).run_pipeline())
