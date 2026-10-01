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
SCRAPER_API_KEY = (os.environ.get("SCRAPER_API_KEY") or "").strip()

# KEEPING THIS TRUE TO FORCE FRESH RUN
FORCE_RUN = True 

MEMORY_FILE = "pending_tickets.json"

def get_dynamic_configs():
    eat_time = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
    today_date = eat_time.strftime('%Y-%m-%d')
    cb = int(time.time())

    return {
        "Statarea": {
            "url": f"https://www.statarea.com/predictions/date/{today_date}/",
            "fallback_url": None,
            "row_selector": "div", "row_class": "matchrow",
            "home_selector": "div", "home_class": "name", "home_index": 0,
            "away_selector": "div", "away_class": "name", "away_index": 1,
            "pick_selector": "div", "pick_class": "type1", "pick_index": 0,
            "use_scraperapi": False  
        },
        "Vitibet": {
            "url": f"https://www.vitibet.com/index.php?clanek=quicktips&sekce=fotbal&lang=en&cb={cb}",
            "fallback_url": None,
            "row_selector": "a", "row_class": "livescore-match-row",
            "home_selector": "span", "home_class": "livescore-team-name", "home_index": 0,
            "away_selector": "span", "home_class": "livescore-team-name", "home_index": 1,
            "pick_selector": "span", "pick_class": "tip-indicator-circle", "pick_index": 0,
            "use_scraperapi": False
        },
        "WinDrawWin": {
            "url": "https://www.windrawwin.com/predictions/today/",
            "fallback_url": "https://www.windrawwin.com/predictions/",
            "row_selector": "div", "row_class": "wtrow",
            "home_selector": "div", "home_class": "wttmobh", "home_index": 0,
            "away_selector": "div", "away_class": "wttmoba", "away_index": 0,
            "pick_selector": "div", "pick_class": "wtoddsdesc", "pick_index": 0,
            "use_scraperapi": True
        },
        "SoccerVista": {
            "url": "https://www.soccervista.com/",
            "fallback_url": "https://www.soccervista.com/predictions/",
            "row_selector": "tr", "row_class": "",
            "home_selector": "td", "home_class": "", "home_index": 0,
            "away_selector": "td", "home_class": "", "home_index": 1,
            "pick_selector": "td", "pick_class": "", "pick_index": 4,
            "use_scraperapi": True 
        },
        "Zulubet": {
            "url": "https://www.zulubet.com/",
            "fallback_url": "http://www.zulubet.com/",
            "row_selector": "tr", "row_class": "",
            "home_selector": "", "home_class": "", "home_index": 0,
            "away_selector": "", "away_class": "", "away_index": 0,
            "pick_selector": "", "pick_class": "", "pick_index": 0,
            "use_scraperapi": False 
        }
    }

class ConsensusEngine:
    def __init__(self, configs):
        self.configs = configs
        self.master_matrix = {}
        self.corner_stats = {} 
        self.diagnostics = {}

    def check_scraperapi_balance(self):
        if not SCRAPER_API_KEY: 
            return
        try:
            r = requests.get(f"http://api.scraperapi.com/account?api_key={SCRAPER_API_KEY}", timeout=15)
            if r.status_code == 200:
                data = r.json()
                limit = data.get("requestLimit", 1)
                used = data.get("requestCount", 0)
                remaining = limit - used
                self.diagnostics["ScraperAPICredits"] = f"🟢 OK ({remaining:,} remaining)"
            else:
                self.diagnostics["ScraperAPICredits"] = "🔴 FAILED (Check API Dashboard)"
        except Exception:
            self.diagnostics["ScraperAPICredits"] = "🔴 OFFLINE"

    def normalize_prediction(self, raw_text):
        text = str(raw_text).strip().lower()
        if text in ["home", "home win", "h"]: return "1"
        if text in ["draw", "x", "0", "d"]: return "X"
        if text in ["away", "away win", "a"]: return "2"

        if len(text) > 0:
            char = text[0]
            if char == "1" or char == "h": return "1"
            if char in ["x", "0", "d"]: return "X"
            if char == "2" or char == "a": return "2"
        return None

    def clean_team_name(self, name):
        cleaned = re.sub(r'(?i)\b(match preview|preview|results?)\b', '', str(name))
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

    def fetch_corners_sync(self):
        url = "https://www.totalcorner.com/match/today"
        for attempt in range(1, 3):
            try:
                if SCRAPER_API_KEY and attempt == 1:
                    proxy_url = f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={url}"
                    r = requests.get(proxy_url, timeout=35)
                else:
                    r = tls_requests.get(url, impersonate="chrome124", timeout=25)
                
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
                                        
                    self.diagnostics["CornersEngine"] = f"🟢 OK ({valid_corners} High-Corner Teams)"
                    return
                else:
                    time.sleep(1)
            except Exception:
                time.sleep(1)
                
        self.diagnostics["CornersEngine"] = "🔴 TIMEOUT/ERROR"

    def fetch_and_scrape_sync(self, site_name, cfg):
        max_attempts = 4
        req_timeout = 90 
        last_error_str = "TIMEOUT"
        target_url = cfg["url"]

        for attempt in range(1, max_attempts + 1):
            try:
                active_url = cfg.get("fallback_url") if (attempt >= 3 and cfg.get("fallback_url")) else target_url
                r = None
                
                if site_name == "WinDrawWin":
                    if attempt == 1 and SCRAPER_API_KEY:
                        r = requests.get("http://api.scraperapi.com/", params={"api_key": SCRAPER_API_KEY, "url": active_url, "premium": "true", "country_code": "uk"}, timeout=req_timeout)
                    elif attempt == 2 and SCRAPER_API_KEY:
                        r = requests.get("http://api.scraperapi.com/", params={"api_key": SCRAPER_API_KEY, "url": active_url, "premium": "true", "country_code": "us"}, timeout=req_timeout)
                    elif attempt == 3:
                        r = tls_requests.get(active_url, impersonate="chrome124", timeout=req_timeout)
                    elif attempt == 4 and SCRAPER_API_KEY:
                        r = requests.get("http://api.scraperapi.com/", params={"api_key": SCRAPER_API_KEY, "url": active_url, "premium": "true"}, timeout=req_timeout)
                
                elif site_name == "SoccerVista":
                    if attempt <= 3 and SCRAPER_API_KEY:
                        r = requests.get("http://api.scraperapi.com/", params={"api_key": SCRAPER_API_KEY, "url": active_url, "premium": "true", "render": "true"}, timeout=req_timeout)
                    else:
                        r = tls_requests.get(active_url, impersonate="chrome124", timeout=req_timeout)
                
                else:
                    use_proxy = cfg.get("use_scraperapi") and bool(SCRAPER_API_KEY)
                    if use_proxy:
                        r = requests.get("http://api.scraperapi.com/", params={"api_key": SCRAPER_API_KEY, "url": active_url, "premium": "true"}, timeout=req_timeout)
                    else:
                        r = tls_requests.get(active_url, impersonate="chrome124", timeout=req_timeout)

                if r is None:
                    continue

                if r.status_code == 200:
                    challenge_phrases = ["just a moment", "cf-browser-verification", "checking your browser", "turnstile", "ray id", "security check", "verify you are human", "enable javascript", "cloudflare"]
                    
                    if any(phrase in r.text.lower() for phrase in challenge_phrases) and len(r.text) < 150000:
                        last_error_str = "Cloudflare Challenge"
                        time.sleep(2)
                        continue

                    soup = BeautifulSoup(r.content, 'html.parser')
                    
                    if site_name == "WinDrawWin":
                        rows = soup.find_all("div", class_=re.compile(r"(wttr|wtrow|match-row|pr-match)", re.I))
                        if not rows:
                            child_elems = soup.find_all("div", class_=re.compile(r"(wttmobh|wttmoba|team1|team2)", re.I))
                            if child_elems:
                                rows = list(set([c.parent for c in child_elems if c.parent]))
                        if not rows:
                            rows = soup.find_all("tr")
                        if not rows:
                            raw_rows = soup.find_all("div", class_=re.compile(r'(row|match|fixture)', re.I))
                            rows = [row_elem for row_elem in raw_rows if len(row_elem.find_all('a')) >= 2 and len(row_elem.text) < 800]
                    elif site_name in ["SoccerVista", "Zulubet"]:
                        rows = soup.find_all("tr")
                        if not rows or len(rows) < 5:
                            raw_rows = soup.find_all("div", class_=re.compile(r'(predict|match|row|fixture|item)', re.I))
                            rows = [r for r in raw_rows if len(r.find_all('a')) >= 2 or len(r.find_all('div')) >= 2]
                    else:
                        row_target = cfg["row_class"]
                        rows = soup.find_all(cfg["row_selector"], class_=row_target)

                    if not rows:
                        page_title = soup.title.text.strip() if soup.title else "No Title"
                        last_error_str = f"0 Rows Parsed | Title: {page_title[:25]}"
                        time.sleep(1)
                        continue

                    valid_count = 0
                    skipped_count = 0

                    for row in rows:
                        try:
                            if self.is_match_active_or_played(row):
                                skipped_count += 1
                                continue

                            home, away, pick = None, None, None

                            if site_name == "WinDrawWin":
                                h_elem = row.find(class_=re.compile(r'(wttmobh|team1|h$|home)', re.I))
                                a_elem = row.find(class_=re.compile(r'(wttmoba|team2|a$|away)', re.I))
                                p_elem = row.find(class_=re.compile(r'(wtoddsdesc|mobpred|prd|pred|pick|tip|prediction)', re.I))

                                if h_elem and a_elem:
                                    home = h_elem.text
                                    away = a_elem.text
                                    if p_elem: pick = p_elem.text
                                    
                                if not home or not away:
                                    links = row.find_all("a")
                                    if len(links) >= 2:
                                        home = links[0].text.strip()
                                        away = links[1].text.strip()
                                        p_div = row.find(class_=re.compile(r'(prd|pred|odds)', re.I))
                                        if p_div and self.normalize_prediction(p_div.text):
                                            pick = p_div.text
                                        else:
                                            valid_picks = ["HOME", "DRAW", "AWAY", "1", "X", "2", "HOME WIN", "AWAY WIN", "H", "A", "D"]
                                            for text_chunk in row.stripped_strings:
                                                if text_chunk.strip().upper() in valid_picks:
                                                    pick = text_chunk.strip()
                                                    break
                                    else:
                                        tds = row.find_all(["td", "div"])
                                        for td in tds:
                                            txt = td.get_text(" ", strip=True)
                                            if " v " in txt or " vs " in txt:
                                                parts = re.split(r'\s+v\s+|\s+vs\s+', txt, maxsplit=1, flags=re.I)
                                                if len(parts) == 2:
                                                    home = parts[0].strip()
                                                    away = parts[1].strip()
                                                    break
                                        
                                        if home and away:
                                            valid_picks = ["HOME", "DRAW", "AWAY", "1", "X", "2", "HOME WIN", "AWAY WIN", "H", "A", "D"]
                                            for text_chunk in row.stripped_strings:
                                                if text_chunk.strip().upper() in valid_picks:
                                                    pick = text_chunk.strip()
                                                    break
                                            
                            elif site_name == "SoccerVista":
                                tds = row.find_all("td")
                                if len(tds) >= 3:
                                    raw_home = tds[1].text.strip()
                                    if len(tds) >= 4 and (re.search(r'\d+:\d+', tds[2].text) or tds[2].text.strip() in ["-", "vs", "v", ""]):
                                        raw_away = tds[3].text.strip()
                                    else:
                                        raw_away = tds[2].text.strip()
                                        
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
                                            
                                if not home or not away:
                                    text_chunks = [t.strip() for t in row.stripped_strings if t.strip()]
                                    for chunk in text_chunks:
                                        if " v " in chunk.lower() or " vs " in chunk.lower():
                                            parts = re.split(r'(?i)\s+v\s+|\s+vs\s+', chunk, maxsplit=1)
                                            if len(parts) == 2:
                                                home, away = parts[0].strip(), parts[1].strip()
                                        elif chunk in ["1", "X", "2", "1X", "X2", "12"]:
                                            pick = chunk

                            elif site_name == "Zulubet":
                                text_chunks = [t.strip() for t in row.stripped_strings if t.strip()]
                                for chunk in text_chunks:
                                    if " - " in chunk and len(chunk) > 5 and not re.search(r'\d+:\d+', chunk):
                                        parts = chunk.split(" - ", 1)
                                        if len(parts) == 2:
                                            home, away = parts[0].strip(), parts[1].strip()
                                    elif chunk.upper() in ["1", "X", "2", "1X", "X2", "12"]:
                                        pick = chunk.upper()
                                        
                                if not home or not away:
                                    tds = row.find_all("td")
                                    for td in tds:
                                        txt = td.text.strip()
                                        if " - " in txt and not re.search(r'\d+:\d+', txt):
                                            parts = txt.split(" - ", 1)
                                            if len(parts) == 2:
                                                home, away = parts[0].strip(), parts[1].strip()
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

                            if re.search(r'(?i)\s+vs?\s+', away_str) and len(home_str) < 4:
                                parts = re.split(r'(?i)\s+vs?\s+', away_str, maxsplit=1)
                                if len(parts) == 2:
                                    home_str, away_str = self.clean_team_name(parts[0]), self.clean_team_name(parts[1])

                            if re.search(r'(?i)\s+vs?\s+', home_str) and len(away_str) < 4:
                                parts = re.split(r'(?i)\s+vs?\s+', home_str, maxsplit=1)
                                if len(parts) == 2:
                                    home_str, away_str = self.clean_team_name(parts[0]), self.clean_team_name(parts[1])

                            if home_str and away_str and pick:
                                self.log_prediction_qa(site_name, home_str, away_str, pick)
                                valid_count += 1

                        except Exception:
                            continue

                    if valid_count > 0 or skipped_count > 0:
                        self.diagnostics[site_name] = f"🟢 OK ({valid_count} Upcoming | {skipped_count} Played)"
                        return

                elif r.status_code in [403, 500, 502, 503, 504, 429]:
                    last_error_str = f"HTTP {r.status_code}"
                    time.sleep(2)
                    continue
                else:
                    last_error_str = f"HTTP {r.status_code}"
                    time.sleep(2)
                    continue

            except requests.exceptions.ReadTimeout:
                last_error_str = "Error: ReadTimeout (ScraperAPI needs more time)"
                time.sleep(2)
                continue
            except Exception as e:
                last_error_str = f"Error: {type(e).__name__}"
                time.sleep(2)
                continue

        self.diagnostics[site_name] = f"🔴 FAILED ({last_error_str})"

    def process_consensus_signals(self):
        agreed_matches = []
        structured_tickets = []
        ai_input_data = []
        
        all_scrapers = ["Statarea", "Vitibet", "WinDrawWin", "SoccerVista", "Zulubet"]
        required_consensus = 3 

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

        return agreed_matches, structured_tickets, ai_input_data, required_consensus

    # ======================================================================
    # PURE PYTHON ALGORITHMIC TICKET BUILDER (NO AI / 0 CREDITS / INSTANT)
    # ======================================================================
    def build_algorithmic_ticket(self, ai_input_data, active_corner_teams):
        self.diagnostics["QuantEngine"] = "🟢 Algorithmic Ticket Generated"
        
        # Sort logic: Most backing sites first, least contradictions second
        def get_score(match_data):
            backing_count = len(match_data["backed_by"].split(" + "))
            contradiction_count = len(match_data["contradictions"])
            return (backing_count, -contradiction_count)

        sorted_matches = sorted(ai_input_data, key=get_score, reverse=True)
        
        final_picks = []
        
        # Pull the absolute best 4 matches from the consensus
        for m in sorted_matches:
            final_picks.append(f"{m['match']} ➔ {m['consensus_pick']}")
            if len(final_picks) == 4:
                break
                
        # If we have less than 4 matches, intelligently fill with high-probability corners
        if len(final_picks) < 4:
            for corner in active_corner_teams:
                corner_pick = f"{corner['match']} ➔ Over 8.5 Corners (Avg: {corner['avg_corners']})"
                if corner_pick not in final_picks:
                    final_picks.append(corner_pick)
                if len(final_picks) == 4:
                    break
                    
        if not final_picks:
            return "No high-conviction matches found today to safely build an elite ticket."
            
        # Format the perfect ticket output
        ticket_text = "🤖 **TITAN ALGORITHMIC TICKET** 🤖\n\n"
        ticket_text += "🛡️ **Ticket 1: Elite Ironclad (100% of Daily Stake)**\n"
        
        for pick in final_picks[:3]:
            ticket_text += f"• {pick}\n"
            
        if len(final_picks) > 3:
            ticket_text += f"🔄 [RESERVE PICK]: {final_picks[3]}\n"
            
        return ticket_text

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
            r = tls_requests.get(url, impersonate="chrome124", timeout=25)
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
        
        eat_tz = datetime.timezone(datetime.timedelta(hours=3))
        today_date_obj = datetime.datetime.now(datetime.timezone.utc).astimezone(eat_tz).date()

        for date_str, payload in memory.items():
            try:
                ticket_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
                days_old = (today_date_obj - ticket_date).days
            except Exception:
                days_old = 0

            tickets = payload if isinstance(payload, list) else payload.get("tickets", [])
            for t in tickets:
                if t.get("status") == "PENDING":
                    if days_old > 4:
                        t["status"] = "EXPIRED ⚪"
                        needs_save = True
                    else:
                        dates_to_check.add(date_str)

        if not dates_to_check:
            if needs_save: self.save_memory(memory)
            return []

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
        if not (TELEGRAM_TOKEN and TELEGRAM_CHAT_ID):
            print("Telegram credentials missing.")
            return

        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        chunk_size = 4000
        msg_chunks = [msg[i:i+chunk_size] for i in range(0, len(msg), chunk_size)]
        
        for chunk in msg_chunks:
            payload = {"chat_id": TELEGRAM_CHAT_ID, "text": chunk, "parse_mode": "Markdown"}
            try:
                r = requests.post(url, json=payload, timeout=25)
                if r.status_code != 200:
                    payload.pop("parse_mode", None)
                    r2 = requests.post(url, json=payload, timeout=25)
                    if r2.status_code != 200:
                        print(f"Telegram alert error: {r2.text}")
            except Exception as e:
                print(f"Telegram alert exception: {e}")
            time.sleep(1)

    async def run_pipeline(self):
        eat_time = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
        today_date = eat_time.strftime('%Y-%m-%d')
        current_hour = eat_time.hour

        memory = self.load_memory()
        today_payload = memory.get(today_date)

        is_already_locked = False
        if isinstance(today_payload, dict) and not FORCE_RUN:
            if today_payload.get("locked"):
                is_already_locked = True

        if is_already_locked:
            print(f"🔒 Data for {today_date} is already securely locked. Bypassing scrapers to conserve ScraperAPI tokens.")
            daily_data = memory[today_date]
            agreed_matches = daily_data.get("agreed_matches", [])
            ai_optimized_message = daily_data.get("ai_optimized_message")
            req_threshold = daily_data.get("req_threshold", 3)
            self.diagnostics["DailyLock"] = f"🟢 CACHED (Tokens Saved for {today_date})"
        else:
            print(f"🔓 Scraping data for {today_date} and building Algorithmic Ticket...")
            self.check_scraperapi_balance()
            loop = asyncio.get_running_loop()
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
                tasks = [loop.run_in_executor(pool, self.fetch_and_scrape_sync, n, c) for n, c in self.configs.items()]
                tasks.append(loop.run_in_executor(pool, self.fetch_corners_sync))
                await asyncio.gather(*tasks)

            agreed_matches, structured_tickets, ai_input_data, req_threshold = self.process_consensus_signals()

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
                # FIX: Generating ticket using pure, instant Python logic
                ai_optimized_message = self.build_algorithmic_ticket(ai_input_data, active_corner_teams)

            should_lock = (current_hour >= 5) and (ai_optimized_message is not None or not ai_input_data)

            if not FORCE_RUN:
                memory[today_date] = {
                    "locked": should_lock,
                    "agreed_matches": agreed_matches,
                    "ai_optimized_message": ai_optimized_message,
                    "req_threshold": req_threshold,
                    "tickets": structured_tickets
                }
                self.save_memory(memory)
            
            if should_lock:
                self.diagnostics["DailyLock"] = f"🟢 LOCKED NEW DATA FOR {today_date}"
            else:
                self.diagnostics["DailyLock"] = f"⏳ PREVIEW (Will Lock At 05:00 EAT)"

        settled_reports = self.settle_pending_tickets(memory)

        if not is_already_locked or settled_reports:
            msg = f"🤝 **RAW CONSENSUS DATA ({req_threshold}+ SITES AGREEMENT)** 🤝\n\n"
            if not agreed_matches:
                msg += f"No matches found with {req_threshold}+ sites in agreement today.\n\n"
            else:
                for match in agreed_matches: msg += f"{match}\n"
                    
            if settled_reports:
                msg += "📊 **SETTLED RESULTS (Newly Finalized)** 📊\n\n"
                for rep in settled_reports: msg += f"{rep}\n"
                msg += "\n"

            msg += "⚙️ **SCRAPER STATUS** ⚙️\n"
            for site, status in self.diagnostics.items(): msg += f"↳ {site}: {status}\n"

            self.send_telegram_alert(msg)

            if ai_optimized_message and not is_already_locked:
                time.sleep(1.5)
                self.send_telegram_alert(ai_optimized_message)

if __name__ == "__main__":
    live_configs = get_dynamic_configs()
    asyncio.run(ConsensusEngine(live_configs).run_pipeline())
