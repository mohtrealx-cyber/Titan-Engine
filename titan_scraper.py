import os
import asyncio
import csv
import datetime
from bs4 import BeautifulSoup
from collections import Counter
import concurrent.futures
from curl_cffi import requests as tls_requests

# ==============================================================================
# CONFIGURATION & SECURITY
# ==============================================================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# --- NEW: BANKROLL & STRATEGY SETTINGS ---
CURRENT_BANKROLL = 10000   # Set your total bankroll here in KShs
ACTIVE_STRATEGY = "Titan"  # Change to Fortress, Velocity, or Lone Wolf if running different models

TARGET_CONFIG = {
    "Statarea": {
        "url": "https://www.statarea.com/predictions",
        "row_selector": "div", "row_class": "matchrow",
        "home_selector": "div", "home_class": "name", "home_index": 0,
        "away_selector": "div", "away_class": "name", "away_index": 1,
        "pick_selector": "div", "pick_class": "type1", "pick_index": 0
    },
    "PredictZ": {
        "url": "https://www.predictz.com/predictions/",
        "row_selector": "div", "row_class": "pttr",
        "home_selector": "div", "home_class": "pttmobh", "home_index": 0,
        "away_selector": "div", "away_class": "pttmoba", "away_index": 0,
        "pick_selector": "div", "pick_class": "ptoddsdesc", "pick_index": 0
    },
    "Vitibet": {
        "url": "https://www.vitibet.com/index.php?clanek=quicktips&sekce=fotbal&lang=en",
        "row_selector": "a", "row_class": "livescore-match-row",
        "home_selector": "span", "home_class": "livescore-team-name", "home_index": 0,
        "away_selector": "span", "away_class": "livescore-team-name", "away_index": 1,
        "pick_selector": "span", "pick_class": "tip-indicator-circle", "pick_index": 0
    }
}

class TitanAdvancedEngine:
    def __init__(self, configs):
        self.configs = configs
        self.master_matrix = {}

    def calculate_stakes(self, bankroll):
        """Calculates the 1%, 2%, and 3% stakes based on the current bankroll."""
        conservative = bankroll * 0.01
        standard = bankroll * 0.02
        aggressive = bankroll * 0.03
        return conservative, standard, aggressive

    def send_telegram_alert(self, message):
        """Dispatches real-time alerts to your Telegram bot."""
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
            print("[!] Error: Telegram keys are missing from the environment vault.")
            return
            
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        try:
            tls_requests.post(url, json=payload, impersonate="chrome120", timeout=10)
        except Exception as e:
            print(f"[!] Bot Alert Failed: {e}")

    def clean_team_name(self, name):
        name = name.strip().lower()
        mapping = {
            "man utd": "manchester united", "chelsea fc": "chelsea",
            "lfc": "liverpool", "bosnia and herzegovina": "bosnia-herzegovina"
        }
        return mapping.get(name, name).title()

    def log_prediction(self, home, away, prediction):
        match_key = f"{self.clean_team_name(home)} vs {self.clean_team_name(away)}"
        if match_key not in self.master_matrix:
            self.master_matrix[match_key] = []
        self.master_matrix[match_key].append(prediction.strip().upper())

    def fetch_and_scrape_sync(self, site_name, cfg):
        try:
            response = tls_requests.get(cfg["url"], impersonate="chrome120", timeout=20)
            if response.status_code != 200: return site_name, 0
            soup = BeautifulSoup(response.content, 'html.parser')
            rows = soup.find_all(cfg["row_selector"], class_=cfg["row_class"])
            count = 0
            for row in rows:
                try:
                    h = row.find_all(cfg["home_selector"], class_=cfg["home_class"])[cfg["home_index"]].text
                    a = row.find_all(cfg["away_selector"], class_=cfg["away_class"])[cfg["away_index"]].text
                    p = row.find_all(cfg["pick_selector"], class_=cfg["pick_class"])[cfg["pick_index"]].text
                    if h and a and p:
                        self.log_prediction(h, a, p)
                        count += 1
                except: continue
            return site_name, count
        except: return site_name, 0

    def save_to_history(self):
        filename = "betting_performance_history.csv"
        with open(filename, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for match, picks in self.master_matrix.items():
                counter = Counter(picks)
                top, occ = counter.most_common(1)[0]
                conf = (occ / len(picks)) * 100
                # Appended ACTIVE_STRATEGY to the history log
                writer.writerow([datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), ACTIVE_STRATEGY, match, top, f"{conf}%", str(picks)])

    async def run_pipeline(self):
        print("[+] Launching Titan Consensus Engine...")
        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            await asyncio.gather(*[loop.run_in_executor(pool, self.fetch_and_scrape_sync, n, c) for n, c in self.configs.items()])
        self.save_to_history()
        self.display_consensus()

    def display_consensus(self):
        print("\n" + "="*70 + "\n TITAN HIGH-CONFIDENCE SIGNALS \n" + "="*70)
        found_strong = False
        cons, std, agg = self.calculate_stakes(CURRENT_BANKROLL)
        
        for match, picks in self.master_matrix.items():
            counter = Counter(picks)
            top, occ = counter.most_common(1)[0]
            if len(picks) > 1:
                conf = (occ / len(picks)) * 100
                
                # Upgraded Professional Telegram Message
                msg = (
                    f"🚨 [STRONG] SIGNAL DETECTED 🚨\n\n"
                    f"⚙️ Strategy Engine: {ACTIVE_STRATEGY}\n"
                    f"⚽ Match: {match}\n"
                    f"🎯 Verdict: {top} ({conf:.0f}% Consensus)\n\n"
                    f"💰 RECOMMENDED STAKING (KShs):\n"
                    f"• Conservative (1%): {cons:,.0f} KShs\n"
                    f"• Standard (2%): {std:,.0f} KShs\n"
                    f"• Aggressive (3%): {agg:,.0f} KShs\n\n"
                    f"Execute on Betika or Bangbet."
                )
                
                print(f"[STRONG] {match} - Verdict: {top} ({conf:.0f}%)")
                self.send_telegram_alert(msg)
                found_strong = True
                
        if not found_strong: print("[!] No high-confidence signals found.")

if __name__ == "__main__":
    engine = TitanAdvancedEngine(TARGET_CONFIG)
    asyncio.run(engine.run_pipeline())
