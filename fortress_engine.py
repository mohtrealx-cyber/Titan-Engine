import os
import time
import asyncio
import csv
import datetime
from difflib import SequenceMatcher
from bs4 import BeautifulSoup
import concurrent.futures
from curl_cffi import requests as tls_requests
from understatapi import UnderstatClient

# ==============================================================================
# 1. CONFIGURATION & SECURITY
# ==============================================================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

ACTIVE_STRATEGY = "Fortress V3.1 (Live Date Routing)"
CSV_FILE_PATH = "fortress_performance_history.csv"

def get_dynamic_configs():
    """Generates live URLs for TODAY only and attaches a cache-buster to bypass Cloudflare."""
    today_date = datetime.datetime.now().strftime('%Y-%m-%d')
    cb = int(time.time()) 
    
    return {
        "Statarea": {"url": f"https://www.statarea.com/predictions/date/{today_date}/", "row_selector": "div", "row_class": "matchrow", "home_selector": "div", "home_class": "name", "home_index": 0, "away_selector": "div", "away_class": "name", "away_index": 1, "pick_selector": "div", "pick_class": "type1", "pick_index": 0},
        "PredictZ": {"url": f"https://www.predictz.com/predictions/today/?cb={cb}", "row_selector": "div", "row_class": "pttr", "home_selector": "div", "home_class": "pttmobh", "home_index": 0, "away_selector": "div", "away_class": "pttmoba", "away_index": 0, "pick_selector": "div", "pick_class": "ptoddsdesc", "pick_index": 0},
        "Vitibet": {"url": f"https://www.vitibet.com/index.php?clanek=quicktips&sekce=fotbal&lang=en&cb={cb}", "row_selector": "a", "row_class": "livescore-match-row", "home_selector": "span", "home_class": "livescore-team-name", "home_index": 0, "away_selector": "span", "away_class": "livescore-team-name", "away_index": 1, "pick_selector": "span", "pick_class": "tip-indicator-circle", "pick_index": 0}
    }

class FortressMasterEngine:
    def __init__(self, configs):
        self.configs = configs
        self.master_matrix = {}
        self.dynamic_weights = self.calculate_dynamic_weights()

    # ==============================================================================
    # 2. PHASE 1: MACHINE LEARNING & TRANSLATOR LOGIC
    # ==============================================================================
    def calculate_dynamic_weights(self):
        weights = {"Statarea": 1.0, "PredictZ": 1.0, "Vitibet": 1.0}
        if not os.path.exists(CSV_FILE_PATH): return weights
        try:
            with open(CSV_FILE_PATH, 'r', encoding='utf-8') as f:
                for row in csv.reader(f):
                    if len(row) >= 7:
                        grade, top_pick, sources_str = str(row[6]).strip().upper(), str(row[3]).strip(), str(row[5])
                        if grade in ["WIN", "LOSS"]:
                            for item in sources_str.replace("['", "").replace("']", "").replace("', '", "|").split("|"):
                                if ":" in item:
                                    site, pick = item.split(":", 1)
                                    if site.strip() in weights:
                                        if grade == "WIN" and pick.strip() == top_pick: weights[site.strip()] += 0.05
                                        elif grade == "LOSS" and pick.strip() == top_pick: weights[site.strip()] -= 0.05
                                        weights[site.strip()] = max(0.5, min(weights[site.strip()], 2.0))
        except: pass
        return weights

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

    # ==============================================================================
    # 3. PHASE 2: LIVE ODDS API INGESTION (FUZZY MATCH UPGRADE)
    # ==============================================================================
    def is_similar_name(self, name_a, name_b):
        return SequenceMatcher(None, name_a.lower(), name_b.lower()).ratio() > 0.70

    def fetch_live_bookmaker_odds(self, home_team):
        if not ODDS_API_KEY: return None
        url = f"https://api.the-odds-api.com/v4/sports/upcoming/odds/?apiKey={ODDS_API_KEY}&regions=eu&markets=h2h"
        try:
            response = tls_requests.get(url, timeout=10)
            if response.status_code == 200:
                for match in response.json():
                    api_home_team = match.get('home_team', '')
                    if self.is_similar_name(home_team, api_home_team) or home_team.lower() in api_home_team.lower():
                        bookmakers = match.get('bookmakers', [])
                        if bookmakers:
                            for outcome in bookmakers[0].get('markets', [])[0].get('outcomes', []):
                                if self.is_similar_name(outcome.get('name', ''), api_home_team):
                                    return outcome.get('price')
        except: pass
        return None

    # ==============================================================================
    # 4. PHASE 3: QUANT ENGINE & DYNAMIC SEASON ROLLED
    # ==============================================================================
    def get_active_season(self):
        now = datetime.datetime.now()
        if now.month < 8: 
            return str(now.year - 1)
        return str(now.year)

    def get_live_team_xg(self, team_name, season):
        formatted_name = team_name.replace(" ", "_")
        try:
            with UnderstatClient() as understat:
                match_data = understat.team(team=formatted_name).get_match_data(season=season)
                completed_matches = [m for m in match_data if m.get('isResult') == True]
                if completed_matches:
                    latest_match = completed_matches[-1]
                    if latest_match['h']['title'].lower() == team_name.lower():
                        return float(latest_match['xG']['h'])
                    return float(latest_match['xG']['a'])
        except: pass
        return None

    def calculate_pure_probability(self, home_xg, away_xg):
        total_xg = home_xg + away_xg
        if total_xg == 0: return 33.3, 33.3, 33.3
        home_raw_pct = (home_xg / total_xg) * 100
        away_raw_pct = (away_xg / total_xg) * 100
        home_advantage_pct = home_raw_pct + 5.0
        away_adjusted_pct = away_raw_pct - 5.0
        xg_difference = abs(home_xg - away_xg)
        draw_pct = 28.0 - (xg_difference * 5) 
        draw_pct = max(15.0, min(draw_pct, 35.0))
        remaining_pct = 100.0 - draw_pct
        total_adjusted_strength = home_advantage_pct + away_adjusted_pct
        home_final_prob = (home_advantage_pct / total_adjusted_strength) * remaining_pct
        away_final_prob = (away_adjusted_pct / total_adjusted_strength) * remaining_pct
        return home_final_prob, draw_pct, away_final_prob

    # ==============================================================================
    # 5. DATA PIPELINE & MATH ENGINE
    # ==============================================================================
    def fetch_and_scrape_sync(self, site_name, cfg):
        try:
            r = tls_requests.get(cfg["url"], impersonate="chrome120", timeout=20)
            if r.status_code != 200: return
            for row in BeautifulSoup(r.content, 'html.parser').find_all(cfg["row_selector"], class_=cfg["row_class"]):
                try: self.log_prediction_qa(site_name, row.find_all(cfg["home_selector"], class_=cfg["home_class"])[cfg["home_index"]].text, row.find_all(cfg["away_selector"], class_=cfg["away_class"])[cfg["away_index"]].text, row.find_all(cfg["pick_selector"], class_=cfg["pick_class"])[cfg["pick_index"]].text)
                except: continue
        except: return

    def filter_existing_today(self):
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        scraped = set()
        if os.path.exists(CSV_FILE_PATH):
            with open(CSV_FILE_PATH, 'r', encoding='utf-8') as f:
                for row in csv.reader(f):
                    if len(row) > 2 and row[0].startswith(today): scraped.add(row[2])
        self.master_matrix = {k: v for k, v in self.master_matrix.items() if k not in scraped}

    def process_quant_signals(self):
        daily_sures, jackpot_builders, value_exploits, csv_rows = [], [], [], []
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        season = self.get_active_season()

        for match, listings in self.master_matrix.items():
            if len(listings) < 2: continue
            
            home_team = match.split(" vs ")[0]
            away_team = match.split(" vs ")[1]
            prediction_weights = {}
            total_weight = sum(self.dynamic_weights[site] for site, _ in listings)

            for site, pick in listings:
                prediction_weights[pick] = prediction_weights.get(pick, 0.0) + self.dynamic_weights.get(site, 1.0)

            top_pick = max(prediction_weights, key=prediction_weights.get)
            confidence_pct = (prediction_weights[top_pick] / total_weight) * 100
            true_odds = 1 / (confidence_pct / 100) if confidence_pct > 0 else 0.0

            home_xg = self.get_live_team_xg(home_team, season)
            away_xg = self.get_live_team_xg(away_team, season)
            xg_tag = ""
            
            bookie_odds = self.fetch_live_bookmaker_odds(home_team) if top_pick == "1" else None
            
            if home_xg and away_xg:
                h_prob, d_prob, a_prob = self.calculate_pure_probability(home_xg, away_xg)
                xg_tag = f"\n   ↳ 📊 xG Pure Math: Home({h_prob:.1f}%) Draw({d_prob:.1f}%) Away({a_prob:.1f}%)"
                
                if bookie_odds and top_pick == "1":
                    ev_percentage = ((h_prob / 100) * bookie_odds) - 1
            else:
                if bookie_odds and top_pick == "1":
                    ev_percentage = ((confidence_pct / 100) * bookie_odds) - 1

            if bookie_odds and 'ev_percentage' in locals() and ev_percentage > 0.05: 
                value_exploits.append(f"🚨 {match}\n   ➔ True Odds: {true_odds:.2f} | Bookie Pays: {bookie_odds}\n   ➔ Edge: +{ev_percentage*100:.1f}% EV{xg_tag}")

            csv_rows.append([timestamp, ACTIVE_STRATEGY, match, top_pick, f"{confidence_pct:.0f}%", str([f"{s}:{p}" for s, p in listings]), ""])

            if confidence_pct >= 99.9: daily_sures.append(f"• {match} ➔ {top_pick} [True Odds: {true_odds:.2f}]{xg_tag}")
            else: jackpot_builders.append(f"• {match} ➔ {top_pick} ({confidence_pct:.0f}%) [True Odds: {true_odds:.2f}]{xg_tag}")

        return daily_sures, jackpot_builders, value_exploits, csv_rows

    def send_telegram_alert(self, msg):
        if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
            tls_requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, impersonate="chrome120", timeout=10)

    async def run_pipeline(self):
        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            await asyncio.gather(*[loop.run_in_executor(pool, self.fetch_and_scrape_sync, n, c) for n, c in self.configs.items()])
        
        self.filter_existing_today()
        sures, jackpots, exploits, rows = self.process_quant_signals()
        
        if not sures and not jackpots: return
        
        file_exists = os.path.exists(CSV_FILE_PATH)
        with open(CSV_FILE_PATH, 'a', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            if not file_exists: w.writerow(["Timestamp", "Strategy", "Match", "Top_Pick", "Confidence", "Sources", "Grade"])
            w.writerows(rows)

        msg = f"🏰 PROJECT {ACTIVE_STRATEGY.upper()} 🏰\n\n"
        if exploits:
            msg += "🚨 HIGH-VALUE EXPLOITS DETECTED 🚨\n"
            for b in exploits: msg += f"{b}\n\n"
        if sures:
            msg += "🏆 PREMIUM SURE SLIPS\n"
            for b in sures: msg += f"{b}\n"
            msg += "\n"
        if jackpots:
            msg += "🎫 ALGORITHMIC BUILDERS\n"
            for b in jackpots: msg += f"{b}\n"
            msg += "\n"
        
        self.send_telegram_alert(msg)

if __name__ == "__main__":
    live_configs = get_dynamic_configs()
    asyncio.run(FortressMasterEngine(live_configs).run_pipeline())
