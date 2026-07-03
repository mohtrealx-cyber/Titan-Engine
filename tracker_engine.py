import os
import re
import json
import requests
from datetime import datetime, timedelta

# ==============================================================================
# TITAN TRACKER: PURE COMBINATION CORE (COMBO + ANTI-TRAP JACKPOT)
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
        for league in target_leagues:
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/?apiKey={ODDS_API_KEY}&regions=eu,uk,us&markets=h2h"
            try:
                r = requests.get(url, timeout=10)
                if r.status_code == 200:
                    all_matches.extend(r.json())
                elif r.status_code == 429:
                    self.api_status = "🔴 QUOTA EXCEEDED (429) - Monthly limit reached."
                    break 
                elif r.status_code == 401:
                    self.api_status = "🔴 UNAUTHORIZED (401)"
                    self.api_error_message = r.text 
                    break 
            except Exception as e: 
                continue
            
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
            home_prices, away_prices, draw_prices = [], [], []
            
            for bookie in bookmakers:
                for mkt in bookie.get("markets", []):
                    if mkt.get("key") == "h2h":
                        for outcome in mkt.get("outcomes", []):
                            price = float(outcome.get("price"))
                            if outcome.get("name") == home: home_prices.append(price)
                            elif outcome.get("name") == away: away_prices.append(price)
                            elif outcome.get("name") == "Draw": draw_prices.append(price)

            if home_prices and away_prices and draw_prices:
                avg_home, avg_away, avg_draw = sum(home_prices)/len(home_prices), sum(away_prices)/len(away_prices), sum(draw_prices)/len(draw_prices)
                
                if avg_home < avg_away:
                    fav, avg_fav, sym = home, avg_home, "1"
                else:
                    fav, avg_fav, sym = away, avg_away, "2"
                
                match_title = f"{self.clean_team_name(home)} vs {self.clean_team_name(away)}"

                # 1. DRAW CONTRACTION TRAP DETECTOR
                is_draw_trap = False
                if avg_fav <= 1.70 and avg_draw < 3.70:
                    is_draw_trap = True 
                elif avg_fav <= 2.20 and avg_draw < 3.10:
                    is_draw_trap = True 
                
                # If it passes the trap test, feed it to the massive Jackpot pool
                if not is_draw_trap:
                    self.jackpot_candidates.append({"text": f"{match_title} ({sym})", "odds": avg_fav})
                    
                    # Track it for the scoreboard ledger
                    self.structured_tickets.append({
                        "date": match_date_key, "match": match_title, "prediction": sym, "status": "PENDING", "score": "-"
                    })

                # 2. STRICT COMBO SIFTING (Only the absolute safest 1.50 & 4.00+ Draw games)
                if avg_fav <= 1.50 and avg_draw >= 4.00:
                    self.combo_candidates.append({"text": f"{match_title} ({sym})", "odds": avg_fav})

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
        if not os.path.exists(file_path): return ""
        try:
            with open(file_path, "r") as f: memory = json.load(f)
        except: return ""

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

        all_settled_games = []
        wins, losses = 0, 0
        
        for d_key in sorted(memory.keys(), reverse=True):
            for t in memory[d_key]:
                if "WON" in t["status"]:
                    wins += 1
                    all_settled_games.append(f"• {t['match']} ➔ **WON 🟢** (Score: {t['score']})")
                elif "LOST" in t["status"]:
                    losses += 1
                    all_settled_games.append(f"• {t['match']} ➔ **LOST 🔴** (Score: {t['score']})")

        total_settled = wins + losses
        win_rate = (wins / total_settled * 100) if total_settled > 0 else 0.0

        sb = "📊 **TITAN SCOREBOARD & LIVE LEDGER** 📊\n"
        sb += f"🏆 **All-Time Win Rate:** `{win_rate:.1f}%` ({wins}W - {losses}L)\n"
        sb += f"📈 **Total Settled Volume:** `{total_settled} selections`\n\n"
        
        if all_settled_games:
            sb += "🕒 **Recent Game Ledger (Latest Lookback):**\n"
            for game in all_settled_games[:5]:
                sb += f"{game}\n"
        else:
            sb += "No matches settled in ledger history yet.\n"
            
        return sb + "\n"

    def dispatch_alerts(self, scoreboard_text):
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
            
        msg = "🎯 **TITAN ENGINE: COMBINATION CORE** 🎯\n\n"
            
        if len(self.combo_candidates) >= 2:
            sorted_candidates = sorted(self.combo_candidates, key=lambda x: x["odds"])
            combo_picks = sorted_candidates[:3]
            total_odds = 1.0
            combo_text_lines = []
            for pick in combo_picks:
                total_odds *= pick["odds"]
                combo_text_lines.append(f" ↳ {pick['text']} @ {pick['odds']:.2f}")
            msg += "🔥 **RECOMMENDED 3-LEG COMBINATION TICKET** 🔥\n"
            msg += "\n".join(combo_text_lines) + "\n"
            msg += f"📈 **Estimated Total Odds:** {total_odds:.2f}\n💰 **Suggested Stake:** 100 KES\n\n"
        else:
            msg += "🔥 **RECOMMENDED COMBINATION TICKET** 🔥\n↳ 🟡 Insufficient high-confidence matches for a safe combo today.\n\n"

        if self.jackpot_candidates:
            # Sort all surviving non-trap favorites by relative odd strength
            sorted_jackpot = sorted(self.jackpot_candidates, key=lambda x: x["odds"])
            jackpot_odds = 1.0
            jackpot_text_lines = []
            for pick in sorted_jackpot:
                jackpot_odds *= pick["odds"]
                jackpot_text_lines.append(f" ↳ {pick['text']} @ {pick['odds']:.2f}")
                
            msg += f"🎰 **TITAN {len(sorted_jackpot)}-LEG ANTI-TRAP JACKPOT SLIP** 🎰\n"
            msg += "\n".join(jackpot_text_lines) + "\n"
            msg += f"📈 **Estimated Cumulative Odds:** {jackpot_odds:,.2f}\n💰 **Suggested System Stake:** 10 KES\n\n"
        else:
            msg += "🎰 **TITAN ANTI-TRAP JACKPOT** 🎰\n↳ 🟡 All matches on the current 48h slate flagged as potential Draw Traps. Awaiting clean volume...\n\n"

        msg += scoreboard_text

        msg += "⚙️ **SYSTEM DIAGNOSTICS** ⚙️\n"
        msg += f"↳ API Status: {self.api_status}\n"
        if self.api_error_message: msg += f"↳ Server Response: `{self.api_error_message}`\n"
        msg += f"↳ Raw Matches Scanned: {self.raw_match_count}\n"

        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    from bs4 import BeautifulSoup
    engine = MegaTicketVolumeSieve()
    engine.process_matrix()
    engine.save_tickets_to_memory()
    live_scoreboard = engine.settle_and_build_scoreboard()
    engine.dispatch_alerts(live_scoreboard)
