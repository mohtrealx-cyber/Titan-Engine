import os
import re
import json
import time
import requests
import itertools
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# ==============================================================================
# TITAN TRACKER: APEX CORE (MUTUALLY EXCLUSIVE MATRIX WITH CONSENSUS FALLBACK)
# ==============================================================================
TELEGRAM_TOKEN = os.environ.get("TRACKER_TRACKER_TELEGRAM_TOKEN") if os.environ.get("TRACKER_TRACKER_TELEGRAM_TOKEN") else os.environ.get("TRACKER_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TRACKER_TRACKER_TELEGRAM_CHAT_ID") if os.environ.get("TRACKER_TRACKER_TELEGRAM_CHAT_ID") else os.environ.get("TRACKER_TELEGRAM_CHAT_ID")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

class MegaTicketVolumeSieve:
    def __init__(self):
        self.combo_candidates = []
        self.jackpot_candidates = [] 
        self.structured_tickets = [] 
        self.raw_match_count = 0
        self.api_status = "🟢 OK"
        self.api_error_message = None 

    def fetch_market_data(self):
        if not ODDS_API_KEY: 
            self.api_status = "🔴 MISSING API KEY"
            return []
            
        target_leagues = [
            "soccer_fifa_world_cup", "soccer_brazil_campeonato", "soccer_brazil_serie_b", 
            "soccer_usa_mls", "soccer_japan_j_league", "soccer_sweden_allsvenskan",
            "soccer_ireland_premier_division", "soccer_norway_eliteserien",
            "soccer_argentina_primera_division", "soccer_finland_veikkausliiga",
            "soccer_korea_kleague1", "soccer_china_superleague"
        ]
        
        all_matches = []
        print(f"Scanning {len(target_leagues)} leagues for Apex Matrix...")
        
        for league in target_leagues:
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/?apiKey={ODDS_API_KEY}&regions=eu,uk,us&markets=h2h"
            
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    r = requests.get(url, timeout=15)
                    if r.status_code == 200:
                        all_matches.extend(r.json())
                        break 
                    elif r.status_code == 429:
                        print(f"⚠️ Odds API Limit hit on {league}. Sleeping for 10s (Attempt {attempt+1}/{max_retries})...")
                        time.sleep(10)
                        if attempt == max_retries - 1:
                            self.api_status = "🔴 QUOTA EXCEEDED (429) - Monthly limit reached."
                    elif r.status_code == 401:
                        self.api_status = "🔴 UNAUTHORIZED (401)"
                        self.api_error_message = r.text 
                        break 
                    else:
                        break 
                except Exception as e: 
                    time.sleep(2) 
            
            time.sleep(1.5)
            if "QUOTA EXCEEDED" in self.api_status:
                break
            
        self.raw_match_count = len(all_matches)
        return all_matches

    def clean_team_name(self, name):
        return name.strip().title()

    def process_matrix(self):
        matches = self.fetch_market_data()
        if not matches: return

        now = datetime.utcnow()
        limit = now + timedelta(hours=48)

        for match in matches:
            home, away = match.get("home_team"), match.get("away_team")
            time_str = match.get("commence_time", "")
            try:
                dt = datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%SZ")
                if dt < now or dt > limit: continue
                match_eat = dt + timedelta(hours=3)
                match_date_key = match_eat.strftime("%Y-%m-%d")
            except: continue 

            bookmakers = match.get("bookmakers", [])
            
            # Target values
            m_home, m_away, m_draw = None, None, None
            
            # Strategy Phase 1: Hunt for Pinnacle
            for bookie in bookmakers:
                if bookie.get("key") == "pinnacle":
                    for mkt in bookie.get("markets", []):
                        if mkt.get("key") == "h2h":
                            for outcome in mkt.get("outcomes", []):
                                price = float(outcome.get("price"))
                                name = outcome.get("name")
                                if name == home: m_home = price
                                elif name == away: m_away = price
                                elif name == "Draw": m_draw = price
            
            # Strategy Phase 2: Consensus Fallback Matrix if Pinnacle is missing
            if not (m_home and m_away and m_draw):
                home_prices, away_prices, draw_prices = [], [], []
                for bookie in bookmakers:
                    for mkt in bookie.get("markets", []):
                        if mkt.get("key") == "h2h":
                            for outcome in mkt.get("outcomes", []):
                                price = float(outcome.get("price"))
                                name = outcome.get("name")
                                if name == home: home_prices.append(price)
                                elif name == away: away_prices.append(price)
                                elif name == "Draw": draw_prices.append(price)
                
                if home_prices and away_prices and draw_prices:
                    m_home = sum(home_prices) / len(home_prices)
                    m_away = sum(away_prices) / len(away_prices)
                    m_draw = sum(draw_prices) / len(draw_prices)

            # Strategy Phase 3: Run Sieves on Verified Odds Data
            if m_home and m_away and m_draw:
                if m_home < m_away:
                    fav_team, sharp_fav_odd, sym = home, m_home, "1"
                else:
                    fav_team, sharp_fav_odd, sym = away, m_away, "2"
                
                match_title = f"{self.clean_team_name(home)} vs {self.clean_team_name(away)}"

                geometric_score = m_draw / sharp_fav_odd
                margin = (1.0 / m_home) + (1.0 / m_away) + (1.0 / m_draw) - 1.0
                
                is_panic_market = margin > 0.085
                is_weak_away_fav = (sym == "2") and (sharp_fav_odd > 1.85)

                passed_jackpot = not is_panic_market and not is_weak_away_fav and (geometric_score >= 2.15)
                passed_combo = not is_panic_market and not is_weak_away_fav and (geometric_score >= 2.80) and (sharp_fav_odd <= 1.50)

                if passed_jackpot:
                    self.jackpot_candidates.append({
                        "text": f"{match_title} ({sym})", "odds": sharp_fav_odd, "score": geometric_score
                    })
                
                if passed_combo:
                    self.combo_candidates.append({"text": f"{match_title} ({sym})", "odds": sharp_fav_odd})

                if passed_jackpot or passed_combo:
                    self.structured_tickets.append({
                        "date": match_date_key, "match": match_title, "prediction": sym, "status": "PENDING", "score": "-"
                    })

    def save_tickets_to_memory(self):
        if not self.structured_tickets: return
        file_path = "pending_tracker_tickets.json"
        memory = {}
        if os.path.exists(file_path):
            try:
                with open(file_path, "r") as f: memory = json.load(f)
            except: pass
            
        for ticket in self.structured_tickets:
            d_key = ticket["date"]
            if d_key not in memory: memory[d_key] = []
            
            if not any(t["match"] == ticket["match"] for t in memory[d_key]):
                memory[d_key].append({
                    "match": ticket["match"], "prediction": ticket["prediction"], "status": ticket["status"], "score": ticket["score"]
                })
        try:
            with open(file_path, "w") as f: json.dump(memory, f, indent=4)
        except: pass

    def fuzzy_team_align(self, name1, name2):
        noise = ["fc", "afc", "sc", "cf", "fk", "united", "utd", "city", "town", "rovers", "athletic", "club", "de", "sporting", "real"]
        def strip_noise(s):
            s = s.lower()
            for token in noise: s = re.sub(rf'\b{token}\b', '', s)
            return "".join(re.findall(r'[a-z0-9]', s))
        c1, c2 = strip_noise(name1), strip_noise(name2)
        return c1 in c2 or c2 in c1 if (c1 and c2) else False

    def settle_and_build_scoreboard(self):
        file_path = "pending_tracker_tickets.json"
        if not os.path.exists(file_path): return "📊 **No previous history detected in database ledger.**\n"
        try:
            with open(file_path, "r") as f: memory = json.load(f)
        except: return "📊 **Ledger reading fault.**\n"

        dates_to_audit = [d for d, tickets in memory.items() if any(t["status"] == "PENDING" for t in tickets)]
        
        if dates_to_audit:
            scraped_results = {}
            for d in dates_to_audit:
                url = f"https://www.statarea.com/predictions/date/{d}/"
                try:
                    r = requests.get(url, timeout=20)
                    if r.status_code == 200:
                        soup = BeautifulSoup(r.content, 'html.parser')
                        for row in soup.find_all("div", class_="matchrow"):
                            text = row.get_text(separator=" ").upper()
                            if any(flag in f" {text} " for flag in [" FT ", "FINISHED", " AET ", " PEN "]):
                                h_elems = row.find_all("div", class_="name")
                                if len(h_elems) >= 2:
                                    h_name, a_name = h_elems[0].text.strip(), h_elems[1].text.strip()
                                    score_match = re.search(r'\b(\d{1,2})\s*-\s*(\d{1,2})\b', text)
                                    if score_match:
                                        scraped_results[f"{h_name} vs {a_name}"] = f"{score_match.group(1)}-{score_match.group(2)}"
                except: pass

            file_updated = False
            for d_key, tickets in memory.items():
                for t in tickets:
                    if t["status"] == "PENDING":
                        t_match = t["match"]
                        t_home, t_away = t_match.split(" vs ")
                        
                        matched_score = None
                        for scr_match, scr_score in scraped_results.items():
                            scr_home, scr_away = scr_match.split(" vs ")
                            if self.fuzzy_team_align(t_home, scr_home) and self.fuzzy_team_align(t_away, scr_away):
                                matched_score = scr_score
                                break
                        
                        if matched_score:
                            try:
                                hg, ag = map(int, matched_score.split("-"))
                                actual = "1" if hg > ag else ("X" if hg == ag else "2")
                                t["status"] = "WON 🟢" if t["prediction"] == actual else "LOST 🔴"
                                t["score"] = matched_score
                                file_updated = True
                            except: pass

            if file_updated:
                try:
                    with open(file_path, "w") as f: json.dump(memory, f, indent=4)
                except: pass

        wins, losses = 0, 0
        for d_key in memory.keys():
            for t in memory[d_key]:
                if "WON" in t["status"]: wins += 1
                elif "LOST" in t["status"]: losses += 1

        total_settled = wins + losses
        win_rate = (wins / total_settled * 100) if total_settled > 0 else 0.0

        sb = "📊 **TITAN SCOREBOARD & LIVE LEDGER** 📊\n"
        sb += f"🏆 **All-Time Win Rate:** `{win_rate:.1f}%` ({wins}W - {losses}L)\n"
        sb += f"📈 **Total Settled Volume:** `{total_settled} selections`\n\n"
        return sb

    def dispatch_alerts(self, scoreboard_text):
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
            
        msg = "🎯 **TITAN ENGINE: MUTUALLY EXCLUSIVE MATRIX CORE** 🎯\n\n"
            
        # 1. Combo Ticket Processor
        combo_exclusion_list = []
        if len(self.combo_candidates) >= 3:
            sorted_candidates = sorted(self.combo_candidates, key=lambda x: x["odds"])
            combo_picks = sorted_candidates[:3]
            combo_exclusion_list = [pick['text'] for pick in combo_picks]
            
            total_odds = 1.0
            combo_text_lines = []
            for pick in combo_picks:
                total_odds *= pick["odds"]
                combo_text_lines.append(f" ↳ {pick['text']} @ {pick['odds']:.2f}")
            msg += "🔥 **RECOMMENDED 3-LEG COMBINATION TICKET** 🔥\n"
            msg += "\n".join(combo_text_lines) + "\n"
            msg += f"📈 **Estimated Total Odds:** {total_odds:.2f}\n💰 **Suggested Stake:** 100 KES\n\n"
        else:
            msg += "🔥 **RECOMMENDED COMBINATION TICKET** 🔥\n↳ 🟡 Insufficient matches passed the 2.80 Consensus Combo Sieve.\n\n"

        # 2. Filter Jackpot Pool
        filtered_jackpot_pool = [pick for pick in self.jackpot_candidates if pick["text"] not in combo_exclusion_list]

        # 3. Process Jackpot System Slips
        if filtered_jackpot_pool:
            sorted_jackpot = sorted(filtered_jackpot_pool, key=lambda x: x["score"], reverse=True)[:10]
            n_total = len(sorted_jackpot)
            
            if n_total > 2:
                combo_size = n_total - 2
                all_combos = list(itertools.combinations(sorted_jackpot, combo_size))
                total_matrix_cost = len(all_combos) * 40
                
                msg += f"🎰 **TITAN {combo_size}/{n_total} SYSTEM MATRIX (Drop 2 Matches)** 🎰\n"
                msg += f"↳ *{len(all_combos)} Total Tickets Required*\n"
                msg += f"💰 **Stake:** 40 KES per ticket (Total Matrix Cost: {total_matrix_cost} KES)\n\n"
                
                msg += "📋 **MASTER MATCH LIST:**\n"
                for i, pick in enumerate(sorted_jackpot, 1):
                    msg += f" `[{i}]` {pick['text']} @ {pick['odds']:.2f} (Struct: {pick['score']:.2f})\n"
                    
                msg += "\n剪️ **THE DROP MATRIX (What to leave out):**\n"
                msg += "Build slips by taking the Master List and dropping the bracketed numbers below:\n\n"
                
                drop_pairs = list(itertools.combinations(range(1, n_total + 1), 2))
                drop_lines = [f"T{idx}: Drop [{p[0]}&{p[1]}]" for idx, p in enumerate(drop_pairs, 1)]
                
                for i in range(0, len(drop_lines), 3):
                    msg += " | ".join(drop_lines[i:i+3]) + "\n"
                msg += "\n"
            else:
                msg += "🎰 **TITAN SYSTEM MATRIX** 🎰\n↳ 🟡 Only found {n_total} matches passing the 2.15 safety marker. Need at least 3 for Drop-2 Matrix.\n\n"
        else:
            msg += "🎰 **TITAN GEOMETRIC JACKPOT** 🎰\n↳ 🟡 No matches matched the geometric safety criteria on the consensus stream.\n\n"

        msg += scoreboard_text

        msg += "⚙️ **SYSTEM DIAGNOSTICS** ⚙️\n"
        msg += f"↳ API Status: {self.api_status}\n"
        if self.api_error_message: msg += f"↳ Server Response: `{self.api_error_message}`\n"
        msg += f"↳ Raw Matches Scanned: {self.raw_match_count}\n"
        msg += f"↳ Active Sieves: Consensus Fallback Optimization, Panic Tax Protection, Geometric Variance Sieve\n"

        try:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                          json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
            print("Alert successfully dispatched to Telegram.")
        except Exception as e:
            print(f"Failed to dispatch Telegram alert: {e}")

if __name__ == "__main__":
    print("Initiating Titan Tracker: Apex Core v2.5...")
    engine = MegaTicketVolumeSieve()
    engine.process_matrix()
    engine.save_tickets_to_memory()
    live_scoreboard = engine.settle_and_build_scoreboard()
    engine.dispatch_alerts(live_scoreboard)
    print("Routine complete.")
