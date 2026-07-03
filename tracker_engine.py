import os
import requests
from datetime import datetime, timedelta

# ==============================================================================
# TITAN TRACKER: STABLE CORE + UNLIMITED MEGA-TICKET
# ==============================================================================
TELEGRAM_TOKEN = os.environ.get("TRACKER_TRACKER_TELEGRAM_TOKEN") if os.environ.get("TRACKER_TRACKER_TELEGRAM_TOKEN") else os.environ.get("TRACKER_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TRACKER_TRACKER_TELEGRAM_CHAT_ID") if os.environ.get("TRACKER_TRACKER_TELEGRAM_CHAT_ID") else os.environ.get("TRACKER_TELEGRAM_CHAT_ID")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

class MegaTicketVolumeSieve:
    def __init__(self):
        self.anchor_bookie = "pinnacle"
        self.gold_preds = []
        self.std_preds = []
        self.combo_candidates = []       # For the 3-leg safe combo (Gold only)
        self.mega_combo_candidates = []  # For the risky combo (Gold + Standard)
        self.system_stake = "100 KES" 
        self.raw_match_count = 0
        self.api_status = "🟢 OK"

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
            url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/?apiKey={ODDS_API_KEY}®ions=eu,uk,us&markets=h2h"
            try:
                r = requests.get(url, timeout=10)
                if r.status_code == 200:
                    all_matches.extend(r.json())
                elif r.status_code == 429:
                    self.api_status = "🔴 QUOTA EXCEEDED (429)"
                elif r.status_code == 401:
                    self.api_status = "🔴 UNAUTHORIZED API KEY (401)"
            except Exception: pass
            
        self.raw_match_count = len(all_matches)
        return all_matches

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
                fmt_time = dt.strftime("%d %b, %H:%M")
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
                
                # GOLD TIER
                if avg_fav <= 1.50 and avg_draw >= 4.00:
                    self.gold_preds.append(f"📅 **{fmt_time}**\n• {home} vs {away} ➔ {sym} `[Stake: {self.system_stake}]`\n\n")
                    self.combo_candidates.append({"text": f"{home} vs {away} ({sym})", "odds": avg_fav})
                    self.mega_combo_candidates.append({"text": f"{home} vs {away} ({sym})", "odds": avg_fav})
                
                # STANDARD TIER
                elif avg_fav <= 2.10 and avg_draw >= 3.00:
                    self.std_preds.append(f"📅 **{fmt_time}**\n• {home} vs {away} ➔ {sym} `[Stake: {self.system_stake}]`\n\n")
                    self.mega_combo_candidates.append({"text": f"{home} vs {away} ({sym})", "odds": avg_fav})

    def dispatch_alerts(self):
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
            
        msg = "🎯 **TITAN ENGINE: HIGH-VOLUME CORE** 🎯\n\n"
        if self.gold_preds:
            msg += f"💎 **GOLD-TIER ({len(self.gold_preds)})**\n" + "".join(self.gold_preds)
        if self.std_preds:
            msg += f"🥈 **STANDARD-TIER ({len(self.std_preds)})**\n" + "".join(self.std_preds)
        
        if not self.gold_preds and not self.std_preds:
            msg += "No actionable matches found.\n\n"
            
        # --- AUTOMATED 3-LEG SLIP (SAFE) ---
        if len(self.combo_candidates) >= 2:
            sorted_candidates = sorted(self.combo_candidates, key=lambda x: x["odds"])
            combo_picks = sorted_candidates[:3]
            
            total_odds = 1.0
            combo_text_lines = []
            for pick in combo_picks:
                total_odds *= pick["odds"]
                combo_text_lines.append(f" ↳ {pick['text']} @ {pick['odds']:.2f}")
                
            msg += "🔥 **RECOMMENDED TITAN COMBINATION TICKET** 🔥\n"
            msg += "\n".join(combo_text_lines) + "\n"
            msg += f"📈 **Estimated Total Odds:** {total_odds:.2f}\n"
            msg += f"💰 **Suggested Stake:** 100 KES\n\n"

        # --- AUTOMATED UNLIMITED MEGA-TICKET (HIGH RISK) ---
        if len(self.mega_combo_candidates) >= 4:
            # Sort all available matches (Gold + Standard) by lowest odds (Safest first)
            sorted_mega = sorted(self.mega_combo_candidates, key=lambda x: x["odds"])
            # Take ALL matches that cleared the filter (No limit)
            mega_picks = sorted_mega
            
            mega_odds = 1.0
            mega_text_lines = []
            for pick in mega_picks:
                mega_odds *= pick["odds"]
                mega_text_lines.append(f" ↳ {pick['text']} @ {pick['odds']:.2f}")
                
            msg += f"🧨 **TITAN {len(mega_picks)}-LEG MEGA-TICKET (HIGH RISK)** 🧨\n"
            msg += "\n".join(mega_text_lines) + "\n"
            msg += f"📈 **Estimated Total Odds:** {mega_odds:.2f}\n"
            msg += f"💰 **Suggested Stake:** 20 KES\n\n"

        # SYSTEM DIAGNOSTICS
        msg += "⚙️ **SYSTEM DIAGNOSTICS** ⚙️\n"
        msg += f"↳ API Status: {self.api_status}\n"
        msg += f"↳ Raw Matches Scanned: {self.raw_match_count}\n"
        msg += "↳ Bankroll: 100 KES/match"

        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    engine = MegaTicketVolumeSieve()
    engine.process_matrix()
    engine.dispatch_alerts()
