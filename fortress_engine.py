import os
import asyncio
import csv
import datetime
from bs4 import BeautifulSoup
from collections import Counter
import concurrent.futures
from curl_cffi import requests as tls_requests

# ==============================================================================
# 1. CONFIGURATION & SECURITY
# ==============================================================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

ACTIVE_STRATEGY = "Fortress"
CSV_FILE_PATH = "fortress_performance_history.csv"

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

class FortressMasterEngine:
    def __init__(self, configs):
        self.configs = configs
        self.master_matrix = {}
        self.dynamic_weights = self.calculate_dynamic_weights() # Triggers the AI learning loop

    # ==============================================================================
    # 2. MACHINE LEARNING FEEDBACK LOOP (SELF-TUNING)
    # ==============================================================================
    def calculate_dynamic_weights(self):
        """Reads graded historical data and mathematically adjusts trust scores."""
        weights = {"Statarea": 1.0, "PredictZ": 1.0, "Vitibet": 1.0}
        
        if not os.path.exists(CSV_FILE_PATH):
            print("[*] No historical data found. Using baseline weights.")
            return weights
            
        try:
            with open(CSV_FILE_PATH, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    # Look for rows that have been manually graded (7 columns)
                    if len(row) >= 7:
                        grade = str(row[6]).strip().upper()
                        top_pick = str(row[3]).strip()
                        sources_str = str(row[5])
                        
                        if grade in ["WIN", "LOSS"]:
                            # Parse the saved string back into usable data
                            clean_str = sources_str.replace("['", "").replace("']", "").replace("', '", "|")
                            sources_list = clean_str.split("|")
                            
                            for item in sources_list:
                                if ":" in item:
                                    site, pick = item.split(":", 1)
                                    site = site.strip()
                                    pick = pick.strip()
                                    
                                    if site in weights:
                                        if grade == "WIN" and pick == top_pick:
                                            weights[site] += 0.05  # Reward accurate predictions
                                        elif grade == "LOSS" and pick == top_pick:
                                            weights[site] -= 0.05  # Penalize inaccurate predictions
                                        
                                        # Set math boundaries so weights don't break the system
                                        weights[site] = max(0.5, min(weights[site], 2.0))
        except Exception as e:
            print(f"[!] Warning: Feedback loop encountered an error: {e}")
            
        print(f"[*] AI Dynamic Weights Calculated: {weights}")
        return weights

    # ==============================================================================
    # 3. UNIVERSAL DATA TRANSLATOR LAYER
    # ==============================================================================
    def normalize_prediction(self, raw_text):
        text = str(raw_text).strip().lower()
        translation_matrix = {
            "1": ["1", "home", "home win", "team a", "team 1"],
            "X": ["x", "draw", "tie"],
            "2": ["2", "away", "away win", "team b", "team 2"],
            "1X": ["1x", "home or draw", "home/draw", "1 x"],
            "X2": ["x2", "away or draw", "away/draw", "x 2"],
            "12": ["12", "home or away", "any winner"],
            "OVER 1.5": ["o1.5", "over 1.5", "over 1.5 goals", "+1.5"],
            "OVER 2.5": ["o2.5", "over 2.5", "over 2.5 goals", "+2.5"],
            "UNDER 2.5": ["u2.5", "under 2.5", "under 2.5 goals", "-2.5"],
            "GG": ["gg", "btts", "both teams to score", "yes"],
            "NG": ["ng", "btts - no", "no goal", "no"]
        }
        for standard_tag, variations in translation_matrix.items():
            if text in variations:
                return standard_tag
        return None

    def clean_team_name(self, name):
        name = name.strip().lower()
        mapping = {"man utd": "manchester united", "chelsea fc": "chelsea", "lfc": "liverpool"}
        return mapping.get(name, name).title()

    def log_prediction_qa(self, site_name, home, away, raw_prediction):
        if not home or not away or not raw_prediction: return
        normalized_pick = self.normalize_prediction(raw_prediction)
        if not normalized_pick: return
        match_key = f"{self.clean_team_name(home)} vs {self.clean_team_name(away)}"
        if match_key not in self.master_matrix: self.master_matrix[match_key] = []
        self.master_matrix[match_key].append((site_name, normalized_pick))

    # ==============================================================================
    # 4. SCRAPER PIPELINE
    # ==============================================================================
    def fetch_and_scrape_sync(self, site_name, cfg):
        try:
            response = tls_requests.get(cfg["url"], impersonate="chrome120", timeout=20)
            if response.status_code != 200: return
            soup = BeautifulSoup(response.content, 'html.parser')
            rows = soup.find_all(cfg["row_selector"], class_=cfg["row_class"])
            for row in rows:
                try:
                    h = row.find_all(cfg["home_selector"], class_=cfg["home_class"])[cfg["home_index"]].text
                    a = row.find_all(cfg["away_selector"], class_=cfg["away_class"])[cfg["away_index"]].text
                    p = row.find_all(cfg["pick_selector"], class_=cfg["pick_class"])[cfg["pick_index"]].text
                    self.log_prediction_qa(site_name, h, a, p)
                except: continue
        except: return

    def filter_existing_today(self):
        today_date = datetime.datetime.now().strftime('%Y-%m-%d')
        scraped_today = set()
        if os.path.exists(CSV_FILE_PATH):
            with open(CSV_FILE_PATH, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) > 2 and row[0].startswith(today_date):
                        scraped_today.add(row[2])
        self.master_matrix = {k: v for k, v in self.master_matrix.items() if k not in scraped_today}

    # ==============================================================================
    # 5. QUANT ENGINE & ALGORITHMIC OUTPUT
    # ==============================================================================
    def process_quant_signals(self):
        daily_sure_bets = []
        jackpot_builders = []
        csv_rows_to_save = []
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        for match, listings in self.master_matrix.items():
            if len(listings) < 2: continue

            prediction_weights = {}
            total_possible_weight = sum(self.dynamic_weights[site] for site, _ in listings)

            for site, pick in listings:
                weight = self.dynamic_weights.get(site, 1.0)
                prediction_weights[pick] = prediction_weights.get(pick, 0.0) + weight

            top_pick = max(prediction_weights, key=prediction_weights.get)
            weighted_score = prediction_weights[top_pick]
            confidence_pct = (weighted_score / total_possible_weight) * 100
            true_odds = 1 / (confidence_pct / 100) if confidence_pct > 0 else 0.0

            raw_sources_log = str([f"{s}:{p}" for s, p in listings])
            # Added a placeholder for the grading column
            csv_rows_to_save.append([timestamp, ACTIVE_STRATEGY, match, top_pick, f"{confidence_pct:.0f}%", raw_sources_log, ""])

            if confidence_pct >= 99.9: # Accounts for floating point math
                daily_sure_bets.append(f"• {match} ➔ {top_pick} [True Odds: {true_odds:.2f}]")
            else:
                jackpot_builders.append(f"• {match} ➔ {top_pick} ({confidence_pct:.0f}%) [True Odds: {true_odds:.2f}]")

        return daily_sure_bets, jackpot_builders, csv_rows_to_save

    def save_to_history(self, rows):
        file_exists = os.path.exists(CSV_FILE_PATH)
        with open(CSV_FILE_PATH, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Timestamp", "Strategy", "Match", "Top_Pick", "Confidence", "Sources", "Grade"])
            writer.writerows(rows)

    def send_telegram_alert(self, message):
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        try:
            tls_requests.post(url, json=payload, impersonate="chrome120", timeout=10)
        except Exception as e: print(f"[!] Bot Alert Failed: {e}")

    async def run_pipeline(self):
        print(f"[+] Initializing Project {ACTIVE_STRATEGY} Data Pipeline...")
        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            await asyncio.gather(*[loop.run_in_executor(pool, self.fetch_and_scrape_sync, n, c) for n, c in self.configs.items()])
        
        self.filter_existing_today()
        daily_sures, jackpot_slips, rows = self.process_quant_signals()
        
        if not daily_sures and not jackpot_slips:
            print("[!] No new validated analytical signals generated today.")
            return

        self.save_to_history(rows)

        msg = f"🏰 PROJECT {ACTIVE_STRATEGY.upper()}: QUANT ALERT 🏰\n\n"
        if daily_sures:
            msg += "🏆 PREMIUM SURE SLIPS (Dynamic AI Weights)\n"
            for bet in daily_sures: msg += f"{bet}\n"
            msg += "\n"
        if jackpot_slips:
            msg += "🎫 ALGORITHMIC JACKPOT BUILDERS\n"
            for bet in jackpot_slips: msg += f"{bet}\n"
            msg += "\n"
        msg += f"📊 Powered by Fortress V2 Self-Tuning Engine."
        
        self.send_telegram_alert(msg)
        print("[+] Quant Mega-Ticket dispatched to Bot #2.")

if __name__ == "__main__":
    engine = FortressMasterEngine(TARGET_CONFIG)
    asyncio.run(engine.run_pipeline())
