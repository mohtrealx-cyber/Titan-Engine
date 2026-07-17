import os
import re
import json
import time
import asyncio
import datetime
import difflib
import random
from bs4 import BeautifulSoup
import concurrent.futures
from curl_cffi import requests as tls_requests

# ==============================================================================
# CONFIGURATION & SECURE ROUTING FALLBACKS
# ==============================================================================
TELEGRAM_TOKEN = os.environ.get("QUANT_TELEGRAM_TOKEN") or os.environ.get("TRACKER_TRACKER_TELEGRAM_TOKEN") or os.environ.get("TRACKER_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("QUANT_TELEGRAM_CHAT_ID") or os.environ.get("TRACKER_TRACKER_TELEGRAM_CHAT_ID") or os.environ.get("TRACKER_TELEGRAM_CHAT_ID")

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
            "pick_selector": "div", "pick_class": "type1", "pick_index": 0
        },
        "Vitibet": {
            "url": f"https://www.vitibet.com/index.php?clanek=quicktips&sekce=fotbal&lang=en&cb={cb}", 
            "row_selector": "a", "row_class": "livescore-match-row", 
            "home_selector": "span", "home_class": "livescore-team-name", "home_index": 0, 
            "away_selector": "span", "away_class": "livescore-team-name", "away_index": 1, 
            "pick_selector": "span", "pick_class": "tip-indicator-circle", "pick_index": 0
        },
        "Forebet": {
            "url": "https://www.forebet.com/en/football-predictions-for-today", 
            "row_selector": "div", "row_class": "rcnt", 
            "home_selector": "span", "home_class": "homeTeam", "home_index": 0, 
            "away_selector": "span", "away_class": "awayTeam", "away_index": 0, 
            "pick_selector": "span", "pick_class": "forepr", "pick_index": 0
        }
    }

class ZenRowsConsensusEngine:
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

        # FUZZY MATCHING TO GROUP SIMILAR TEAM NAMES ACROSS DIFFERENT SITES
        for existing_key in self.master_matrix.keys():
            similarity = difflib.SequenceMatcher(None, raw_match_key.lower(), existing_key.lower()).ratio()
            if similarity >= 0.75:  
                final_key = existing_key
                break

        if final_key not in self.master_matrix: self.master_matrix[final_key] = []
        
        existing_sites = [entry[0] for entry in self.master_matrix[final_key]]
        if site_name not in existing_sites:
            self.master_matrix[final_key].append((site_name, normalized_pick))

    # ==========================================================
    # FORECASTER: LIVE SCRAPE ENGINE
    # ==========================================================
    def fetch_and_scrape_sync(self, site_name, cfg):
        try:
            print(f"   [Scraper] Extracting data from {site_name}...")
            
            # --- STEALTH HEADERS & BROWSER ROULETTE ---
            # Forebet monitors static fingerprints, so we rotate them dynamically
            browsers = ["chrome110", "chrome116", "chrome120", "safari15_3", "safari15_5", "edge101"]
            target_browser = random.choice(browsers)
            
            stealth_headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
                "Referer": "https://www.google.com/"
            }
            
            r = tls_requests.get(
                cfg["url"], 
                headers=stealth_headers, 
                impersonate=target_browser, 
                timeout=30
            )
            
            if r.status_code != 200: 
                self.diagnostics[site_name] = f"🔴 FAILED (HTTP {r.status_code})"
                return
                
            soup = BeautifulSoup(r.content, 'html.parser')
            rows = soup.find_all(cfg["row_selector"], class_=cfg["row_class"])
            
            if not rows:
                page_title = soup.title.string.strip() if soup.title and soup.title.string else "No Title Found"
                self.diagnostics[site_name] = f"🟡 BLOCKED (Title: {page_title[:25]}...)"
                return
                
            valid_count = 0
            skipped_count = 0
            
            for row in rows:
                try: 
                    # Drop matches that have already played or are currently live
                    if self.is_match_active_or_played(row):
                        skipped_count += 1
                        continue

                    # Filter out scoreline regex to prevent grabbing finished matches
                    row_text = row.text.upper()
                    if re.search(r'\d+\s*[-:]\s*\d+', row_text):
                        possible_scores = re.findall(r'\b\d+\s*-\s*\d+\b', row_text)
                        if possible_scores:
                            skipped_count += 1
                            continue

                    home = row.find_all(cfg["home_selector"], class_=cfg["home_class"])[cfg["home_index"]].text
                    away = row.find_all(cfg["away_selector"], class_=cfg["away_class"])[cfg["away_index"]].text
                    pick = row.find_all(cfg["pick_selector"], class_=cfg["pick_class"])[cfg["pick_index"]].text
                    
                    if home and away and pick:
                        self.log_prediction_qa(site_name, home, away, pick)
                        valid_count += 1
                        
                except Exception: 
                    continue
                
            self.diagnostics[site_name] = f"🟢 OK ({valid_count} Upcoming | {skipped_count} Played)"
                
        except Exception as e: 
            self.diagnostics[site_name] = f"🔴 TIMEOUT/ERROR: {e}"
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

    # ==========================================================
    # ACCOUNTANT: MEMORY & SETTLEMENT ENGINE
    # ==========================================================
    def save_tickets_to_memory(self, new_tickets):
        file_path = "pending_tickets.json"
        memory = {}
        if os.path.exists(file_path):
            try:
                with open(file_path, "r") as f:
                    memory = json.load(f)
            except Exception: pass
            
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

    def settle_pending_tickets(self):
        memory_path = "pending_tickets.json"
        if not os.path.exists(memory_path): return []
        
        try:
            with open(memory_path, "r") as f:
                memory = json.load(f)
        except Exception: return []
            
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
                        except Exception: pass
                            
        if needs_save:
            try:
                with open(memory_path, "w") as f:
                    json.dump(memory, f, indent=4)
            except Exception: pass
                
        return settled_reports

    def send_telegram_alert(self, msg):
        if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
            print("   [Telegram] Dispatching slip via Telegram API...")
            try:
                tls_requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                    json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, 
                    impersonate="chrome120", timeout=10
                )
            except Exception as e:
                print(f"   [Telegram] Dispatch Failed: {e}")
        else:
            print(msg)

    async def run_pipeline(self):
        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            await asyncio.gather(*[loop.run_in_executor(pool, self.fetch_and_scrape_sync, n, c) for n, c in self.configs.items()])
        
        consensus_list, structured_tickets = self.process_consensus_signals()
        
        if structured_tickets:
            self.save_tickets_to_memory(structured_tickets)
            
        settled_reports = self.settle_pending_tickets()
        
        msg = "🤝 **CONSENSUS ENGINE** 🤝\n*(Statarea + Vitibet + Forebet)*\n\n"
        
        if not consensus_list:
            msg += "No matches found with 2+ sites in agreement today.\n\n"
        else:
            msg += f"🔥 **LOCKED UPCOMING CONSENSUS ({len(consensus_list)})** 🔥\n\n"
            for match in consensus_list: msg += f"{match}\n"
            
            total_matches = len(consensus_list)
            if total_matches >= 2:
                half_idx = total_matches // 2
                msg += "💰 **RECOMMENDED STAKING PLAN (250 KES TOTAL)** 💰\n"
                msg += f"🎟️ **Ticket 1 (Mega Acca - All {total_matches} Matches):** 50 KES\n"
                msg += f"🎟️ **Ticket 2 (Half 1 - First {half_idx} Matches):** 100 KES\n"
                msg += f"🎟️ **Ticket 3 (Half 2 - Last {total_matches - half_idx} Matches):** 100 KES\n\n"
            else:
                msg += "💰 **RECOMMENDED STAKING PLAN:**\n"
                msg += "🎟️ **Single Ticket:** 250 KES\n\n"
                
        if settled_reports:
            msg += "📊 **SETTLED RESULTS (Newly Finalized)** 📊\n\n"
            for rep in settled_reports: msg += f"{rep}\n"
            msg += "\n"
                
        msg += "⚙️ **SCRAPER STATUS** ⚙️\n"
        for site, status in self.diagnostics.items(): msg += f"↳ {site}: {status}\n"
                
        self.send_telegram_alert(msg)

if __name__ == "__main__":
    print("Initiating Consensus Engine (Statarea + Vitibet + Forebet)...")
    live_configs = get_dynamic_configs()
    asyncio.run(ZenRowsConsensusEngine(live_configs).run_pipeline())
    print("Routine Complete.")
