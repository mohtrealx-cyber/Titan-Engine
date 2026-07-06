import os
import time
import asyncio
import datetime
import requests
import difflib
from bs4 import BeautifulSoup
import concurrent.futures
from curl_cffi import requests as tls_requests
from google import genai 
from google.genai import types, errors

# ==============================================================================
# 1. CONFIGURATION & SECURITY
# ==============================================================================
TELEGRAM_TOKEN = "8970975457:AAEoqpJzuBIrYz672f71FvCWC3sEzLacRik"
TELEGRAM_CHAT_ID = "5876539862"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

print("--- SYSTEM DIAGNOSTICS ---")
print(f"Bot Token Loaded: {'YES' if TELEGRAM_TOKEN else 'NO'}")
print(f"Chat ID Loaded: {'YES' if TELEGRAM_CHAT_ID else 'NO'}")
print(f"Gemini API Key Loaded: {'YES' if GEMINI_API_KEY else 'NO'}")
print(f"Groq API Key Loaded: {'YES' if GROQ_API_KEY else 'NO'}")
print(f"Odds API Key Loaded: {'YES' if ODDS_API_KEY else 'NO'}")
print("--------------------------\n")

ACTIVE_STRATEGY = "Titan Apex: Debate + Proportional EV Micro-Staking (39 KES/Day)"

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
        
        # FIX: Force the client to use v1alpha to bypass the 404 v1beta missing model error
        if GEMINI_API_KEY:
            try:
                self.gemini_client = genai.Client(
                    api_key=GEMINI_API_KEY,
                    http_options=types.HttpOptions(api_version='v1alpha')
                )
            except Exception as e:
                print(f"⚠️ [System] Falling back to standard client init: {e}")
                self.gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        else:
            self.gemini_client = None

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
        
        raw_match_key = f"{self.clean_team_name(home)} vs {self.clean_team_name(away)}"
        final_key = raw_match_key

        for existing_key in self.master_matrix.keys():
            similarity = difflib.SequenceMatcher(None, raw_match_key.lower(), existing_key.lower()).ratio()
            if similarity >= 0.75:  
                final_key = existing_key
                break

        if final_key not in self.master_matrix: self.master_matrix[final_key] = []
        
        existing_sites = [entry[0] for entry in self.master_matrix[final_key]]
        if site_name not in existing_sites:
            self.master_matrix[final_key].append((site_name, normalized_pick))

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

    def safe_gemini_call(self, prompt, max_retries=3):
        """Wraps Gemini calls with an auto-switching model fallback to bypass 404 errors."""
        if not self.gemini_client: return "⚠️ Gemini API Key missing."
        
        # List of known valid models. The script will try them in order until one works.
        models_to_try = [
            'gemini-2.5-flash', 
            'gemini-2.0-flash', 
            'gemini-1.5-flash-latest', 
            'gemini-1.5-flash', 
            'gemini-pro'
        ]
        
        for model_name in models_to_try:
            for attempt in range(max_retries):
                try:
                    print(f"   [Gemini] Attempting {model_name} (Try {attempt + 1}/{max_retries})...")
                    response = self.gemini_client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.4,
                            safety_settings=[
                                types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH),
                                types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH),
                                types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH),
                                types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH)
                            ]
                        )
                    )
                    
                    if response and response.text:
                        return response.text.strip()
                    else:
                        finish_reason = "Unknown"
                        if response and response.candidates:
                            finish_reason = response.candidates[0].finish_reason
                        print(f"   ⚠️ [Gemini] Blank response. Finish reason: {finish_reason}. Retrying...")
                        time.sleep(10)
                        continue
                        
                except Exception as e:
                    error_msg = str(e).lower()
                    if "404" in error_msg or "not found" in error_msg:
                        print(f"   ⚠️ [Gemini] Model '{model_name}' not found for this API key. Switching to next model...")
                        break # Breaks the retry loop, moves to the next model in 'models_to_try'
                    elif "429" in error_msg or "resource_exhausted" in error_msg or "quota" in error_msg:
                        print(f"   ⚠️ [Gemini] Rate Limit or Quota hit! Sleeping 45s... Details: {e}")
                        time.sleep(45)
                        continue
                    else:
                        print(f"   ⚠️ [Gemini] Unexpected Exception: {e}")
                        return f"⚠️ API Error: {str(e)}"
                        
        return "⚠️ Arbitrator Error: All fallback models failed or max retries exceeded."

    def gemini_opening_statement(self, data):
        prompt = f"""You are a sports statistical analyst. Review these upcoming football fixtures. 
        STRICT RULES:
        1. YOU MUST ONLY analyze matches from the Data list provided below. DO NOT invent or guess matches.
        2. DO NOT predict simple outright winners (Home/Away). 
        3. Identify matches with high statistical probability for alternative outcomes: Over/Under Goals, BTTS (Yes/No), or Double Chance (1X/X2).
        Select your top 10 matches. Provide a 1-sentence statistical reason for your selection.
        
        Data:\n{data}"""
        return self.safe_gemini_call(prompt)

    def llama3_rebuttal(self, data, gemini_proposal):
        if not GROQ_API_KEY: return "⚠️ Groq API Key missing."
        prompt = f"""You are a strict data validator. Your colleague just proposed statistical forecasts. 
        Read their proposal. Critically evaluate any forecast that has high mathematical variance. 
        STRICT RULES:
        1. YOU MUST ONLY select matches from the Original Data list provided below. DO NOT invent matches.
        2. If they picked a straight outright winner (1 or 2), REJECT IT IMMEDIATELY. 
        3. Force the final selections into safer statistical models (Double Chance, Over/Under, BTTS).
        Counter-propose the absolute safest matches (up to 10). Provide a 1-sentence statistical justification.
        
        Original Data:
        {data}
        
        Colleague's Proposal:
        {gemini_proposal}
        """
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        payload = {"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": prompt}], "temperature": 0.3}
        try:
            r = requests.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=15)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
        except Exception as e: return f"⚠️ Llama 3 Error: {str(e)}"

    def final_verdict(self, gemini_proposal, llama_critique):
        prompt = f"""
        You are the Executive Arbitrator. Two highly intelligent AI agents just debated today's fixtures.
        
        Agent 1 (Statistical Analyst):
        {gemini_proposal}
        
        Agent 2 (Data Validator):
        {llama_critique}
        
        YOUR INSTRUCTIONS:
        1. Find the matches that BOTH agents agreed upon.
        2. YOU MUST NOT invent matches. Only use matches mentioned by the agents.
        3. Format these surviving matches using EXACTLY this syntax:
           Match Name | Agreed Market
           * For Double Chance markets, output ONLY the exact symbol (e.g., 1X, X2, 12). DO NOT write the words "Double Chance".
        4. CRITICAL: Provide ZERO explanations, emojis, or intro text. Just the raw text lines separated by newlines.
        """
        return self.safe_gemini_call(prompt)

    def fetch_live_odds_matrix(self):
        if not ODDS_API_KEY: return []
        print("\n🌐 Fetching Live Odds from Global Bookmakers...")
        try:
            url = f"https://api.the-odds-api.com/v4/sports/upcoming/odds/?apiKey={ODDS_API_KEY}&regions=eu&markets=h2h&bookmakers=bet365"
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                return response.json()
            return []
        except: return []

    def apply_ev_and_format(self, raw_ticket, odds_matrix, scraped_match_whitelist):
        if "⚠️" in raw_ticket: return raw_ticket
        
        DAILY_BUDGET_KES = 39
        lines = raw_ticket.split('\n')
        
        accepted_matches = []
        rejected_matches = []
        total_units = 0.0
        
        for line in lines:
            if "|" not in line: continue
            parts = line.split("|")
            match_name = parts[0].strip()
            market = parts[1].strip()

            # --- ANTI-HALLUCINATION GUARDRAIL ---
            is_real_match = False
            for real_match in scraped_match_whitelist:
                if difflib.SequenceMatcher(None, match_name.lower(), real_match.lower()).ratio() >= 0.70:
                    is_real_match = True
                    match_name = real_match 
                    break
            
            if not is_real_match:
                rejected_matches.append({"name": match_name, "reason": "Hallucinated by LLM (Not in today's scraped fixtures)"})
                continue
            
            # --- DOUBLE CHANCE FORMAT SANITIZER ---
            ml = market.lower()
            if "double chance" in ml or "dc" in ml or "1x" in ml or "x2" in ml:
                if "1x" in ml or "home or draw" in ml: market = "1X"
                elif "x2" in ml or "2x" in ml or "away or draw" in ml: market = "X2"
                elif "12" in ml or "home or away" in ml: market = "12"
            
            best_price = None
            if odds_matrix:
                for game in odds_matrix:
                    api_match_name = f"{game.get('home_team', '')} vs {game.get('away_team', '')}"
                    similarity = difflib.SequenceMatcher(None, match_name.lower(), api_match_name.lower()).ratio()
                    
                    if similarity > 0.6: 
                        try:
                            outcomes = game['bookmakers'][0]['markets'][0]['outcomes']
                            prices = [o['price'] for o in outcomes]
                            best_price = min(prices) 
                            break
                        except: pass
            
            if best_price and best_price >= 1.15:
                units = round((best_price - 1) * 2.5, 1)
                if units <= 0: units = 1.0 
                total_units += units
                accepted_matches.append({"name": match_name, "market": market, "odds": best_price, "units": units})
            elif best_price and best_price < 1.15:
                rejected_matches.append({"name": match_name, "reason": f"Odds {best_price} too low"})
            else:
                accepted_matches.append({"name": match_name, "market": market, "odds": None, "units": 1.0})
                total_units += 1.0

        final_output = ""
        kes_distributed = 0
        
        for i, match in enumerate(accepted_matches):
            if total_units > 0:
                if i == len(accepted_matches) - 1:
                    kes_alloc = DAILY_BUDGET_KES - kes_distributed
                else:
                    kes_alloc = int(round((match["units"] / total_units) * DAILY_BUDGET_KES))
                    kes_distributed += kes_alloc
            else:
                kes_alloc = 0

            odds_display = f"Estimated Odds: {match['odds']}" if match['odds'] else "Live Odds Pending"
            final_output += f"⚽ **{match['name']}**\n   ➔ {match['market']}\n   📊 {odds_display} | 💰 Stake: {kes_alloc} KES\n\n"
            
        for match in rejected_matches:
            final_output += f"🗑️ ~~{match['name']}~~ *(Rejected: {match['reason']})*\n\n"
            
        if accepted_matches:
            final_output += f"========================\n"
            final_output += f"💵 **TOTAL DAILY STAKE:** {DAILY_BUDGET_KES} KES\n"
            final_output += f"========================"
            
        return final_output.strip()

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

        valid_matches = sorted(valid_matches, key=lambda x: x["confidence"], reverse=True)[:35]
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
        except Exception as e: print(f"Failed to send Telegram message: {e}")

    async def run_pipeline(self):
        print("Starting Scrapers...")
        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            await asyncio.gather(*[loop.run_in_executor(pool, self.fetch_and_scrape_sync, n, c) for n, c in self.configs.items()])
        
        match_summary, count = self.process_signals()
        if count == 0: 
            self.send_telegram_alert("🛡️ TITAN: Scrape finalized. Zero matches detected.")
            return
            
        print("\n=== STEP 1: GEMINI DRAFTS PROPOSAL ===")
        proposal = self.gemini_opening_statement(match_summary)
        if "⚠️" in proposal: 
            return self.send_telegram_alert(f"🚨 **TITAN API FAULT** 🚨\nAgent 1 Failed:\n{proposal}")
        
        print("\n=== STEP 2: LLAMA 3 READS & CRITIQUES ===")
        rebuttal = self.llama3_rebuttal(match_summary, proposal)
        if "⚠️" in rebuttal: 
            return self.send_telegram_alert(f"🚨 **TITAN API FAULT** 🚨\nAgent 2 Failed:\n{rebuttal}")
        
        print("\n⏳ Initiating 65-second cooldown to completely reset Google API RPM limit...")
        time.sleep(65)
        
        print("\n=== STEP 3: ARBITRATOR EXTRACTS CONSENSUS ===")
        raw_ticket = self.final_verdict(proposal, rebuttal)
        if "⚠️" in raw_ticket: 
            return self.send_telegram_alert(f"🚨 **TITAN API FAULT** 🚨\nArbitrator Failed:\n{raw_ticket}")
        
        print("\n=== STEP 4: APPLYING EXPECTED VALUE (EV) FILTER ===")
        odds_matrix = self.fetch_live_odds_matrix()
        
        valid_scraped_match_names = list(self.master_matrix.keys())
        final_ticket = self.apply_ev_and_format(raw_ticket, odds_matrix, valid_scraped_match_names)
        
        if final_ticket.lower() == "none" or not final_ticket or "ZERO_CONSENSUS" in final_ticket:
            final_msg = f"🛡️ **TITAN SAFETY PROTOCOL ACTIVATED** 🛡️\n\nDebate collapsed or odds held zero value. Capital preserved.\n\n📊 Strategy: {ACTIVE_STRATEGY}"
        elif "⚠️" in final_ticket:
            final_msg = f"🚨 **TITAN API FAULT** 🚨\n\nFormatting failed: {final_ticket}" 
        else:
            final_msg = f"🧠 **TITAN CROSS-MODEL DEBATE ENGINE** 🧠\n\n{final_ticket}\n\n📊 Strategy: {ACTIVE_STRATEGY}"
            
        self.send_telegram_alert(final_msg)

if __name__ == "__main__":
    live_configs = get_dynamic_configs()
    asyncio.run(TitanMasterEngine(live_configs).run_pipeline())
