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
ZENROWS_API_KEY = os.environ.get("ZENROWS_API_KEY") # Ensure this is in GitHub Secrets

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
            "url": f"https://www.predictz.com/predictions/today/?cb={cb}", 
            "row_selector": "div", "row_class": "pttr", 
            "home_selector": "div", "home_class": "pttmobh", "home_index": 0, 
            "away_selector": "div", "away_class": "pttmoba", "away_index": 0, 
            "pick_selector": "div", "pick_class": "ptoddsdesc", "pick_index": 0,
            "use_zenrows": True # Triggers the ZenRows API bypass
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
        if len(text) > 0: text = text[0]
        matrix = {"1": ["1", "home"], "X": ["x", "draw", "0"], "2": ["2", "away"]}
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
            # ==========================================================
            # THE ZENROWS CLOUDFLARE BYPASS
            # ==========================================================
            if cfg.get("use_zenrows") and ZENROWS_API_KEY:
                proxy_url = "https://api.zenrows.com/v1/"
                params = {
                    "apikey": ZENROWS_API_KEY,
                    "url": cfg["url"],
                    "js_render": "true", # Forces Cloudflare JS challenge to solve
                    "premium_proxy": "true" 
                }
                # ZenRows handles the impersonation, so we use a standard get
                r = tls_requests.get(proxy_url, params=params, timeout=60)
            else:
                # Open sites continue to use the standard TLS impersonation
                if cfg.get("use_zenrows") and not ZENROWS_API_KEY:
                    self.diagnostics[site_name] = "🔴 MISSING ZENROWS KEY"
                    return
                r = tls_requests.get(cfg["url"], impersonate="chrome120", timeout=20)
            
            if r.status_code != 200: 
                self.diagnostics[site_name] = f"🔴 FAILED (HTTP {r.status_code})"
                return
                
            soup = BeautifulSoup(r.content, 'html.parser')
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
        
        msg = "🤝 **ZENROWS CONSENSUS ENGINE** 🤝\n"
        msg += "*(Statarea + Vitibet + PredictZ)*\n\n"
        
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
    asyncio.run(ZenRowsConsensusEngine(live_configs).run_pipeline())
