import os
import time
import asyncio
import csv
import datetime
from bs4 import BeautifulSoup
import concurrent.futures
from curl_cffi import requests as tls_requests

# ==============================================================================
# 1. CONFIGURATION & SECURITY
# ==============================================================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

ACTIVE_STRATEGY = "Titan"
CSV_FILE_PATH = "titan_performance_history.csv"

def get_dynamic_configs():
    """Generates live URLs for TODAY only to bypass stale cached pages."""
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

    def normalize_prediction(self, raw_text):
        text = str(raw_text).strip().lower()
        matrix = {"1": ["1", "home", "home win"], "X": ["x", "draw"], "2": ["2", "away", "away win"], "OVER 1.5": ["o1.5", "over 1.5", "+1.5"], "OVER 2.5": ["o2.5", "over 2.5", "+2.5"], "UNDER 2.5": ["u2.5", "under 2.5", "-2.5"], "GG": ["gg", "btts", "yes"]}
        for tag, vars in matrix.items():
            if text in vars: return tag
        return None

    def clean_team_name(self, name): return name.strip().title()

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
            if r.status_code != 200: return
            for row in BeautifulSoup(r.content, 'html.parser').find_all(cfg["row_selector"], class_=cfg["row_class"]):
                try: self.log_prediction_qa(site_name, row.find_all(cfg["home_selector"], class_=cfg["home_class"])[cfg["home_index"]].text, row.find_all(cfg["away_selector"], class_=cfg["away_class"])[cfg["away_index"]].text, row.find_all(cfg["pick_selector"], class_=cfg["pick_class"])[cfg["pick_index"]].text)
                except: continue
        except: return

    def process_signals(self):
        daily_sures, jackpot_builders, csv_rows = [], [], []
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        for match, listings in self.master_matrix.items():
            if len(listings) == 0: continue
            
            prediction_weights = {}
            for site, pick in listings:
                prediction_weights[pick] = prediction_weights.get(pick, 0) + 1

            top_pick = max(prediction_weights, key=prediction_weights.get)
            
            # Simple percentage based on how many sites agree
            confidence_pct = (prediction_weights[top_pick] / len(listings)) * 100

            csv_rows.append([timestamp, ACTIVE_STRATEGY, match, top_pick, f"{confidence_pct:.0f}%", str([f"{s}:{p}" for s, p in listings]), ""])

            if confidence_pct >= 99.9: 
                daily_sures.append(f"• {match} ➔ {top_pick}")
            else: 
                jackpot_builders.append(f"• {match} ➔ {top_pick} ({confidence_pct:.0f}%)")

        return daily_sures, jackpot_builders, csv_rows

    def send_telegram_alert(self, msg):
        if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
            tls_requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, impersonate="chrome120", timeout=10)

    async def run_pipeline(self):
        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            await asyncio.gather(*[loop.run_in_executor(pool, self.fetch_and_scrape_sync, n, c) for n, c in self.configs.items()])
        
        sures, jackpots, rows = self.process_signals()
        
        if not sures and not jackpots: 
            self.send_telegram_alert("🛡️ TITAN ENGINE: Scrape complete, but zero matches found for today. Bankroll protected.")
            return
        
        # Formatting exactly to your preferred Mega-Ticket layout
        msg = f"🎫 TITAN ENGINE: MEGA-TICKET 🎫\n\n"
        if sures:
            msg += "🔥 DAILY SURE BETS (100%)\n"
            for b in sures: msg += f"{b}\n"
            msg += "\n"
        if jackpots:
            msg += "🎟️ DAILY JACKPOT BUILDER\n"
            for b in jackpots: msg += f"{b}\n"
            msg += "\n"
            
        msg += f"📈 Strategy: {ACTIVE_STRATEGY}"
        
        self.send_telegram_alert(msg)

if __name__ == "__main__":
    live_configs = get_dynamic_configs()
    asyncio.run(TitanMasterEngine(live_configs).run_pipeline())
