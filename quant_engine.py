import os
import re
import json
import time
import asyncio
import datetime
import difflib
import requests
from bs4 import BeautifulSoup
import concurrent.futures
from curl_cffi import requests as tls_requests

# ==============================================================================
# CONFIGURATION & SECURE ROUTING FALLBACKS
# ==============================================================================
TELEGRAM_TOKEN = os.environ.get("QUANT_TELEGRAM_TOKEN") or os.environ.get("TRACKER_TRACKER_TELEGRAM_TOKEN") or os.environ.get("TRACKER_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("QUANT_TELEGRAM_CHAT_ID") or os.environ.get("TRACKER_TRACKER_TELEGRAM_CHAT_ID") or os.environ.get("TRACKER_TELEGRAM_CHAT_ID")
SCRAPER_API_KEY = os.environ.get("SCRAPER_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

MEMORY_FILE = "pending_tickets.json"

def get_dynamic_configs():
    eat_time = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
    today_date = eat_time.strftime('%Y-%m-%d')
    cb = int(time.time())

    return {
        "Statarea": {
            "url": f"https://www.statarea.com/predictions/date/{today_date}/",
            "row_selector": "div", "row_class": "matchrow",
            "home_selector": "div", "home_class": "name", "home_index": 0,
            "away_selector": "div", "away_class": "name", "away_index": 1,
            "pick_selector": "div", "pick_class": "type1", "pick_index": 0,
            "use_scraperapi": True  
        },
        "Vitibet": {
            "url": f"https://www.vitibet.com/index.php?clanek=quicktips&sekce=fotbal&lang=en&cb={cb}",
            "row_selector": "a", "row_class": "livescore-match-row",
            "home_selector": "span", "home_class": "livescore-team-name", "home_index": 0,
            "away_selector": "span", "away_class": "livescore-team-name", "away_index": 1,
            "pick_selector": "span", "pick_class": "tip-indicator-circle", "pick_index": 0,
            "use_scraperapi": False
        },
        "PredictZ": {
            "url": "https://www.predictz.com/predictions/today/",
            "row_selector": "div", "row_class": "pttr",
            "home_selector": "div", "home_class": "pttmobh", "home_index": 0,
            "away_selector": "div", "away_class": "pttmoba", "away_index": 0,
            "pick_selector": "div", "pick_class": "ptoddsdesc", "pick_index": 0,
            "use_scraperapi": True
        },
        "WinDrawWin": {
            "url": "https://www.windrawwin.com/predictions/today/",
            "row_selector": "div", "row_class": "wtrow",
            "home_selector": "div", "home_class": "wttmobh", "home_index": 0,
            "away_selector": "div", "away_class": "wttmoba", "away_index": 0,
            "pick_selector": "div", "pick_class": "wtoddsdesc", "pick_index": 0,
            "use_scraperapi": True
        }
    }

class ConsensusEngine:
    def __init__(self, configs):
        self.configs = configs
        self.master_matrix = {}
        self.diagnostics = {}

    def normalize_prediction(self, raw_text):
        text = str(raw_text).strip().lower()
        if text in ["home", "home win"]: return "1"
        if text in ["draw", "x", "0"]: return "X"
        if text in ["away", "away win"]: return "2"

        if len(text) > 0:
            char = text[0]
            if char == "1" or char == "h": return "1"
            if char in ["x", "0", "d"]: return "X"
            if char == "2" or char == "a": return "2"
        return None

    def clean_team_name(self, name):
        return name.strip().title()

    def is_match_active_or_played(self, row):
        text = row.get_text(separator=" ").upper()
        padded_text = f" {text} "
        status_flags = [" FT ", " HT ", "CANC", "POSTP", "FINISHED", " LIVE ", "AET ", "PEN ", "DELAYED"]
        for flag in status_flags:
            if flag in padded_text:
                return True
        return False

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
            if cfg.get("use_scraperapi") and SCRAPER_API_KEY:
                proxy_url = f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={cfg['url']}"
                r = tls_requests.get(proxy_url, timeout=60)
            else:
                if cfg.get("use_scraperapi") and not SCRAPER_API_KEY:
                    self.diagnostics[site_name] = "🔴 MISSING SCRAPER_API_KEY"
                    return
                r = tls_requests.get(cfg["url"], impersonate="chrome120", timeout=20)

            if r.status_code != 200:
                self.diagnostics[site_name] = f"🔴 FAILED (HTTP {r.status_code})"
                return

            soup = BeautifulSoup(r.content, 'html.parser')
            
            if site_name in ["PredictZ", "WinDrawWin"]:
                row_target = re.compile(r"(pt|wt)(tr|row)")
            else:
                row_target = cfg["row_class"]
                
            rows = soup.find_all(cfg["row_selector"], class_=row_target)

            if not rows:
                self.diagnostics[site_name] = f"🟡 BLOCKED"
                return

            valid_count = 0
            skipped_count = 0

            for row in rows:
                try:
                    if self.is_match_active_or_played(row):
                        skipped_count += 1
                        continue

                    home, away, pick = None, None, None

                    if site_name in ["PredictZ", "WinDrawWin"]:
                        prefix = "pt" if site_name == "PredictZ" else "wt"
                        
                        h_elem = row.find(class_=f"{prefix}tmobh")
                        a_elem = row.find(class_=f"{prefix}tmoba")
                        p_elem = row.find(class_=re.compile(f"{prefix}oddsdesc|{prefix}mobpred"))

                        if h_elem and a_elem and p_elem:
                            home = h_elem.text
                            away = a_elem.text
                            pick = p_elem.text
                        else:
                            links = row.find_all("a")
                            if len(links) >= 2:
                                home = links[0].text
                                away = links[1].text
                                p_div = row.find(class_=re.compile(f"{prefix}prd|{prefix}pred"))
                                if p_div: pick = p_div.text
                            else:
                                for td in row.find_all("div", class_=f"{prefix}td"):
                                    norm = self.normalize_prediction(td.text)
                                    if norm:
                                        pick = norm
                                        break
                    else:
                        home = row.find_all(cfg["home_selector"], class_=cfg["home_class"])[cfg["home_index"]].text
                        away = row.find_all(cfg["away_selector"], class_=cfg["away_class"])[cfg["away_index"]].text
                        pick = row.find_all(cfg["pick_selector"], class_=cfg["pick_class"])[cfg["pick_index"]].text

                    if home and away and pick:
                        self.log_prediction_qa(site_name, home, away, pick)
                        valid_count += 1

                except Exception:
                    continue

            self.diagnostics[site_name] = f"🟢 OK ({valid_count} Upcoming | {skipped_count} Played)"

        except Exception:
            self.diagnostics[site_name] = "🔴 TIMEOUT/ERROR"
            return

    def process_consensus_signals(self):
        agreed_matches = []
        niche_matches = []
        structured_tickets = []
        ai_input_data = []

        all_scrapers = ["Statarea", "Vitibet", "PredictZ", "WinDrawWin"]
        active_scrapers_count = sum(1 for status in self.diagnostics.values() if "🟢 OK" in status)
        required_consensus = 3 if active_scrapers_count >= 4 else 2

        for match, listings in self.master_matrix.items():
            prediction_weights = {}
            sites_backing = {}
            for site, pick in listings:
                prediction_weights[pick] = prediction_weights.get(pick, 0) + 1
                if pick not in sites_backing: sites_backing[pick] = []
                sites_backing[pick].append(site)

            if not prediction_weights:
                continue

            top_pick = max(prediction_weights, key=prediction_weights.get)
            
            # --- TIER 1: CORE CONSENSUS ---
            if prediction_weights[top_pick] >= required_consensus:
                backing_sites_list = sites_backing[top_pick]
                backing_sites_str = " + ".join(backing_sites_list)

                match_text = (
                    f"• **{match}** ➔ {top_pick}\n"
                    f"  ↳ ✅ Backed by: `{backing_sites_str}`\n"
                )

                left_out_sites = [s for s in all_scrapers if s not in backing_sites_list]
                for left_out in left_out_sites:
                    other_pick = None
                    for pick, sites in sites_backing.items():
                        if pick != top_pick and left_out in sites:
                            other_pick = pick
                            break
                    
                    if other_pick:
                        match_text += f"  ↳ ⚠️ {left_out} backed: {other_pick}\n"
                    else:
                        match_text += f"  ↳ ⚪ {left_out}: Not Listed\n"

                agreed_matches.append(match_text)

                structured_tickets.append({
                    "match": match, "prediction": top_pick, "status": "PENDING", "score": "-"
                })

                ai_input_data.append({
                    "match": match, "consensus_pick": top_pick, 
                    "backed_by": backing_sites_str, "tier": "Core Consensus"
                })

            # --- TIER 2: NICHE CONSENSUS (2/2 PERFECT AGREEMENT) ---
            elif required_consensus == 3 and len(listings) == 2 and prediction_weights[top_pick] == 2:
                backing_sites_list = sites_backing[top_pick]
                backing_sites_str = " + ".join(backing_sites_list)
                
                match_text = (
                    f"• **{match}** ➔ {top_pick}\n"
                    f"  ↳ ✅ Backed by: `{backing_sites_str}`\n"
                )
                
                left_out_sites = [s for s in all_scrapers if s not in backing_sites_list]
                for left_out in left_out_sites:
                    match_text += f"  ↳ ⚪ {left_out}: Not Listed\n"
                    
                niche_matches.append(match_text)
                
                structured_tickets.append({
                    "match": match, "prediction": top_pick, "status": "PENDING", "score": "-"
                })

                ai_input_data.append({
                    "match": match, "consensus_pick": top_pick, 
                    "backed_by": backing_sites_str, "tier": "Niche Coverage"
                })

        return agreed_matches, niche_matches, structured_tickets, ai_input_data, required_consensus

    def ask_llm_to_optimize_tickets(self, ai_input_data):
        if not GEMINI_API_KEY:
            self.diagnostics["AI_Status"] = "🔴 Missing GEMINI_API_KEY"
            return None

        model_name = "models/gemini-3.5-flash"  
        try:
            list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
            resp = requests.get(list_url, timeout=10)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                
                valid_models = []
                for m in models:
                    name = m.get("name", "")
                    methods = m.get("supportedGenerationMethods", [])
                    if "generateContent" in methods and "flash" in name.lower() and "preview" not in name.lower():
                        valid_models.append(name)
                
                if valid_models:
                    valid_models.sort(reverse=True)
                    model_name = valid_models[0]

                self.diagnostics["AI_Handshake"] = f"🟢 Connected ({model_name})"
        except Exception as e:
            self.diagnostics["AI_Handshake"] = f"🔴 Handshake Exception: {str(e)[:40]}"

        url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={GEMINI_API_KEY}"
        
        prompt = f"""
        You are an expert quantitative sports betting algorithmic model. Your sole task is to analyze today's football consensus data and generate highly optimized betslips with ABSOLUTELY ZERO textual explanations, introductions, headers, or footnotes.

        Here is today's raw consensus data:
        {json.dumps(ai_input_data, indent=2)}

        STRICT ARCHITECTURE RULES:
        1. NEVER repeat the same match across multiple tickets. A match can only appear ONCE in your entire output.
        2. IF there are 3 or more matches provided: Divide them into up to THREE completely separate, non-overlapping tickets:
           🛡️ TICKET 1: SAFE ANCHORS 
           ⚖️ TICKET 2: BALANCED GROWTH 
           🎯 TICKET 3: VALUE & VOLATILITY
        3. IF there are only 1 or 2 matches provided: Output a single ticket:
           🔥 TICKET 1: PREMIUM SINGLES/DOUBLES
           • [Match Name] ➔ [Optimized Prediction]
        4. Apply your advanced risk-mitigation optimizations DIRECTLY on the slip lines (e.g., change '➔ 1' to '➔ 1X' or '➔ Draw No Bet').
        5. NO paragraphs of text. NO explanations. Output ONLY the formatted tickets.
        """

        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                data = response.json()
                self.diagnostics["AI_Status"] = "🟢 Optimization Complete"
                return data['candidates'][0]['content']['parts'][0]['text']
            else:
                self.diagnostics["AI_Status"] = f"🔴 API Error {response.status_code}"
                return None
        except Exception as e:
            self.diagnostics["AI_Status"] = f"🔴 Exception: {str(e)[:60]}"
            return None

    # ==========================================================================
    # IMMUTABLE DAILY LOCKING ARCHITECTURE & BACKWARDS COMPATIBILITY
    # ==========================================================================
    def load_memory(self):
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE, "r") as f:
                    return json.load(f)
            except Exception: pass
        return {}

    def save_memory(self, memory):
        try:
            with open(MEMORY_FILE, "w") as f:
                json.dump(memory, f, indent=4)
        except Exception: pass

    def fetch_results_from_statarea(self, target_date):
        results = {}
        url = f"https://www.statarea.com/predictions/date/{target_date}/"
        try:
            r = tls_requests.get(url, impersonate="chrome120", timeout=20)
            if r.status_code == 200:
                soup = BeautifulSoup(r.content, 'html.parser')
                for row in soup.find_all("div", class_="matchrow"):
                    text = row.get_text(separator=" ").upper()
                    padded_text = f" {text} "
                    if any(flag in padded_text for flag in [" FT ", "FINISHED", " AET ", " PEN "]):
                        home_elems = row.find_all("div", class_="name")
                        if len(home_elems) >= 2:
                            home = self.clean_team_name(home_elems[0].text)
                            away = self.clean_team_name(home_elems[1].text)
                        
                        score_match = re.search(r'\b(\d{1,2})\s*-\s*(\d{1,2})\b', text)
                        if score_match:
                            score = f"{score_match.group(1)}-{score_match.group(2)}"
                            results[f"{home} vs {away}"] = score
        except Exception: pass
        return results

    def settle_pending_tickets(self, memory):
        settled_reports = []
        needs_save = False

        dates_to_check = set()
        for date_str, payload in memory.items():
            # BACKWARDS COMPATIBILITY: Handle old list format vs new dict format
            tickets = payload if isinstance(payload, list) else payload.get("tickets", [])
            for t in tickets:
                if t.get("status") == "PENDING":
                    dates_to_check.add(date_str)

        if not dates_to_check: return []

        results_matrix = {}
        for d in dates_to_check:
            results_matrix.update(self.fetch_results_from_statarea(d))

        for date_str, payload in memory.items():
            # BACKWARDS COMPATIBILITY
            tickets = payload if isinstance(payload, list) else payload.get("tickets", [])
            for t in tickets:
                if t.get("status") == "PENDING":
                    match_key = t["match"]
                    prediction = t["prediction"]

                    score = None
                    for res_key, res_score in results_matrix.items():
                        if res_key.lower() == match_key.lower():
                            score = res_score
                            break

                    if score:
                        try:
                            home_g, away_g = map(int, score.split("-"))
                            if home_g > away_g: actual = "1"
                            elif home_g == away_g: actual = "X"
                            else: actual = "2"

                            if prediction == actual: t["status"] = "WON 🟢"
                            else: t["status"] = "LOST 🔴"

                            t["score"] = score
                            needs_save = True

                            settled_reports.append(
                                f"• **{match_key}** ➔ **{t['status']}** (Score: {score})"
                            )
                        except Exception: pass

        if needs_save:
            self.save_memory(memory)

        return settled_reports

    def send_telegram_alert(self, msg):
        if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}
            try:
                r = tls_requests.post(url, json=payload, impersonate="chrome120", timeout=15)
                if r.status_code != 200:
                    payload.pop("parse_mode")
                    tls_requests.post(url, json=payload, impersonate="chrome120", timeout=15)
            except Exception as e:
                print(f"Telegram alert failed: {e}")

    async def run_pipeline(self):
        today_date = (datetime.datetime.utcnow() + datetime.timedelta(hours=3)).strftime('%Y-%m-%d')
        memory = self.load_memory()

        today_payload = memory.get(today_date)

        # Check if today's picks are ALREADY LOCKED (Safely checks against old list format)
        if isinstance(today_payload, dict) and today_payload.get("locked"):
            print(f"🔒 Today's predictions ({today_date}) are already locked. Reusing existing picks.")
            daily_data = memory[today_date]
            agreed_matches = daily_data.get("agreed_matches", [])
            niche_matches = daily_data.get("niche_matches", [])
            ai_optimized_message = daily_data.get("ai_optimized_message")
            req_threshold = daily_data.get("req_threshold", 3)
            self.diagnostics["Daily_Lock"] = f"🔒 LOCKED ON {today_date}"
        else:
            print(f"🔓 First run for {today_date} (or upgrading old format). Scraping and generating tickets...")
            loop = asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                await asyncio.gather(*[loop.run_in_executor(pool, self.fetch_and_scrape_sync, n, c) for n, c in self.configs.items()])

            agreed_matches, niche_matches, structured_tickets, ai_input_data, req_threshold = self.process_consensus_signals()

            ai_optimized_message = None
            if ai_input_data:
                ai_optimized_message = self.ask_llm_to_optimize_tickets(ai_input_data)

            # LOCK TODAY'S DATA PERMANENTLY (Upgrades old list format to new dict format automatically)
            memory[today_date] = {
                "locked": True,
                "agreed_matches": agreed_matches,
                "niche_matches": niche_matches,
                "ai_optimized_message": ai_optimized_message,
                "req_threshold": req_threshold,
                "tickets": structured_tickets
            }
            self.save_memory(memory)
            self.diagnostics["Daily_Lock"] = f"🟢 LOCKED NEW DATA FOR {today_date}"

        # Settle results across all pending days
        settled_reports = self.settle_pending_tickets(memory)

        # Build Message
        msg = f"🤝 **RAW CONSENSUS DATA ({req_threshold}+ SITES AGREEMENT)** 🤝\n\n"
        if not agreed_matches:
            msg += f"No matches found with {req_threshold}+ sites in agreement today.\n\n"
        else:
            for match in agreed_matches: msg += f"{match}\n"
                
        if niche_matches:
            msg += "🕵️ **NICHE CONSENSUS (100% AGREEMENT ON OBSCURE MATCHES)** 🕵️\n\n"
            for match in niche_matches: msg += f"{match}\n"
                
        if ai_optimized_message:
            msg += f"🤖 **TITAN AI OPTIMIZED TICKETS** 🤖\n\n{ai_optimized_message}\n\n"

        if settled_reports:
            msg += "📊 **SETTLED RESULTS (Newly Finalized)** 📊\n\n"
            for rep in settled_reports: msg += f"{rep}\n"
            msg += "\n"

        msg += "⚙️ **SCRAPER STATUS** ⚙️\n"
        for site, status in self.diagnostics.items(): msg += f"↳ {site}: {status}\n"

        self.send_telegram_alert(msg)

if __name__ == "__main__":
    live_configs = get_dynamic_configs()
    asyncio.run(ConsensusEngine(live_configs).run_pipeline())
