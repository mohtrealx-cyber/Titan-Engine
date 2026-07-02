import os
import sys
import csv
from datetime import datetime
import requests
from bs4 import BeautifulSoup

# =====================================================================
# 1. SECURITY & CONFIGURATION SETTINGS
# =====================================================================
# Secret Vault Retrieval (Hides your private tokens from the public)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# --- USER PROFILE BANKROLL & STRATEGY ---
CURRENT_BANKROLL = 10000   # Set your total bankroll here in KShs
ACTIVE_STRATEGY = "Titan"   # Tag options: Titan, Fortress, Velocity, Lone Wolf
CSV_FILE_PATH = "betting_performance_history.csv"


# =====================================================================
# 2. CORE MATHEMATICAL UTILITIES
# =====================================================================
def calculate_stakes(bankroll):
    """
    Executes the strict 1-3% money management formula.
    Returns calculated values rounded to the nearest Shilling.
    """
    conservative = bankroll * 0.01
    standard = bankroll * 0.02
    aggressive = bankroll * 0.03
    return conservative, standard, aggressive


# =====================================================================
# 3. TELEGRAM NOTIFICATION ENGINE
# =====================================================================
def send_telegram_alert(match_name, prediction, odds="N/A"):
    """
    Formats and transmits a high-visibility structural alert 
    directly to your mobile device via Telegram API.
    """
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[-] Error: Missing Telegram credentials in environment vault.")
        return

    # Calculate stakes dynamically based on CURRENT_BANKROLL
    cons, std, agg = calculate_stakes(CURRENT_BANKROLL)

    # Build the clean structured message block
    message = (
        f"🚨 [STRONG] SIGNAL DETECTED 🚨\n\n"
        f"⚙️ Strategy Engine: {ACTIVE_STRATEGY}\n"
        f"⚽ Match: {match_name}\n"
        f"🎯 Prediction: {prediction}\n"
        f"📊 Average Odds: {odds}\n\n"
        f"💰 RECOMMENDED STAKING (KShs):\n"
        f"• Conservative (1%): {cons:,.0f} KShs\n"
        f"• Standard (2%): {std:,.0f} KShs\n"
        f"• Aggressive (3%): {agg:,.0f} KShs\n\n"
        f"🤖 Automated via GitHub Actions Cloud Engine."
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"[+] Success: Alert pushed to phone for {match_name}")
        else:
            print(f"[-] Broadcast failure: {response.text}")
    except Exception as e:
        print(f"[-] Connection Error to Telegram Endpoint: {e}")


# =====================================================================
# 4. AUTO-LOGGING TRAJECTORY ENGINE
# =====================================================================
def log_to_history(match_name, prediction, odds="N/A"):
    """
    Automatically logs identified high-confidence signals directly 
    into the tracking CSV file for consistency checks.
    """
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    file_exists = os.path.exists(CSV_FILE_PATH)
    
    try:
        with open(CSV_FILE_PATH, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            
            # Create structural headers if file is fresh
            if not file_exists:
                writer.writerow(["Date", "Strategy", "Match", "Prediction", "Odds", "Outcome", "Points"])
            
            # Append rows safely
            writer.writerow([date_str, ACTIVE_STRATEGY, match_name, prediction, odds, "PENDING", "0"])
            print(f"[+] Performance log successfully updated in {CSV_FILE_PATH}")
    except Exception as e:
        print(f"[-] CSV Write Failure: {e}")


# =====================================================================
# 5. CENTRAL SCRAPING HARVESTER
# =====================================================================
def run_main_scraper():
    """
    Executes core scraping sequences.
    """
    print(f"[*] Initializing {ACTIVE_STRATEGY} engine run sequence...")

    # -----------------------------------------------------------------
    # NOTE FOR ENOCK: Place your custom URL requests and BeautifulSoup 
    # parsing code inside this section.
    # -----------------------------------------------------------------
    
    # --- SAMPLE TRIGGER DATA (Used to test if your pipeline works) ---
    # Replace or delete this mock match setup once your live site scraping logic is added
    signal_found = True
    match_discovered = "Liverpool vs Chelsea"
    predicted_outcome = "Over 2.5 Goals"
    estimated_odds = "1.85"
    # -----------------------------------------------------------------

    if signal_found:
        # 1. Fire the dynamic alert to your phone
        send_telegram_alert(match_discovered, predicted_outcome, estimated_odds)
        
        # 2. Append directly to your tracking sheet
        log_to_history(match_discovered, predicted_outcome, estimated_odds)


# =====================================================================
# 6. OPERATIONAL SYSTEM RUNNER
# =====================================================================
if __name__ == "__main__":
    run_main_scraper()
