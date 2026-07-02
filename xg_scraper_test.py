# ==============================================================================
# PROJECT FORTRESS: PHASE 3 - LIVE TELEGRAM TRANSMISSION
# ==============================================================================
import os
import requests
from understatapi import UnderstatClient

# Pull secure credentials from GitHub Actions vault
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_alert(message):
    """Pushes the mathematical analysis directly to your Telegram inbox."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[-] Telegram credentials missing. Ensure secrets are loaded in the .yml file.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("[+] Telegram alert successfully delivered!")
        else:
            print(f"[-] Telegram delivery failed: {response.text}")
    except Exception as e:
        print(f"[-] Telegram API Error: {e}")

def calculate_pure_probability(home_xg, away_xg):
    """Converts live rolling xG metrics into true match probabilities."""
    total_xg = home_xg + away_xg
    if total_xg == 0: 
        return 33.3, 33.3, 33.3
        
    home_raw_pct = (home_xg / total_xg) * 100
    away_raw_pct = (away_xg / total_xg) * 100
    
    # Apply standard Home Field Advantage modifier
    home_advantage_pct = home_raw_pct + 5.0
    away_adjusted_pct = away_raw_pct - 5.0
    
    # Estimate Draw decay based on statistical variance
    xg_difference = abs(home_xg - away_xg)
    draw_pct = 28.0 - (xg_difference * 5) 
    draw_pct = max(15.0, min(draw_pct, 35.0))
    
    remaining_pct = 100.0 - draw_pct
    total_adjusted_strength = home_advantage_pct + away_adjusted_pct
    
    home_final_prob = (home_advantage_pct / total_adjusted_strength) * remaining_pct
    away_final_prob = (away_adjusted_pct / total_adjusted_strength) * remaining_pct
    
    return home_final_prob, draw_pct, away_final_prob

def get_live_team_xg(team_name, season="2023"):
    """Queries the backend database endpoints for live metrics."""
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
    except Exception as e:
        print(f"[-] API Error for {team_name}: {e}")
    return None

# ==============================================================================
# RUN ENGINE & TRANSMIT
# ==============================================================================
if __name__ == "__main__":
    print("=== PROJECT FORTRESS: PHASE 3 LIVE FUSION ===\n")
    
    home_team = "Chelsea"
    away_team = "Liverpool"
    
    print(f"[*] Querying live database for {home_team} vs {away_team}...")
    home_xg = get_live_team_xg(home_team)
    away_xg = get_live_team_xg(away_team)
    
    if home_xg and away_xg:
        h_prob, d_prob, a_prob = calculate_pure_probability(home_xg, away_xg)
        
        # Construct the Markdown payload for the Telegram alert
        tg_message = (
            "🛡️ *PROJECT FORTRESS: QUANT ENGINE* 🛡️\n\n"
            f"⚽ *Matchup:* {home_team} vs {away_team}\n\n"
            "📊 *Raw xG Ingestion:*\n"
            f"• {home_team}: `{home_xg:.2f}`\n"
            f"• {away_team}: `{away_xg:.2f}`\n\n"
            "🧮 *Mathematical Win Probability:*\n"
            f"• 1 (Home): `{h_prob:.1f}%`\n"
            f"• X (Draw): `{d_prob:.1f}%`\n"
            f"• 2 (Away): `{a_prob:.1f}%`\n\n"
            "_Status: Phase 3 Active. Awaiting Round Execution._"
        )
        
        print("[*] Transmitting intelligence to Telegram...")
        send_telegram_alert(tg_message)
    else:
        print("[-] Data pipeline failed to compile metrics.")
