import os
import re
import json
import time
import asyncio
import datetime
import difflib
import traceback
import threading
import random
import concurrent.futures
from bs4 import BeautifulSoup
from curl_cffi import requests as tls_requests
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

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
            "url": "https://www.soccervista.com/predictions/",
            "row_selector": "tr", "row_class": "",
            "home_selector": "td", "home_class": "", "home_index": 0,
            "away_selector": "td", "home_class": "", "away_index": 1,
            "pick_selector": "td", "pick_class": "", "pick_index": 4,
            "use_scraperapi": True
        },
        "Forebet": {
            "url": "https://www.forebet.com/en/football-tips-and-predictions-for-today",
            "row_selector": "div", "row_class": "rcnt",
            "home_selector": "span", "home_class": "homeTeam", "home_index": 0,
            "away_selector": "span", "away_class": "awayTeam", "away_index": 0,
            "pick_selector": "div", "pick_class": "predict_y", "pick_index": 0,
            "use_scraperapi": True
        },
        "Zulubet": {
            "url": "https://www.zulubet.com/",
            "row_selector": "tr", "row_class": "",
            "home_selector": "td", "home_class": "", "home_index": 0,
            "away_selector": "td", "home_class": "", "away_index": 1,
            "pick_selector": "td", "pick_class": "prediction_full", "pick_index": 0,
            "use_scraperapi": True
        },
        "BetExplorer": {
            "url": "https://www.betexplorer.com/football/popular-bets/",
            "row_selector": "tr", "row_class": "",
            "home_selector": "a", "home_class": "", "home_index": 0,
            "away_selector": "a", "away_class": "", "away_index": 1,
            "pick_selector": "td", "pick_class": "", "pick_index": 2,
            "use_scraperapi": True
        },
        "BettingTips1x2": {
            "url": "https://www.bettingtips1x2.com/",
            "row_selector": "tr", "row_class": "",
            "home_selector": "td", "home_class": "", "home_index": 0,
            "away_selector": "td", "home_class": "", "away_index": 1,
            "pick_selector": "td", "pick_class": "", "pick_index": 2,
            "use_scraperapi": True
        },
        "VictorsPredict": {
            "url": "https://victorspredict.com/free-tips",
            "row_selector": "tr", "row_class": "",
            "home_selector": "td", "home_class": "", "home_index": 1,
            "away_selector": "td", "away_class": "", "away_index": 2,
            "pick_selector": "td", "pick_class": "", "pick_index": 3,
            "use_scraperapi": True
        },
        "ProSoccer": {
            "url": "https://www.prosoccer.eu/football-predictions/",
            "row_selector": "tr", "row_class": "",
            "use_scraperapi": True
        },
        "Tipsbet": {
            "url": "https://tipsbet.co.uk/free-betting-tips/",
            "row_selector": "tr", "row_class": "",
            "use_scraperapi": True
        },
        "SoccerPunter": {
            "url": "https://www.soccerpunter.com/",
            "row_selector": "tr", "row_class": "",
            "use_scraperapi": True
        },
        "BetClan": {
            "url": "https://www.betclan.com/",
            "row_selector": "div", "row_class": "match-row",
            "home_selector": "div", "home_class": "team-name", "home_index": 0,
            "away_selector": "div", "away_class": "team-name", "away_index": 1,
            "pick_selector": "div", "pick_class": "prediction", "pick_index": 0,
            "use_scraperapi": True
        },
        "FootballPredictions": {
            "url": "https://footballpredictions.com/footballpredictions/",
            "row_selector": "div", "row_class": "match",
            "home_selector": "div", "home_class": "team", "home_index": 0,
            "away_selector": "div", "away_class": "team", "away_index": 1,
            "pick_selector": "div", "pick_class": "pred", "pick_index": 0,
            "use_scraperapi": True
        }
    }

class ConsensusEngine:
    def __init__(self, configs):
        self.configs = configs
        self.master_matrix = {}
        self.corner_stats = {} 
        self.diagnostics = {}
        self.matrix_lock = threading.Lock()

    def normalize_prediction(self, raw_text):
        text = str(raw_text).strip().upper()
        
        if text in ["1X", "1 OR X", "HOME OR DRAW"]: return "1X"
        if text in ["X2", "X OR 2", "AWAY OR DRAW"]: return "X2"
        if text in ["12", "1 OR 2", "HOME OR AWAY"]: return "12"
        if "OVER" in text: return "OVER"
        if "UNDER" in text: return "UNDER"

        if text in ["HOME", "HOME WIN", "1"]: return "1"
        if text in ["DRAW", "X", "0"]: return "X"
        if text in ["AWAY", "AWAY WIN", "2"]: return "2"

        if len(text) > 0:
            char = text[0]
            if char == "1" or char == "H": return "1"
            if char in ["X", "0", "D"]: return "X"
            if char == "2" or char == "A": return "2"
        return None

    def clean_team_name(self, name):
        cleaned = re.sub(r'(?i)\b(match preview|preview|results?)\b', '', str(name))
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned.title()

    def is_match_active_or_played(self, row, site_name=""):
        text = row.get_text(separator=" ").upper()
        padded_text = f" {text} "
        
        if site_name == "Forebet":
            status_flags = [" FINISHED ", " CANC ", " POSTP "]
        else:
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

        with self.matrix_lock:
            for existing_key in self.master_matrix.keys():
                similarity = difflib.SequenceMatcher(None, raw_match_key.lower(), existing_key.lower()).ratio()
                if similarity >= 0.75: 
                    final_key = existing_key
                    break

            if final_key not in self.master_matrix: 
                self.master_matrix[final_key] = []

            existing_sites = [entry[0] for entry in self.master_matrix[final_key]]
            if site_name not in existing_sites:
                self.master_matrix[final_key].append((site_name, normalized_pick))

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=3, max=25), reraise=True)
    def robust_get_request(self, url, use_scraperapi=False, site_name=""):
        # Stagger concurrent requests dynamically to prevent immediate 429 blocks
        time.sleep(random.uniform(1.0, 5.0)) 
        
        if use_scraperapi and SCRAPER_API_KEY:
            render_flag = "&render=true" if site_name in ["SoccerVista", "BetExplorer", "BettingTips1x2", "ProSoccer"] else ""
            proxy_url = f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={url}{render_flag}"
            r = tls_requests.get(proxy_url, timeout=60)
        else:
            r = tls_requests.get(url, impersonate="chrome", timeout=30)
            
        # Force a Tenacity retry sequence if rate-limited or encountering server errors
        if r.status_code in [429, 500, 502, 503, 504]:
            raise Exception(f"HTTP {r.status_code} encountered on {site_name}. Triggering Tenacity backoff...")
            
        return r

    def fetch_corners_sync(self):
        url = "https://www.totalcorner.com/match/today"
        try:
            r = self.robust_get_request(url, use_scraperapi=True, site_name="Corners_Engine")
            
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
            r = self.robust_get_request(cfg['url'], cfg.get("use_scraperapi", False), site_name)

            if r.status_code != 200:
                self.diagnostics[site_name] = f"🔴 FAILED (HTTP {r.status_code})"
                return

            soup = BeautifulSoup(r.content, 'html.parser')
            
            if site_name in ["PredictZ", "WinDrawWin"]:
                row_target = re.compile(r"(pt|wt)(tr|row)")
                rows = soup.find_all("div", class_=row_target)
            elif site_name in ["SoccerVista", "Zulubet", "BetExplorer", "BettingTips1x2", "VictorsPredict", "ProSoccer", "Tipsbet", "SoccerPunter"]:
                rows = soup.find_all("tr")
            elif site_name in ["BetClan", "FootballPredictions"]:
                rows = soup.find_all("div", class_=cfg.get("row_class", "match"))
            else:
                row_target = cfg.get("row_class", "")
                rows = soup.find_all(cfg["row_selector"], class_=row_target)

            if not rows:
                self.diagnostics[site_name] = f"🟡 BLOCKED"
                return

            valid_count = 0
            skipped_count = 0

            for row in rows:
                try:
                    if self.is_match_active_or_played(row, site_name):
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
                                        
                    elif site_name == "SoccerVista":
                        tds = row.find_all("td")
                        if len(tds) >= 4:
                            raw_home = tds[1].text
                            raw_away = tds[3].text if len(tds) > 3 else (tds[2].text if len(tds) > 2 else "")
                            home = re.sub(r'^([WDL]\s+)+', '', raw_home).strip()
                            away = re.sub(r'(\s+[WDL])+$', '', raw_away).strip()
                            
                            for td in tds:
                                txt = td.text.strip().upper()
                                if "10 ON " in txt:
                                    target = txt.replace("10 ON ", "").strip()
                                    if target in ["DRAW", "X"]: pick = "X"
                                    elif target and (target in home.upper() or home.upper().startswith(target)): pick = "1"
                                    elif target and (target in away.upper() or away.upper().startswith(target)): pick = "2"
                                    elif len(target) >= 3 and target[:3] in home.upper(): pick = "1"
                                    elif len(target) >= 3 and target[:3] in away.upper(): pick = "2"
                                    else: pick = "1"
                                    break
                                elif txt in ["1", "X", "2", "1X", "X2", "12"]:
                                    pick = txt
                                    break

                    elif site_name == "Zulubet":
                        links = row.find_all("a")
                        if len(links) >= 2:
                            home = links[0].text
                            away = links[1].text
                        
                        prob_cells = row.find_all("td", class_=re.compile("prediction_full"))
                        if len(prob_cells) >= 3:
                            vals = []
                            for pc in prob_cells:
                                clean_val = re.sub(r'\D', '', pc.text)
                                vals.append(int(clean_val) if clean_val else 0)
                            if max(vals) > 0:
                                max_idx = vals.index(max(vals))
                                if max_idx == 0: pick = "1"
                                elif max_idx == 1: pick = "X"
                                else: pick = "2"

                    elif site_name in ["BetExplorer", "BettingTips1x2", "VictorsPredict", "ProSoccer", "Tipsbet", "SoccerPunter"]:
                        tds = row.find_all("td")
                        if len(tds) >= 3:
                            links = row.find_all("a")
                            if len(links) >= 2:
                                home = links[0].text
                                away = links[1].text
                            else:
                                home = tds[1].text if len(tds) > 1 else ""
                                away = tds[2].text if len(tds) > 2 else ""
                            
                            for td in tds:
                                txt = td.text.strip()
                                norm = self.normalize_prediction(txt)
                                if norm:
                                    pick = norm
                                    break

                    else:
                        home = row.find_all(cfg["home_selector"], class_=cfg["home_class"])[cfg["home_index"]].text
                        away = row.find_all(cfg["away_selector"], class_=cfg["away_class"])[cfg["away_index"]].text
                        pick = row.find_all(cfg["pick_selector"], class_=cfg["pick_class"])[cfg["pick_index"]].text

                    home_str = self.clean_team_name(home) if home else ""
                    away_str = self.clean_team_name(away) if away else ""

                    if not home_str and away_str:
                        if re.search(r'(?i)\s+vs?\s+', away_str):
                            parts = re.split(r'(?i)\s+vs?\s+', away_str, maxsplit=1)
                            home_str, away_str = self.clean_team_name(parts[0]), self.clean_team_name(parts[1])

                    if not away_str and home_str:
                        if re.search(r'(?i)\s+vs?\s+', home_str):
                            parts = re.split(r'(?i)\s+vs?\s+', home_str, maxsplit=1)
                            home_str, away_str = self.clean_team_name(parts[0]), self.clean_team_name(parts[1])

                    home, away = home_str, away_str

                    if home and away and pick:
                        self.log_prediction_qa(site_name, home, away, pick)
                        valid_count += 1

                except Exception:
                    continue

            self.diagnostics[site_name] = f"🟢 OK ({valid_count} Upcoming | {skipped_count} Played)"

        except Exception as e:
            self.diagnostics[site_name] = "🔴 TIMEOUT/ERROR"
            return

    def process_consensus_signals(self):
        agreed_matches = []
        niche_matches = []
        structured_tickets = []
        ai_input_data = []

        all_scrapers = [
            "Statarea", "Vitibet", "PredictZ", "WinDrawWin", "SoccerVista", 
            "Forebet", "Zulubet", "BetExplorer", "BettingTips1x2", 
            "VictorsPredict", "ProSoccer", "Tipsbet", "BetClan", 
            "FootballPredictions", "SoccerPunter"
        ]
        
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
            
            if prediction_weights[top_pick] >= required_consensus:
                backing_sites_list = sites_backing[top_pick]
                backing_sites_str = " + ".join(backing_sites_list)
                contradictions = []

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
                        contradictions.append(f"{left_out} ({other_pick})")
                    else: 
                        match_text += f"  ↳ ⚪ {left_out}: Not Listed\n"

                agreed_matches.append(match_text)
                structured_tickets.append({"match": match, "prediction": top_pick, "status": "PENDING", "score": "-"})
                
                ai_input_data.append({
                    "match": match, 
                    "consensus_pick": top_pick, 
                    "backed_by": backing_sites_str, 
                    "contradictions": contradictions, 
                    "tier": "Core Consensus"
                })

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
                structured_tickets.append({"match": match, "prediction": top_pick, "status": "PENDING", "score": "-"})
                
                ai_input_data.append({
                    "match": match, 
                    "consensus_pick": top_pick, 
                    "backed_by": backing_sites_str, 
                    "contradictions": [], 
                    "tier": "Niche Coverage"
                })

        return agreed_matches, niche_matches, structured_tickets, ai_input_data, required_consensus

    def ask_llm_to_optimize_tickets(self, ai_input_data, active_corner_teams):
        if not GEMINI_API_KEY:
            self.diagnostics["AI_Status"] = "🔴 Missing GEMINI_API_KEY"
            return None, []

        model_name = "models/gemini-2.5-flash"
        try:
            list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
            resp = requests.get(list_url, timeout=10)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                valid_models = []
                for m in models:
                    name = m.get("name", "")
                    methods = m.get("supportedGenerationMethods", [])
                    if "generateContent" in methods and "flash" in name.lower() and "preview" not in name.lower() and "8b" not in name.lower():
                        valid_models.append(name)
                if valid_models:
                    valid_models.sort(reverse=True)
                    model_name = valid_models[0]
                self.diagnostics["AI_Handshake"] = f"🟢 Connected ({model_name})"
        except Exception as e:
            self.diagnostics["AI_Handshake"] = f"🔴 Handshake Exception: {str(e)[:40]}"

        url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={GEMINI_API_KEY}"
        
        prompt = f"""
        You are Titan, an elite quantitative sports betting AI Portfolio Manager.
        Analyze the following raw consensus data and corner statistics to construct optimized betting tickets.

        === RAW CONSENSUS DATA ===
        {json.dumps(ai_input_data, indent=2)}

        === HIGH-PROBABILITY CORNER STATISTICS ===
        {json.dumps(active_corner_teams, indent=2)}

        STRICT ARCHITECTURE RULES:
        1. NEVER repeat the same match across multiple tickets or reserve slots. Every match must be completely unique.
        2. You are allowed to REPLACE weak consensus matches with Corner predictions (e.g., 'Over 8.5 Corners') if the corner data provides a mathematically safer floor.
        3. TICKET 4 (CORNER LAB): Create a dedicated corner-only accumulator strictly using high-probability corner stats from MAJOR leagues only. Reject obscure lower-tier divisions.
        4. YOU MUST RETURN YOUR OUTPUT IN PURE JSON FORMAT MATCHING EXACTLY THIS SCHEMA:
        {{
          "tickets": [
            {{
              "ticket_name": "🛡️ Ticket 1: Ironclad (40% of Daily Stake)",
              "matches": [
                {{"match": "Team A vs Team B", "prediction": "1X"}},
                {{"match": "Team C vs Team D", "prediction": "Over 8.5 Corners"}}
              ],
              "reserve_match": {{"match": "Team E vs Team F", "prediction": "1"}}
            }}
          ]
        }}
        Create Tickets 1, 2, 3, and 4. No markdown text outside the JSON.
        """

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"response_mime_type": "application/json"}
        }
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                data = response.json()
                raw_content = data['candidates'][0]['content']['parts'][0]['text']
                
                parsed_json = json.loads(raw_content)
                ai_message_lines = []
                ai_structured_tickets = []
                
                for ticket in parsed_json.get("tickets", []):
                    ai_message_lines.append(f"{ticket['ticket_name']}")
                    for match in ticket.get("matches", []):
                        ai_message_lines.append(f"• **{match['match']}** ➔ {match['prediction']}")
                        ai_structured_tickets.append({"match": match['match'], "prediction": match['prediction'], "status": "PENDING", "score": "-"})
                    
                    reserve = ticket.get("reserve_match")
                    if reserve:
                        ai_message_lines.append(f"🔄 [RESERVE PICK]: {reserve['match']} ➔ {reserve['prediction']}\n")
                        ai_structured_tickets.append({"match": reserve['match'], "prediction": reserve['prediction'], "status": "PENDING", "score": "-"})
                
                self.diagnostics["AI_Status"] = "🟢 Optimization Complete"
                return "\n".join(ai_message_lines), ai_structured_tickets
            else:
                self.diagnostics["AI_Status"] = f"🔴 API Error {response.status_code}"
                return None, []
        except Exception as e:
            self.diagnostics["AI_Status"] = f"🔴 Exception: {str(e)[:60]}"
            return None, []

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
            r = tls_requests.get(url, impersonate="chrome", timeout=20)
            if r.status_code == 200:
                soup = BeautifulSoup(r.content, 'html.parser')
                for row in soup.find_all("div", class_="matchrow"):
                    home = away = score = None
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
                            
                        if home and away and score:
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

                            if "corner" in prediction.lower():
                                t["status"] = "MANUAL CHECK 🟡"
                            elif prediction == actual: 
                                t["status"] = "WON 🟢"
                            else: 
                                t["status"] = "LOST 🔴"

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
        if not (TELEGRAM_TOKEN and TELEGRAM_CHAT_ID):
            print("Telegram credentials missing.")
            return

        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        
        msg_chunks = []
        current_chunk = ""
        for line in msg.split("\n"):
            if len(current_chunk) + len(line) + 1 > 3500:
                msg_chunks.append(current_chunk)
                current_chunk = line + "\n"
            else:
                current_chunk += line + "\n"
        if current_chunk:
            msg_chunks.append(current_chunk)
        
        for chunk in msg_chunks:
            payload = {"chat_id": TELEGRAM_CHAT_ID, "text": chunk, "parse_mode": "Markdown"}
            try:
                r = tls_requests.post(url, json=payload, impersonate="chrome", timeout=15)
                if r.status_code != 200:
                    payload.pop("parse_mode")
                    tls_requests.post(url, json=payload, impersonate="chrome", timeout=15)
            except Exception as e:
                print(f"Telegram alert exception: {e}")
            time.sleep(1)

    async def run_pipeline(self):
        eat_time = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
        today_date = eat_time.strftime('%Y-%m-%d')

        memory = self.load_memory()
        today_payload = memory.get(today_date)

        is_already_locked = False
        if isinstance(today_payload, dict):
            if today_payload.get("locked"):
                is_already_locked = True

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
            
            # Throttled the maximum workers down to 5 to avoid triggering immediate 429 concurrency limits
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool: 
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
                ai_optimized_message, ai_structured_tickets = self.ask_llm_to_optimize_tickets(ai_input_data, active_corner_teams)
                if ai_structured_tickets:
                    structured_tickets = ai_structured_tickets

            should_lock = len(agreed_matches) > 0 or len(niche_matches) > 0

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
                self.diagnostics["Daily_Lock"] = f"🔴 NO MATCHES FOUND (Unlocked)"

        settled_reports = self.settle_pending_tickets(memory)

        if agreed_matches or niche_matches:
            msg = f"🤝 **RAW CONSENSUS DATA ({req_threshold}+ SITES AGREEMENT)** 🤝\n\n"
            if not agreed_matches:
                msg += f"No matches found with {req_threshold}+ sites in agreement today.\n\n"
            else:
                for match in agreed_matches: msg += f"{match}\n"
                    
            if niche_matches and len(agreed_matches) <= 9:
                msg += "🕵️ **NICHE CONSENSUS (Top 5 Displayed)** 🕵️\n\n"
                for match in niche_matches[:5]: 
                    msg += f"{match}\n"
                
                if len(niche_matches) > 5:
                    hidden_count = len(niche_matches) - 5
                    msg += f"  ↳ *...and {hidden_count} more passed to AI in background.*\n\n"
                    
            if ai_optimized_message:
                msg += f"🤖 **TITAN AI OPTIMIZED TICKETS** 🤖\n\n{ai_optimized_message}\n\n"

            if settled_reports:
                msg += "📊 **SETTLED RESULTS (Newly Finalized)** 📊\n\n"
                for rep in settled_reports: msg += f"{rep}\n"
                msg += "\n"

            msg += "⚙️ **SCRAPER STATUS** ⚙️\n"
            for site, status in self.diagnostics.items(): msg += f"↳ {site}: {status}\n"

            self.send_telegram_alert(msg)
        else:
            print("No matches reached 3+ site consensus today. Sending heartbeat alert...")
            heartbeat_msg = f"🔒 **DAILY CONSENSUS ENGINE - {today_date}** \n\n⚠️ No matches reached 3+ site consensus today. The scraper ran successfully and monitored all target sites."
            self.send_telegram_alert(heartbeat_msg)

if __name__ == "__main__":
    try:
        live_configs = get_dynamic_configs()
        asyncio.run(ConsensusEngine(live_configs).run_pipeline())
    except Exception as e:
        error_details = traceback.format_exc()[-1000:]
        print(error_details)
        
        if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            payload = {
                "chat_id": TELEGRAM_CHAT_ID, 
                "text": f"🚨 **CRITICAL BOT CRASH** 🚨\n\nThe Quant Engine stopped working:\n```python\n{error_details}\n```",
                "parse_mode": "Markdown"
            }
            try:
                tls_requests.post(url, json=payload, impersonate="chrome", timeout=10)
            except:
                pass
