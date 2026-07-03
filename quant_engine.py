import os
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
        "ZuluBet": {
            "url": "https://www.zulubet.com/", 
            "row_selector": "tr", "row_class": "", 
            "home_selector": "td", "home_class": "", "home_index": 1, 
            "away_selector": "td", "away_class": "", "away_index": 2, 
            "pick_selector": "td", "pick_class": "", "pick_index": 4 
        }
    }

class OpenConsensusEngine:
    def __init__(self, configs):
        self.configs = configs
        self.master_matrix = {}
        self.system_stake = "100 KES"
        self.diagnostics = {} 

    def normalize_prediction(self, raw_text):
        text = str(raw_text).strip().lower()
        matrix = {"1": ["1", "home", "home win"], "X": ["x", "draw"], "2": ["2", "away", "away win"]}
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
            
            if r.status_code != 200: 
                self.diagnostics[site_name] = f"🔴 FAILED (HTTP {r.status_code})"
                return
                
            soup = BeautifulSoup(r.content, 'html.parser')
            
            # ==========================================================
            # BULLETPROOF ZULUBET PARSER
            # ==========================================================
            if site_name == "ZuluBet":
                rows = soup.find_all("tr")
                valid_rows = 0
                for row in rows:
                    cols = row.find_all("td")
                    if len(cols) >= 8 and "aver_odds" not in str(row):
                        try:
                            home = cols[1].text.strip()
                            away = cols[2].text.strip()
                            pick = None
                            
                            # Brute-force HTML string check to avoid NoneType errors
                            for col in cols:
                                col_html = str(col).lower()
                                if 'green' in col_html or '#008000' in col_html:
                                    clean_text = col.text.strip().upper()
                                    if clean_text in ["1", "X", "2"]:
                                        pick = clean_text
                                        break
                                        
                            if home and away and pick:
                                self.log_prediction_qa(site_name, home, away, pick)
                                valid_rows += 1
                        except: continue
                
                self.diagnostics[site_name] = f"🟢 OK ({valid_rows} Matches)" if valid_rows > 0 else "🟡 BLOCKED (0 Rows Found)"
                return

            # ==========================================================
            # STANDARD PARSER (Statarea & Vitibet)
            # ==========================================================
            rows = soup.find_all(cfg["row_selector"], class_=cfg["row_class"])
            if not rows:
                self.diagnostics[site_name] = "🟡 BLOCKED (0 Rows Found)"
                return
                
            self.diagnostics[site_name] = f"🟢 OK ({len(rows)} Matches)"
            
            for row in rows:
                try: 
                    self.log_prediction_qa(
                        site_name, 
                        row.find_all(cfg["home_selector"], class_=cfg["home_class"])[cfg["home_index"]].text, 
                        row.find_all(cfg["away_selector"], class_=cfg["away_class"])[cfg["away_index"]].text, 
                        row.find_all(cfg["pick_selector"], class_=cfg["pick_class"])[cfg["pick_index"]].text
                    )
                except: continue
        except Exception as e: 
            self.diagnostics[site_name] = "🔴 TIMEOUT/ERROR"
            return

    def process_consensus_signals(self):
        agreed_matches = []
        
        for match, listings in self.master_matrix.items():
            if len(listings) < 2: continue
            
            prediction_weights = {}
            sites_backing = {}
            for site, pick in listings: 
                prediction_weights[pick] = prediction_weights.get(pick, 0) + 1
                if pick not in sites_backing:
                    sites_backing[pick] = []
                sites_backing[pick].append(site)
                
            top_pick = max(prediction_weights, key=prediction_weights.get)
            agreement_count = prediction_weights[top_pick]
            
            # Requires 2 or more sites to agree
            if agreement_count >= 2:
                backing_sites_str = " + ".join(sites_backing[top_pick])
                agreed_matches.append(
                    f"• **{match}** ➔ {top_pick}\n"
                    f"  ↳ ✅ Backed by: `{backing_sites_str}`\n"
                    f"  ↳ 💰 `[Stake: {self.system_stake}]`\n"
                )

        return agreed_matches

    def send_telegram_alert(self, msg):
        if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
            tls_requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, 
                impersonate="chrome120", 
                timeout=10
            )

    async def run_pipeline(self):
        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            await asyncio.gather(*[loop.run_in_executor(pool, self.fetch_and_scrape_sync, n, c) for n, c in self.configs.items()])
        
        consensus_list = self.process_consensus_signals()
        
        msg = "🤝 **OPEN-DATA CONSENSUS ENGINE** 🤝\n"
        msg += "*(Statarea + Vitibet + ZuluBet)*\n\n"
        
        if not consensus_list:
            msg += "No matches found with 2+ sites in agreement today.\n\n"
        else:
            msg += f"🔥 **LOCKED CONSENSUS ({len(consensus_list)})** 🔥\n\n"
            for match in consensus_list: 
                msg += f"{match}\n"
                
        msg += "⚙️ **SCRAPER STATUS** ⚙️\n"
        for site, status in self.diagnostics.items():
            msg += f"↳ {site}: {status}\n"
                
        self.send_telegram_alert(msg)

if __name__ == "__main__":
    live_configs = get_dynamic_configs()
    asyncio.run(OpenConsensusEngine(live_configs).run_pipeline())
