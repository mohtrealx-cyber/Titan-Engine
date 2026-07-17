import os
import re
import json
import time
import asyncio
import datetime
import difflib
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
            # We bypass ZenRows completely and use curl_cffi directly for all sites
            print(f"   [Scraper] Extracting data from {site_name}...")
            r = tls_requests.get(cfg["url"], impersonate="chrome120", timeout=20)
            
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
                        
                except Exception as e: 
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
            except: pass
            
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
        except: pass

    def fetch
