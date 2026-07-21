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
            "use_scraperapi": False
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
            row_target = re.compile("pttr|ptrow") if site_name == "PredictZ" else cfg["row_class"]
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

                    if site_name == "PredictZ":
                        h_elem = row.find(class_="pttmobh")
                        a_elem = row.find(class_="pttmoba")
                        p_elem = row.find(class_=re.compile("ptoddsdesc|ptmobpred"))

                        if h_elem and a_elem and p_elem:
                            home = h_elem.text
                            away = a_elem.text
                            pick = p_elem.text
                        else:
                            links = row.find_all("a")
                            if len(links) >= 2:
                                home = links[0].text
                                away = links[1].text
                                p_div = row.find(class_=re.compile("ptprd|ptpred"))
                                if p_div: pick = p_div.text
                            else:
                                for td in row.find_all("div", class_="pttd"):
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

                except Exception as e:
                    continue

            self.diagnostics[site_name] = f"🟢 OK ({valid_count} Upcoming | {skipped_count} Played)"

        except Exception as e:
            self.diagnostics[site_name] = "🔴 TIMEOUT/ERROR"
            return

    def process_consensus_signals(self):
        agreed_matches = []
        structured_tickets = []

        for match, listings in self.master_matrix.items():
            if len(listings) < 2: continue

            prediction_weights = {}
            sites_backing = {}
            for site, pick in listings:
                prediction_weights[pick] = prediction_weights.get(pick, 0) + 1
                if pick not in sites_backing: sites_backing[pick] = []
                sites_backing[pick].append(site)

            top_pick = max(prediction_weights, key=prediction_weights.get)
            if prediction_weights[top_pick] >= 2:
                backing_sites_str = " + ".join(sites_backing[top_pick])

                agreed_matches.append(
                    f"• **{match}** ➔ {top_pick}\n"
                    f"  ↳ ✅ Backed by: `{backing_sites_str}`\n"
                )

                structured_tickets.append({
                    "match": match,
                    "prediction": top_pick,
                    "status": "PENDING",
                    "score": "-"
                })

        return agreed_matches, structured_tickets

    def ask_llm_to_optimize_tickets(self, consensus_list):
        if not GEMINI_API_KEY:
            self.diagnostics["AI_Status"] = "🔴 Missing GEMINI_API_KEY in GitHub Secrets"
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
            else:
                self.diagnostics["AI_Handshake"] = f"🔴 Handshake HTTP {resp.status_code}"
        except Exception as e:
            self.diagnostics["AI_Handshake"] = f"🔴 Handshake Exception: {str(e)[:40]}"

        url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={GEMINI_API_KEY}"
        
        prompt = f"""
        You are an expert quantitative sports betting algorithmic model. Your sole task is to analyze today's football consensus data and generate highly optimized betslips with ABSOLUTELY ZERO textual explanations, introductions, headers, or footnotes.

        Here is today's raw consensus data:
        {json.dumps(consensus_list, indent=2)}

        STRICT ARCHITECTURE RULES:
        1. Divide the provided matches into EXACTLY THREE completely separate, non-overlapping tickets. No match should appear in more than one ticket.
        2. TICKET 1 (SAFE TIER): The absolute lowest variance matches.
        3. TICKET 2 (BALANCED TIER): Solid matches with good tactical advantages.
        4. TICKET 3 (VALUE TIER): The remaining matches that carry more volatility.
        5. NO paragraphs of text. NO explanations. NO footnotes at the bottom.
        6. Apply your advanced risk-mitigation optimizations DIRECTLY on the slip lines themselves. For volatile matchups, change the output from a pure outcome (like '➔ 1') to the optimized market directly (such as '➔ 1X', '➔ Over 1.5 Goals', '➔ Draw No Bet', etc.).
        7. Do not wrap the code in markdown blocks. Output the tickets EXACTLY like this:

        🛡️ TICKET 1: SAFE ANCHORS 
        • [Match Name] ➔ [Optimized Prediction]
        • [Match Name] ➔ [Optimized Prediction]

        ⚖️ TICKET 2: BALANCED GROWTH 
        • [Match Name] ➔ [Optimized Prediction]
        • [Match Name] ➔ [Optimized Prediction]

        🎯 TICKET 3: VALUE & VOLATILITY
        • [Match Name] ➔ [Optimized Prediction]
        • [Match Name] ➔ [Optimized Prediction]
        """

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.0,
                "topK": 1,
                "topP": 0.1
            }
        }
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                data = response.json()
                self.diagnostics["AI_Status"] = "🟢 Optimization Complete"
                return data['candidates'][0]['content']['parts'][0]['text']
            else:
                self.diagnostics["AI_Status"] = f"🔴 API Error {response.status_code}: {response.text[:60]}"
                return None
        except Exception as e:
            self.diagnostics["AI_Status"] = f"🔴 Request Exception: {str(e)[:60]}"
            return None

    def save_tickets_to_memory(self, new_tickets):
        file_path = "pending_tickets.json"
        memory = {}
        if os.path.exists(file_path):
            try:
                with open(file_path, "r") as f:
                    memory = json.load(f)
            except: pass

        today_date = (datetime.datetime.utcnow() + datetime.timedelta(hours=3)).strftime('%Y-%m-%d')
        if today_date not in memory:
            memory[today_date] = []

        existing_matches = [t["match"] for t in memory[today_date]]
        for t in new_tickets:
            if t["match"] not in existing_matches:
                memory[today_date].append(t)

        try:
            with open(file_path, "w") as f:
                json.dump(memory, f, indent=4)
        except: pass

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
        except: pass
        return results

    def settle_pending_tickets(self):
        memory_path = "pending_tickets.json"
        if not os.path.exists(memory_path): return []

        try:
            with open(memory_path, "r") as f:
                memory = json.load(f)
        except: return []

        settled_reports = []
        needs_save = False

        dates_to_check = set()
        for date_str, tickets in memory.items():
            for t in tickets:
                if t.get("status") == "PENDING":
                    dates_to_check.add(date_str)

        if not dates_to_check: return []

        results_matrix = {}
        for d in dates_to_check:
            results_matrix.update(self.fetch_results_from_statarea(d))

        for date_str, tickets in memory.items():
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
                        except: pass

        if needs_save:
            try:
                with open(memory_path, "w") as f:
                    json.dump(memory, f, indent=4)
            except: pass

        return settled_reports

    def send_telegram_alert(self, msg):
        if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}
            
            try:
                r = tls_requests.post(url, json=payload, impersonate="chrome120", timeout=15)
                if r.status_code != 200:
                    print(f"Telegram rejected Markdown format. Retrying as plain text... Error: {r.text}")
                    payload.pop("parse_mode")
                    tls_requests.post(url, json=payload, impersonate="chrome120", timeout=15)
            except Exception as e:
                print(f"Telegram alert failed entirely: {e}")

    async def run_pipeline(self):
        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            await asyncio.gather(*[loop.run_in_executor(pool, self.fetch_and_scrape_sync, n, c) for n, c in self.configs.items()])

        consensus_list, structured_tickets = self.process_consensus_signals()
        settled_reports = self.settle_pending_tickets()

        msg = ""
        total_matches = len(consensus_list)

        if total_matches < 3:
            msg = "🛑 **SYSTEM OVERRIDE: LOW VOLUME (NO BET DAY)** 🛑\n\n"
            msg += f"The engine only found **{total_matches}** matches that passed the strict consensus filter today.\n\n"
            msg += "⚠️ **Verdict: NOT SAFE TO BET.** The volume is too low to properly diversify risk across three tickets. Preserve your bankroll for a better board.\n\n"
            
            if total_matches > 0:
                msg += "*(Matches found for monitoring purposes only:)*\n"
                for match in consensus_list: 
                    msg += f"{match}\n"
            
            self.diagnostics["AI_Status"] = "⚪ Skipped (Low Volume)"
        else:
            if structured_tickets:
                self.save_tickets_to_memory(structured_tickets)
            
            ai_optimized_message = self.ask_llm_to_optimize_tickets(consensus_list)
            
            if ai_optimized_message:
                msg = "🤝 **RAW CONSENSUS MATCHES** 🤝\n*(Agreed by 2+ Sites)*\n\n"
                for match in consensus_list: 
                    msg += f"{match}\n"
                
                msg += f"🤖 **TITAN AI OPTIMIZED TICKETS** 🤖\n\n{ai_optimized_message}\n\n"
            else:
                msg = "🤝 **QUANT CONSENSUS ENGINE (AI FALLBACK)** 🤝\n\n"
                third = total_matches // 3
                t1 = consensus_list[:third]
                t2 = consensus_list[third:2*third]
                t3 = consensus_list[2*third:]

                msg += f"🛡️ **TICKET 1: SAFE TIER ({len(t1)} Matches)** 🛡️\n"
                for match in t1: msg += f"{match}\n"
                
                msg += f"\n⚖️ **TICKET 2: BALANCED TIER ({len(t2)} Matches)** ⚖️\n"
                for match in t2: msg += f"{match}\n"
                
                msg += f"\n🎯 **TICKET 3: VALUE TIER ({len(t3)} Matches)** 🎯\n"
                for match in t3: msg += f"{match}\n\n"

        if settled_reports:
            msg += "\n📊 **SETTLED RESULTS (Newly Finalized)** 📊\n\n"
            for rep in settled_reports: msg += f"{rep}\n"
            msg += "\n"

        msg += "\n⚙️ **SCRAPER STATUS** ⚙️\n"
        for site, status in self.diagnostics.items(): msg += f"↳ {site}: {status}\n"

        self.send_telegram_alert(msg)

if __name__ == "__main__":
    live_configs = get_dynamic_configs()
    asyncio.run(ConsensusEngine(live_configs).run_pipeline())
