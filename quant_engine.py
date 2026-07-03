import os
import re
import json
import time
import asyncio
import datetime
from bs4 import BeautifulSoup
import concurrent.futures
from curl_cffi import requests as tls_requests

# ==============================================================================
# CONFIGURATION & SECURE ROUTING FALLBACKS
# ==============================================================================
TELEGRAM_TOKEN = os.environ.get("QUANT_TELEGRAM_TOKEN") or os.environ.get("TRACKER_TRACKER_TELEGRAM_TOKEN") or os.environ.get("TRACKER_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("QUANT_TELEGRAM_CHAT_ID") or os.environ.get("TRACKER_TRACKER_TELEGRAM_CHAT_ID") or os.environ.get("TRACKER_TELEGRAM_CHAT_ID")
ZENROWS_API_KEY = os.environ.get("ZEN_PROXY_KEY") 

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
            "use_zenrows": False
        },
        "Vitibet": {
            "url": f"https://www.vitibet.com/index.php?clanek=quicktips&sekce=fotbal&lang=en&cb={cb}", 
            "row_selector": "a", "row_class": "livescore-match-row", 
            "home_selector": "span", "home_class": "livescore-team-name", "home_index": 0, 
            "away_selector": "span", "away_class": "livescore-team-name", "away_index": 1, 
            "pick_selector": "span", "pick_class": "tip-indicator-circle", "pick_index": 0,
            "use_zenrows": False
        },
        "PredictZ": {
            "url": "https://www.predictz.com/predictions/today/", 
            "row_selector": "div", "row_class": "pttr", 
            "home_selector": "div", "home_class": "pttmobh", "home_index": 0, 
            "away_selector": "div", "away_class": "pttmoba", "away_index": 0, 
            "pick_selector": "div", "pick_class": "ptoddsdesc", "pick_index": 0,
            "use_zenrows": True 
        }
    }

class ZenRowsConsensusEngine:
    def __init__(self, configs):
        self.configs = configs
        self.master_matrix = {}
        self.system_stake = "100 KES"
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
        match_key = f"{self.clean_team_name(home)} vs {self.clean_team_name(away)}"
        if match_key not in self.master_matrix: self.master_matrix[match_key] = []
        self.master_matrix[match_key].append((site_name, normalized_pick))

    def fetch_and_scrape_sync(self, site_name, cfg):
        try:
            if cfg.get("use_zenrows") and ZENROWS_API_KEY:
                proxy_url = "https://api.zenrows.com/v1/"
                params = {
                    "apikey": ZENROWS_API_KEY,
                    "url": cfg["url"],
                    "js_render": "true", 
                    "wait": "3000",
                    "antibot": "true" 
                }
                r = tls_requests.get(proxy_url, params=params, timeout=60)
            else:
                if cfg.get("use_zenrows") and not ZENROWS_API_KEY:
                    self.diagnostics[site_name] = "🔴 MISSING ZEN_PROXY_KEY"
                    return
                r = tls_requests.get(cfg["url"], impersonate="chrome120", timeout=20)
            
            if r.status_code != 200: 
                self.diagnostics[site_name] = f"🔴 FAILED (HTTP {r.status_code})"
                return
                
            soup = BeautifulSoup(r.content, 'html.parser')
            row_target = re.compile("pttr|ptrow") if site_name == "PredictZ" else cfg["row_class"]
            rows = soup.find_all(cfg["row_selector"], class_=row_target)
            
            if not rows:
                page_title = soup.title.string.strip() if soup.title and soup.title.string else "No Title Found"
                if "moment" in page_title.lower() or "cloudflare" in page_title.lower():
                    self.diagnostics[site_name] = f"🟡 BLOCKED (Cloudflare Checkbox Trap)"
                else:
                    self.diagnostics[site_name] = f"🟡 BLOCKED (Title: {page_title[:25]}...)"
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
                                if p_div:
                                    pick = p_div.text
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
        structured_tickets = [] # For the memory file
        
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
                
                # Standard Telegram format
                agreed_matches.append(
                    f"• **{match}** ➔ {top_pick}\n"
                    f"  ↳ ✅ Backed by: `{backing_sites_str}`\n"
                    f"  ↳ 💰 `[Stake: {self.system_stake}]`\n"
                )
                
                # Structured JSON format for memory
                structured_tickets.append({
                    "match": match,
                    "prediction": top_pick,
                    "backed_by": sites_backing[top_pick],
                    "status": "PENDING",
                    "home_score": "-",
                    "away_score": "-"
                })
                
        return agreed_matches, structured_tickets

    # ==========================================================
    # PHASE 1: DIGITAL NOTEBOOK (SAVES MATCHES TO JSON)
    # ==========================================================
    def save_tickets_to_memory(self, new_tickets):
        file_path = "pending_tickets.json"
        try:
            if os.path.exists(file_path):
                with open(file_path, "r") as f:
                    memory = json.load(f)
            else:
                memory = {}
                
            # Use East Africa Time (EAT) for the date key
            today_date = (datetime.datetime.utcnow() + datetime.timedelta(hours=3)).strftime('%Y-%m-%d')
            
            # Save or overwrite today's tickets in the dictionary
            memory[today_date] = new_tickets
            
            with open(file_path, "w") as f:
                json.dump(memory, f, indent=4)
        except Exception as e:
            pass

    def send_telegram_alert(self, msg):
        if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
            tls_requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, 
                impersonate="chrome120", timeout=10
            )

    async def run_pipeline(self):
        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            await asyncio.gather(*[loop.run_in_executor(pool, self.fetch_and_scrape_sync, n, c) for n, c in self.configs.items()])
        
        consensus_list, structured_tickets = self.process_consensus_signals()
        
        # Save matches to memory notebook before ending the script
        if structured_tickets:
            self.save_tickets_to_memory(structured_tickets)
        
        msg = "🤝 **ZENROWS CONSENSUS ENGINE** 🤝\n*(Statarea + Vitibet + PredictZ)*\n\n"
        
        if not consensus_list:
            msg += "No matches found with 2+ sites in agreement today.\n\n"
        else:
            msg += f"🔥 **LOCKED UPCOMING CONSENSUS ({len(consensus_list)})** 🔥\n\n"
            for match in consensus_list: msg += f"{match}\n"
                
        msg += "⚙️ **SCRAPER STATUS** ⚙️\n"
        for site, status in self.diagnostics.items(): msg += f"↳ {site}: {status}\n"
                
        self.send_telegram_alert(msg)

if __name__ == "__main__":
    live_configs = get_dynamic_configs()
    asyncio.run(ZenRowsConsensusEngine(live_configs).run_pipeline())
