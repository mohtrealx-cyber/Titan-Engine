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
        },
        "SoccerVista": {
            "url": "https://www.soccervista.com/",
            "row_selector": "tr", "row_class": "",
            "home_selector": "td", "home_class": "", "home_index": 0,
            "away_selector": "td", "away_class": "", "away_index": 1,
            "pick_selector": "td", "pick_class": "", "pick_index": 4,
            "use_scraperapi": False
        }
    }

class ConsensusEngine:
    def __init__(self, configs):
        self.configs = configs
        self.master_matrix = {}
        self.corner_stats = {} 
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
        # Strip common web scraping button artifacts
        cleaned = re.sub(r'(?i)\b(match preview|preview)\b', '', str(name))
        # Collapse multiple spaces and clean whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned.title()

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

    # ==========================================================================
    # CORNER STATS SCRAPER MODULE (TOTALCORNER PIVOT)
    # ==========================================================================
    def fetch_corners_sync(self):
        url = "https://www.totalcorner.com/match/today"
        try:
            if SCRAPER_API_KEY:
                proxy_url = f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={url}"
                r = tls_requests.get(proxy_url, timeout=60)
            else:
                r = tls_requests.get(url, impersonate="chrome120", timeout=20)
            
            if r.status_code == 200:
                soup = BeautifulSoup(r.content, 'html.parser')
                rows = soup.find_all("tr")
                
                valid_corners = 0
                for row in rows:
                    cols = [c.text.strip() for c in row.find_all(["td", "th"]) if c.text.strip()]
                    
                    if len(cols) >= 5:
                        team_links = row.find_all("a", href=re.compile(r"/team/"))
                        
                        if len(team_links) >= 2:
                            home_team = self.clean_team_name(team_links[0].text)
                            away_team = self.clean_team_name(team_links[1].text)
                            
                            row_text = row.get_text(separator=" ")
                            averages = re.findall(r'\b([7-9]\.\d|1[0-5]\.\d)\b', row_text)
                            
                            if averages:
                                highest_avg = max([float(x) for x in averages])
                                
                                if highest_avg >= 8.5:
                                    self.corner_stats[home_team] = highest_avg
                                    self.corner_stats[away_team] = highest_avg
                                    valid_corners += 1
                                    
                self.diagnostics["Corners_Engine"] = f"🟢 OK ({valid_corners} High-Corner Teams)"
            else:
                self.diagnostics["Corners_Engine"] = f"🔴 FAILED (HTTP {r.status_code})"
        except Exception as e:
            self.diagnostics["Corners_Engine"] = "🔴 TIMEOUT/ERROR"

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
                rows = soup.find_all("div", class_=row_target)
            elif site_name == "SoccerVista":
                rows = soup.find_all("tr")
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
                                        
                    # Custom parsing rules for SoccerVista tables
                    elif site_name == "SoccerVista":
                        tds = row.find_all("td")
                        if len(tds) >= 4:
                            home_elem = row.find(class_=re.compile(r"home|team1", re.IGNORECASE))
                            away_elem = row.find(class_=re.compile(r"away|team2", re.IGNORECASE))
                            
                            if home_elem and away_elem:
                                home = home_elem.text
                                away = away_elem.text
                            else:
                                # Fallback assumption based on standard SoccerVista tabular data
                                home = tds[1].text if len(tds) > 1 else None
                                away = tds[2].text if len(tds) > 2 else None
                                
                            # Search the remaining columns for the direct 1, X, 2 marker
                            for td in tds[3:]:
                                text = td.get_text(strip=True).upper()
                                if text in ["1", "X", "2", "1X", "X2", "12"]:
                                    pick = text
                                    break
                    
                    # Original parsing for Statarea and Vitibet
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

        # Updated to include SoccerVista in the consensus engine logic
        all_scrapers = ["Statarea", "Vitibet", "PredictZ", "WinDrawWin", "SoccerVista"]
        active_scrapers_count = sum(1 for status in self.diagnostics.values() if "🟢 OK" in status and "Teams" not in status)
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

    def ask_llm_to_optimize_tickets(self, ai_input_data, active_corner_teams):
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
        You are an expert quantitative sports betting algorithmic model. Your task is to analyze today's football consensus data AND high-corner statistical advantages to generate highly optimized betslips with ABSOLUTELY ZERO textual explanations, introductions, headers, or footnotes.

        Here is today's raw consensus data (Match Winners/Goals):
        {json.dumps(ai_input_data, indent=2)}

        Here is today's active High-Corner Team data (Teams playing today with high total corner averages):
        {json.dumps(active_corner_teams, indent=2)}

        STRICT ARCHITECTURE RULES:
        1. NEVER repeat the same match across multiple tickets. A match can only appear ONCE in your entire output.
        2. ACT AS A PORTFOLIO MANAGER: You are allowed to DROP weak consensus matches and REPLACE them with Corner predictions (e.g., 'Over 8.5 Corners' or 'Over 9.5 Corners') if the corner data provides a mathematically safer floor. Mix and match to build the most secure tickets possible.
        3. IF there are 3 or more matches available: Divide them into up to THREE completely separate, non-overlapping tickets:
           🛡️ TICKET 1: THE IRONCLAD SLIP (Highest Safety - Mix safest consensus & safest corners) 
           ⚖️ TICKET 2: BALANCED GROWTH 
           🎯 TICKET 3: VALUE & VOLATILITY (Niche matches)
        4. IF there are only 1 or 2 matches available: Output a single ticket:
           🔥 TICKET 1: PREMIUM SINGLES/DOUBLES
           • [Match Name] ➔ [Optimized Prediction]
        5. Apply your advanced risk-mitigation optimizations DIRECTLY on the slip lines (e.g., change '➔ 1' to '➔ 1X', or replace with '➔ Over 8.5 Corners').
        6. NO paragraphs of text. NO explanations. Output ONLY the formatted tickets.
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
    # IMMUTABLE DAILY LOCKING ARCHITECTURE
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
            tickets = payload if isinstance(payload, list) else payload.get("tickets", [])
            for t in tickets:
                if t.get("status") == "PENDING":
                    dates_to_check.add(date_str)

        if not dates_to_check: return []

        results_matrix = {}
        for d in dates_to_check:
            results_matrix.update(self.fetch_results_from_statarea(d))

        for date_str, payload in memory.items():
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
        eat_time = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
        today_date = eat_time.strftime('%Y-%m-%d')
        current_hour = eat_time.hour

        memory = self.load_memory()
        today_payload = memory.get(today_date)

        is_already_locked = False
        if isinstance(today_payload, dict):
            if today_payload.get("locked") and current_hour >= 6:
                is_already_locked = True
            elif today_payload.get("locked") and current_hour < 6:
                print("⚠️ Found a premature lock. Forcing unlock since it is before 6:00 AM EAT.")
                is_already_locked = False

        if is_already_locked:
            print(f"🔒 Today's predictions ({today_date}) are already locked. Reusing existing picks.")
            daily_data = memory[today_date]
            agreed_matches = daily_data.get("agreed_matches", [])
            niche_matches = daily_data.get("niche_matches", [])
            ai_optimized_message = daily_data.get("ai_optimized_message")
            req_threshold = daily_data.get("req_threshold", 3)
            self.diagnostics["Daily_Lock"] = f"🔒 LOCKED ON {today_date}"
        else:
            print(f"🔓 Scraping and generating tickets for {today_date}...")
            loop = asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
                tasks = [loop.run_in_executor(pool, self.fetch_and_scrape_sync, n, c) for n, c in self.configs.items()]
                tasks.append(loop.run_in_executor(pool, self.fetch_corners_sync))
                await asyncio.gather(*tasks)

            agreed_matches, niche_matches, structured_tickets, ai_input_data, req_threshold = self.process_consensus_signals()

            active_corner_teams = []
            for match in self.master_matrix.keys():
                parts = match.split(" vs ")
                if len(parts) == 2:
                    h, a = parts[0].strip(), parts[1].strip()
                    if h in self.corner_stats and self.corner_stats[h] >= 9.5:
                        active_corner_teams.append({"match": match, "team": h, "avg_corners": self.corner_stats[h]})
                    if a in self.corner_stats and self.corner_stats[a] >= 9.5:
                        active_corner_teams.append({"match": match, "team": a, "avg_corners": self.corner_stats[a]})

            ai_optimized_message = None
            if ai_input_data or active_corner_teams:
                ai_optimized_message = self.ask_llm_to_optimize_tickets(ai_input_data, active_corner_teams)

            should_lock = current_hour >= 6

            memory[today_date] = {
                "locked": should_lock,
                "agreed_matches": agreed_matches,
                "niche_matches": niche_matches,
                "ai_optimized_message": ai_optimized_message,
                "req_threshold": req_threshold,
                "tickets": structured_tickets
            }
            self.save_memory(memory)
            
            if should_lock:
                self.diagnostics["Daily_Lock"] = f"🟢 LOCKED NEW DATA FOR {today_date}"
            else:
                self.diagnostics["Daily_Lock"] = f"⏳ PREVIEW (Will Lock At 06:00 EAT)"

        settled_reports = self.settle_pending_tickets(memory)

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
