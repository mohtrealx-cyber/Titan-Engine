import os
import json
import logging
import requests
from bs4 import BeautifulSoup
from curl_cffi import requests as tls_requests

# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

MEMORY_FILE = "pending_tickets.json"

# ==========================================
# SCRAPER 1: VITIBET
# ==========================================
def scrape_vitibet():
    url = "https://www.vitibet.com/index.php?clanek=quicktips&sekce=fotbal&lang=en"
    matches = []
    try:
        response = tls_requests.get(url, impersonate="chrome110", timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "lxml")
            # Parse table rows (Adjust selectors based on page structure)
            rows = soup.find_all("tr")
            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 4:
                    match_name = cols[0].get_text(strip=True)
                    tip = cols[3].get_text(strip=True)
                    if match_name and tip in ["1", "X", "2", "1X", "X2"]:
                        matches.append({"match": match_name, "tip": tip, "source": "Vitibet"})
            logging.info(f"Vitibet: Found {len(matches)} matches.")
        else:
            logging.warning(f"Vitibet HTTP Error: {response.status_code}")
    except Exception as e:
        logging.error(f"Vitibet Scraper failed: {e}")
    return matches

# ==========================================
# SCRAPER 2: STATAREA
# ==========================================
def scrape_statarea():
    url = "https://www.statarea.com/predictions"
    matches = []
    try:
        response = tls_requests.get(url, impersonate="chrome110", timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "lxml")
            # Parse predictions
            for item in soup.select(".prediction"):
                match_name = item.select_one(".match_name")
                tip = item.select_one(".tip_value")
                if match_name and tip:
                    matches.append({
                        "match": match_name.get_text(strip=True),
                        "tip": tip.get_text(strip=True),
                        "source": "Statarea"
                    })
            logging.info(f"Statarea: Found {len(matches)} matches.")
        else:
            logging.warning(f"Statarea HTTP Error: {response.status_code}")
    except Exception as e:
        logging.error(f"Statarea Scraper failed: {e}")
    return matches

# ==========================================
# SCRAPER 3: WINDRAWWIN (Proxy Enabled)
# ==========================================
def scrape_windrawwin():
    target_url = "https://www.windrawwin.com/predictions/today/"
    scraper_key = os.getenv("SCRAPER_API_KEY")
    matches = []

    try:
        # Route through ScraperAPI if key exists to bypass Cloudflare IP blocks
        if scraper_key:
            logging.info("Routing WinDrawWin via ScraperAPI residential proxy...")
            api_url = f"http://api.scraperapi.com?api_key={scraper_key}&url={target_url}&keep_headers=true"
            response = requests.get(api_url, timeout=30)
        else:
            logging.info("No ScraperAPI key found. Reverting to direct TLS request...")
            response = tls_requests.get(target_url, impersonate="chrome110", timeout=15)

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "lxml")
            # Parse match table
            rows = soup.select("table tr")
            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 3:
                    match_name = cols[0].get_text(strip=True)
                    tip = cols[2].get_text(strip=True)
                    if match_name and tip:
                        matches.append({
                            "match": match_name,
                            "tip": tip,
                            "source": "WinDrawWin"
                        })
            logging.info(f"WinDrawWin: Successfully fetched {len(matches)} predictions.")
        else:
            logging.warning(f"WinDrawWin HTTP Error: {response.status_code}")
    except Exception as e:
        logging.error(f"WinDrawWin Scraper failed: {e}")
    
    return matches

# ==========================================
# SCRAPER 4: PREDICTZ
# ==========================================
def scrape_predictz():
    url = "https://www.predictz.com/predictions/today/"
    matches = []
    try:
        response = tls_requests.get(url, impersonate="chrome110", timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "lxml")
            for row in soup.select("table.ptable tr"):
                cols = row.find_all("td")
                if len(cols) >= 3:
                    match_name = cols[0].get_text(strip=True)
                    tip = cols[1].get_text(strip=True)
                    if match_name and tip:
                        matches.append({
                            "match": match_name,
                            "tip": tip,
                            "source": "PredictZ"
                        })
            logging.info(f"PredictZ: Found {len(matches)} matches.")
        else:
            logging.warning(f"PredictZ HTTP Error: {response.status_code}")
    except Exception as e:
        logging.error(f"PredictZ Scraper failed: {e}")
    return matches

# ==========================================
# CONSENSUS ENGINE & TELEGRAM DISPATCH
# ==========================================
def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}

def save_memory(data):
    with open(MEMORY_FILE, "w") as f:
        json.dump(data, f, indent=4)

def send_telegram(message):
    token = os.getenv("QUANT_TELEGRAM_TOKEN")
    chat_id = os.getenv("QUANT_TELEGRAM_CHAT_ID")
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            logging.error(f"Failed to send Telegram message: {e}")
    else:
        logging.warning("Telegram credentials missing. Output printed to console.")
        print(message)

def run_quant_engine():
    logging.info("Starting Quant Engine...")
    
    # 1. Gather Predictions
    v_data = scrape_vitibet()
    s_data = scrape_statarea()
    w_data = scrape_windrawwin()
    p_data = scrape_predictz()

    all_scrapes = v_data + s_data + w_data + p_data
    
    # 2. Match Aggregation
    consensus_map = {}
    for item in all_scrapes:
        key = item["match"].lower()
        if key not in consensus_map:
            consensus_map[key] = {"display_name": item["match"], "sources": [], "tips": []}
        consensus_map[key]["sources"].append(item["source"])
        consensus_map[key]["tips"].append(item["tip"])

    # 3. Apply Consensus Filter (Requires at least 2 scrapers agreeing)
    qualified_matches = []
    for key, val in consensus_map.items():
        if len(val["sources"]) >= 2:
            qualified_matches.append(val)

    # 4. Generate Report
    status_v = f"OK ({len(v_data)} items)" if v_data else "NO DATA / BLOCKED"
    status_s = f"OK ({len(s_data)} items)" if s_data else "NO DATA / BLOCKED"
    status_w = f"OK ({len(w_data)} items)" if w_data else "NO DATA / BLOCKED"
    status_p = f"OK ({len(p_data)} items)" if p_data else "NO DATA / BLOCKED"

    report = ""
    if len(qualified_matches) < 3:
        report += "<b>SYSTEM OVERRIDE: LOW VOLUME (NO BET DAY)</b>\n\n"
        report += f"The engine only found <b>{len(qualified_matches)}</b> matches that passed the strict consensus filter today.\n\n"
        report += "<b>Verdict: NOT SAFE TO BET.</b> Preserve your bankroll for a better board.\n\n"
        
        if qualified_matches:
            report += "<i>(Matches found for monitoring purposes only:)</i>\n"
            for q in qualified_matches:
                sources_str = " + ".join(q["sources"])
                report += f"• <b>{q['display_name']}</b> ➔ {q['tips'][0]}\n  ↳ Backed by: <code>{sources_str}</code>\n"
            report += "\n"
    else:
        report += f"<b>QUANT ENGINE: QUALIFIED BETSLIP ({len(qualified_matches)} MATCHES)</b>\n\n"
        for q in qualified_matches:
            sources_str = " + ".join(q["sources"])
            report += f"• <b>{q['display_name']}</b> ➔ {q['tips'][0]}\n  ↳ Backed by: <code>{sources_str}</code>\n"
        report += "\n"

    report += "<b>SCRAPER STATUS</b>\n"
    report += f"↳ Vitibet: {status_v}\n"
    report += f"↳ Statarea: {status_s}\n"
    report += f"↳ WinDrawWin: {status_w}\n"
    report += f"↳ PredictZ: {status_p}\n"

    # 5. Dispatch
    send_telegram(report)

if __name__ == "__main__":
    run_quant_engine()
