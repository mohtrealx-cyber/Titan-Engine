import os
import json
import time
import threading
import requests
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime
import google.generativeai as genai

# ==========================================
# CONFIGURATION & THREAD-SAFE FILE LOCKS
# ==========================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

PENDING_FILE = "pending_tickets.json"
LOCK_FILE = "lock_state.json"
FILE_LOCK = threading.Lock()

# Auto-updating TLS fingerprint scraper
scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    # Replaced hardcoded model with dynamic path
    ai_model = genai.GenerativeModel('gemini-1.5-pro-latest')

# ==========================================
# MEMORY & LOCK MANAGEMENT
# ==========================================
def load_json(filepath):
    with FILE_LOCK:
        if not os.path.exists(filepath):
            return {}
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_json(filepath, data):
    with FILE_LOCK:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)

def get_today_str():
    return datetime.utcnow().strftime("%Y-%m-%d")

def is_locked_today():
    lock_data = load_json(LOCK_FILE)
    return lock_data.get("lock_date") == get_today_str()

def set_daily_lock():
    save_json(LOCK_FILE, {"lock_date": get_today_str()})

# ==========================================
# SCRAPER ENGINE 
# ==========================================
def scrape_consensus():
    """
    Simulates scraping Statarea, Vitibet, PredictZ, and WinDrawWin.
    Returns consensus matches (3+ sites agreement).
    """
    # In production, implement the specific BeautifulSoup logic here
    # Example raw consensus structure returned:
    return [
        {"match": "Arda Kardzhali vs Slavia Sofia", "prediction": "1", "sites": "PredictZ + Vitibet + WinDrawWin"},
        {"match": "Viborg vs Odense Bk", "prediction": "1", "sites": "PredictZ + Vitibet + Statarea"},
        {"match": "Sk Prostejov vs Trinec", "prediction": "1", "sites": "PredictZ + Vitibet + WinDrawWin"}
    ]

def scrape_live_score(match_name):
    """
    Scrapes Statarea to find the final score of a match.
    Returns the score string (e.g., "2-1") or None if not finished.
    """
    # Replace with actual Statarea target URL and BS4 parsing
    # Simulated response logic:
    return None # Return None if live/upcoming, or "2-1" if finished

# ==========================================
# AI OPTIMIZATION ENGINE
# ==========================================
def generate_ai_tickets(consensus_data):
    """
    Passes consensus data to the AI model to generate optimized tickets in strict JSON format.
    Enforces League Tier Restrictions (no corner markets in minor leagues).
    """
    prompt = f"""
    You are Titan AI, an elite quantitative sports betting model.
    Analyze this raw consensus data: {json.dumps(consensus_data)}
    
    Rules:
    1. Output strictly valid JSON.
    2. Do NOT select corner markets for minor/untradeable leagues (League Tier Restriction).
    3. Generate 4 tickets: Ironclad (40%), Balanced (20%), Volatility (10%), Corner Lab (30%).
    4. Each ticket must have a list of matches and exactly one "Reserve Pick".
    
    JSON Schema:
    {{
        "Ironclad": {{"matches": [{{"match": "A vs B", "pick": "1X"}}], "reserve": {{"match": "C vs D", "pick": "1"}}}},
        "Balanced": {{"matches": [], "reserve": {{}}}},
        "Volatility": {{"matches": [], "reserve": {{}}}},
        "Corner_Lab": {{"matches": [], "reserve": {{}}}}
    }}
    """
    
    try:
        response = ai_model.generate_content(prompt)
        # Strip markdown blocks to parse JSON safely
        json_str = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(json_str)
    except Exception as e:
        print(f"AI Generation failed: {e}")
        return None

# ==========================================
# SETTLEMENT ENGINE
# ==========================================
def settle_pending_tickets():
    """
    Reads pending_tickets.json, checks final scores, and grades them.
    Eliminates stale variable bugs by initializing fresh state per match.
    """
    pending = load_json(PENDING_FILE)
    if not pending:
        return []

    settled_reports = []
    unsettled = {}

    for match, data in pending.items():
        prediction = data.get("prediction", "")
        
        # Scrape final score
        score = scrape_live_score(match)
        
        if score:
            if "corner" in prediction.lower():
                status = "MANUAL CHECK 🟡"
            else:
                # Basic 1X2 settlement logic based on score
                home, away = map(int, score.split("-"))
                if (prediction == "1" and home > away) or \
                   (prediction == "1X" and home >= away) or \
                   (prediction == "2" and away > home):
                    status = "WON 🟢"
                else:
                    status = "LOST 🔴"
            
            settled_reports.append(f"• **{match}** ➔ **{status}** (Score: {score})")
        else:
            # Match is still live or upcoming
            unsettled[match] = data

    # Save only the matches that haven't finished yet back to memory
    save_json(PENDING_FILE, unsettled)
    return settled_reports

# ==========================================
# TELEGRAM INTEGRATION
# ==========================================
def send_telegram_message(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials missing. Outputting to console instead:\n")
        print(text)
        return
        
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    
    try:
        requests.post(url, json=payload, timeout=10)
    except requests.exceptions.RequestException as e:
        print(f"Failed to send Telegram message: {e}")

# ==========================================
# MAIN WORKFLOW
# ==========================================
def main():
    print("Initializing Titan Quant Engine...")
    message_blocks = []

    # 1. Settle Yesterday's / Earlier Matches
    settled_results = settle_pending_tickets()
    if settled_results:
        block = "📊 **SETTLED RESULTS (Newly Finalized)** 📊\n\n"
        block += "\n".join(settled_results)
        message_blocks.append(block)

    # 2. Check Daily Lock
    if is_locked_today():
        print("Predictions locked for today. Only returning settled results.")
        scraper_status = f"⚙️ **SCRAPER STATUS** ⚙️\n↳ Daily_Lock: LOCKED ON {get_today_str()}"
        message_blocks.append(scraper_status)
        
        if message_blocks:
             send_telegram_message("\n\n***\n\n".join(message_blocks))
        return

    # 3. Scrape New Consensus
    consensus_data = scrape_consensus()
    if not consensus_data:
        send_telegram_message("⚠️ Scraper Error: No consensus data found today.")
        return
        
    raw_block = "🤝 **RAW CONSENSUS DATA (3+ SITES AGREEMENT)** 🤝\n\n"
    for item in consensus_data:
        raw_block += f"• **{item['match']}** ➔ {item['prediction']}\n"
        raw_block += f"  ↳ Backed by: `{item['sites']}`\n\n"
    message_blocks.append(raw_block.strip())

    # 4. Generate AI Tickets
    ai_tickets = generate_ai_tickets(consensus_data)
    pending_to_save = {}
    
    if ai_tickets:
        ai_block = "🤖 **TITAN AI OPTIMIZED TICKETS** 🤖\n\n"
        
        allocations = {
            "Ironclad": "40% of Daily Stake",
            "Balanced": "20% of Daily Stake",
            "Volatility": "10% of Daily Stake",
            "Corner_Lab": "30% of Daily Stake"
        }
        
        for index, (ticket_name, ticket_data) in enumerate(ai_tickets.items(), 1):
            ai_block += f"🛡️ Ticket {index}: {ticket_name.replace('_', ' ')} ({allocations.get(ticket_name, 'Stake')})\n"
            
            for m in ticket_data.get("matches", []):
                ai_block += f"• **{m['match']}** ➔ {m['pick']}\n"
                pending_to_save[m['match']] = {"prediction": m['pick']}
                
            reserve = ticket_data.get("reserve", {})
            if reserve:
                ai_block += f"🔄 [RESERVE PICK]: **{reserve['match']}** ➔ {reserve['pick']}\n"
                pending_to_save[reserve['match']] = {"prediction": reserve['pick']}
                
            ai_block += "\n"
            
        message_blocks.append(ai_block.strip())
    else:
        message_blocks.append("⚠️ AI Engine failed to generate valid tickets.")

    # 5. Scraper Status & Locking
    scraper_status = f"⚙️ **SCRAPER STATUS** ⚙️\n↳ Daily_Lock: LOCKED ON {get_today_str()}"
    message_blocks.append(scraper_status)

    # 6. Save Memory and Dispatch
    # Append to existing pending memory (don't overwrite unsettled live matches)
    current_pending = load_json(PENDING_FILE)
    current_pending.update(pending_to_save)
    save_json(PENDING_FILE, current_pending)
    
    set_daily_lock()

    # 7. Send Final Payload
    final_message = "\n\n***\n\n".join(message_blocks)
    send_telegram_message(final_message)
    print("Execution complete. Message dispatched.")

if __name__ == "__main__":
    main()
