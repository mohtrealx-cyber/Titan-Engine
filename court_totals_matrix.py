import os
import json
import requests
import itertools
from datetime import datetime, timedelta

# ==============================================================================
# TITAN ENGINE: COURT TOTALS AUTOMATOR (BASKETBALL & TENNIS O/U)
# ==============================================================================
# Now using a dedicated Telegram channel for Court Sports
COURT_TELEGRAM_TOKEN = os.environ.get("COURT_TELEGRAM_TOKEN")
COURT_TELEGRAM_CHAT_ID = os.environ.get("COURT_TELEGRAM_CHAT_ID")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

class CourtTotalsCore:
    def __init__(self):
        self.value_candidates = []
        self.raw_match_count = 0
        self.api_status = "🟢 OK"
        self.api_error_message = None 

    def fetch_totals_markets(self):
        if not ODDS_API_KEY: 
            self.api_status = "🔴 MISSING ODDS_API_KEY"
            return []
            
        target_leagues = [
            "basketball_nba", "basketball_wnba", "basketball_euroleague",
            "tennis_atp_wimbledon", "tennis_wta_wimbledon", 
            "tennis_atp_us_open", "tennis_wta_us_open"
        ]
        
        all_matches = []
        for league in target_leagues:
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/?apiKey={ODDS_API_KEY}&regions=eu,uk,us&markets=totals"
            try:
                r = requests.get(url, timeout=10)
                if r.status_code == 200:
                    all_matches.extend(r.json())
                elif r.status_code == 429:
                    self.api_status = "🔴 QUOTA EXCEEDED (429)"
                    break 
                elif r.status_code == 401:
                    self.api_status = "🔴 UNAUTHORIZED (401)"
                    self.api_error_message = r.text 
                    break 
            except Exception: 
                continue
            
        self.raw_match_count = len(all_matches)
        return all_matches

    def process_matrix(self):
        matches = self.fetch_totals_markets()
        if not matches: return

        now = datetime.utcnow()
        limit = now + timedelta(hours=48)

        for match in matches:
            home, away = match.get("home_team"), match.get("away_team")
            time_str = match.get("commence_time", "")
            try:
                dt = datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%SZ")
                if dt < now or dt > limit: continue
            except: continue 

            bookmakers = match.get("bookmakers", [])
            
            pin_over, pin_under = None, None
            soft_over, soft_under = [], []
            line_point = None
            
            for bookie in bookmakers:
                is_pinnacle = (bookie.get("key") == "pinnacle")
                for mkt in bookie.get("markets", []):
                    if mkt.get("key") == "totals":
                        for outcome in mkt.get("outcomes", []):
                            price = float(outcome.get("price"))
                            name = outcome.get("name")
                            point = outcome.get("point")
                            
                            if line_point is None and point is not None:
                                line_point = point
                                
                            if point == line_point:
                                if is_pinnacle:
                                    if name == "Over": pin_over = price
                                    elif name == "Under": pin_under = price
                                else:
                                    if name == "Over": soft_over.append(price)
                                    elif name == "Under": soft_under.append(price)

            if pin_over and pin_under and soft_over and soft_under and line_point:
                avg_soft_over = sum(soft_over) / len(soft_over)
                avg_soft_under = sum(soft_under) / len(soft_under)
                
                if pin_over < pin_under:
                    prediction, sharp_odds, public_odds = f"Over {line_point}", pin_over, avg_soft_over
                else:
                    prediction, sharp_odds, public_odds = f"Under {line_point}", pin_under, avg_soft_under
                
                match_title = f"{home.strip()} vs {away.strip()}"
                edge = public_odds - sharp_odds
                
                if 1.25 <= sharp_odds <= 1.75 and edge > 0.02:
                    self.value_candidates.append({
                        "text": f"{match_title} ➔ {prediction}", 
                        "odds": sharp_odds, 
                        "edge": edge
                    })

    def dispatch_alerts(self):
        if not COURT_TELEGRAM_TOKEN or not COURT_TELEGRAM_CHAT_ID: return
            
        msg = "🏀🎾 **GOAL-LINE COURT MATRIX (O/U TOTALS)** 🎾🏀\n\n"
            
        if self.value_candidates:
            sorted_binary = sorted(self.value_candidates, key=lambda x: x["edge"], reverse=True)[:8]
            n_total = len(sorted_binary)
            
            if n_total >= 4:
                combo_size = n_total - 2
                all_combos = list(itertools.combinations(sorted_binary, combo_size))
                
                msg += f"🎰 **{combo_size}/{n_total} COURT SYSTEM (Drop 2 Matches)** 🎰\n"
                msg += f"↳ *{len(all_combos)} Tickets Required (Pure Binary / No Draws)*\n\n"
                
                msg += "📋 **MASTER OVER/UNDER LIST:**\n"
                for i, pick in enumerate(sorted_binary, 1):
                    msg += f" `[{i}]` {pick['text']} @ {pick['odds']:.2f} (+EV: {pick['edge']:.2f})\n"
                    
                msg += "\n✂️ **THE DROP MATRIX:**\n"
                drop_pairs = list(itertools.combinations(range(1, n_total + 1), 2))
                drop_lines = [f"T{idx}: Drop [{p[0]}&{p[1]}]" for idx, p in enumerate(drop_pairs, 1)]
                
                for i in range(0, len(drop_lines), 3):
                    msg += " | ".join(drop_lines[i:i+3]) + "\n"
                msg += "\n"
            else:
                 msg += "🎰 **GOAL-LINE COURT SYSTEM** 🎰\n↳ 🟡 Insufficient high-value Court Totals to build a Drop-2 Matrix today.\n\n"
        else:
            msg += "🎰 **GOAL-LINE COURT MATRIX** 🎰\n↳ 🟡 No Over/Under court lines currently meet the sharp threshold.\n\n"

        msg += "⚙️ **SYSTEM DIAGNOSTICS** ⚙️\n"
        msg += f"↳ API Status: {self.api_status}\n"
        msg += f"↳ Raw Matches Scanned: {self.raw_match_count}\n"
        msg += f"↳ Active Sieves: Totals Market (O/U), +EV Edge Finder, Court N-2 Matrix\n"

        requests.post(f"https://api.telegram.org/bot{COURT_TELEGRAM_TOKEN}/sendMessage", 
                      json={"chat_id": COURT_TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    engine = CourtTotalsCore()
    engine.process_matrix()
    engine.dispatch_alerts()
