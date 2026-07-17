import os
import sys
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# Graceful import for curl_cffi to prevent script crashes
try:
    from curl_cffi import requests as curl_requests
except ImportError:
    curl_requests = requests

# =====================================================================
# 1. CORE CONFIGURATION & UTILITIES
# =====================================================================

def normalize_team_name(name):
    """Clean and normalize team names for cross-site matching."""
    if not name:
        return ""
    remove_words = ["fc", "united", "utd", "city", "town", "u23", "u21", "u19", "youth", "afc", "sports", "club"]
    cleaned = name.lower()
    for word in remove_words:
        cleaned = cleaned.replace(f" {word} ", " ").replace(f" {word}", "").replace(f"{word} ", "")
    return "".join(c for c in cleaned if c.isalnum())

def teams_match(team1_a, team1_b, team2_a, team2_b):
    """Fuzzy matching to check if two fixtures refer to the same match."""
    t1_home = normalize_team_name(team1_a)
    t1_away = normalize_team_name(team1_b)
    t2_home = normalize_team_name(team2_a)
    t2_away = normalize_team_name(team2_b)
    
    # Direct match or partial string containment
    home_match = (t1_home in t2_home) or (t2_home in t1_home)
    away_match = (t1_away in t2_away) or (t2_away in t1_away)
    return home_match and away_match

def standardize_prediction(pred_str):
    """Maps various site prediction formats to a unified 1, X, 2 scale."""
    if not pred_str:
        return None
    pred_clean = str(pred_str).strip().lower()
    if pred_clean in ["1", "home", "home win", "h"]:
        return "1"
    if pred_clean in ["x", "draw", "d"]:
        return "X"
    if pred_clean in ["2", "away", "away win", "a"]:
        return "2"
    return None

# =====================================================================
# 2. SITE SCRAPERS
# =====================================================================

def fetch_statarea():
    """Scrapes today's matches and tips from Statarea."""
    matches = []
    status = {"upcoming": 0, "played": 0, "state": "OK"}
    url = "https://www.statarea.com/predictions"
    
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/53.3"}
        response = curl_requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            status["state"] = f"FAILED (HTTP {response.status_code})"
            return matches, status
            
        soup = BeautifulSoup(response.text, 'html.parser')
        match_rows = soup.find_all('div', class_='match')
        
        for row in match_rows:
            try:
                home = row.find('div', class_='home').get_text(strip=True)
                away = row.find('div', class_='away').get_text(strip=True)
                
                # Rigid verification of played status
                status_elem = row.find('div', class_='status')
                status_text = status_elem.get_text(strip=True).lower() if status_elem else ""
                
                # Check for concrete score/FT indicators
                score_elem = row.find('div', class_='matchscore')
                score_text = score_elem.get_text(strip=True) if score_elem else ""
                
                is_played = "ft" in status_text or "ended" in status_text or (score_text and "-" in score_text and any(char.isdigit() for char in score_text))
                
                if is_played:
                    status["played"] += 1
                    continue
                
                # Extract tip prediction
                tip_elem = row.find('div', class_='prediction')
                tip = standardize_prediction(tip_elem.get_text(strip=True)) if tip_elem else None
                
                if home and away and tip:
                    matches.append({"home": home, "away": away, "prediction": tip})
                    status["upcoming"] += 1
            except Exception:
                continue
    except Exception as e:
        status["state"] = f"FAILED ({str(e)})"
        
    return matches, status

def fetch_vitibet():
    """Scrapes today's predictions from Vitibet."""
    matches = []
    status = {"upcoming": 0, "played": 0, "state": "OK"}
    url = "https://www.vitibet.com/index.php?clanek=analyzy&sekce=fotbal&lang=en"
    
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/53.3"}
        response = curl_requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            status["state"] = f"FAILED (HTTP {response.status_code})"
            return matches, status
            
        soup = BeautifulSoup(response.text, 'html.parser')
        table_rows = soup.find_all('tr')
        
        for row in table_rows:
            cols = row.find_all('td')
            if len(cols) < 7:
                continue
                
            try:
                home = cols[1].get_text(strip=True)
                away = cols[2].get_text(strip=True)
                
                # Extract score column safely to determine if match played
                score_text = cols[5].get_text(strip=True)
                is_played = score_text and ":" in score_text and any(char.isdigit() for char in score_text)
                
                if is_played:
                    status["played"] += 1
                    continue
                
                tip = standardize_prediction(cols[6].get_text(strip=True))
                
                if home and away and tip:
                    matches.append({"home": home, "away": away, "prediction": tip})
                    status["upcoming"] += 1
            except Exception:
                continue
    except Exception as e:
        status["state"] = f"FAILED ({str(e)})"
        
    return matches, status

def fetch_predictz():
    """Scrapes today's picks from PredictZ utilizing ScraperAPI routing."""
    matches = []
    status = {"upcoming": 0, "played": 0, "state": "OK"}
    
    api_key = os.getenv("SCRAPER_API_KEY")
    if not api_key:
        status["state"] = "FAILED (Missing ScraperAPI Key)"
        return matches, status
        
    target_url = "https://www.predictz.com/predictions/today/"
    proxy_url = f"http://api.scraperapi.com?api_key={api_key}&url={target_url}"
    
    try:
        response = requests.get(proxy_url, timeout=30)
        if response.status_code != 200:
            status["state"] = f"FAILED (Proxy HTTP {response.status_code})"
            return matches, status
            
        soup = BeautifulSoup(response.text, 'html.parser')
        match_wrappers = soup.find_all('div', class_='ptzmatch')
        
        for wrapper in match_wrappers:
            try:
                home = wrapper.find('div', class_='ptzhome').get_text(strip=True)
                away = wrapper.find('div', class_='ptzaway').get_text(strip=True)
                
                # Check for structural full time score containers
                score_container = wrapper.find('div', class_='ptzscore')
                score_text = score_container.get_text(strip=True) if score_container else ""
                is_played = score_text and "-" in score_text and any(char.isdigit() for char in score_text)
                
                if is_played:
                    status["played"] += 1
                    continue
                
                tip_container = wrapper.find('div', class_='ptztip')
                tip = standardize_prediction(tip_container.get_text(strip=True)) if tip_container else None
                
                if home and away and tip:
                    matches.append({"home": home, "away": away, "prediction": tip})
                    status["upcoming"] += 1
            except Exception:
                continue
    except Exception as e:
        status["state"] = f"FAILED ({str(e)})"
        
    return matches, status

# =====================================================================
# 3. QUANT MATRIX & TICKET SPLITTING LOGIC
# =====================================================================

def run_consensus_matrix(statarea_data, vitibet_data, predictz_data):
    """Cross-references the three data arrays to locate dual or triple agreements."""
    consensus_matches = []
    
    # Process Statarea as the starting validation anchor
    for s_match in statarea_data:
        agreement_count = 1
        matched_sites = ["Statarea"]
        target_prediction = s_match["prediction"]
        
        # Check against Vitibet
        for v_match in vitibet_data:
            if teams_match(s_match["home"], s_match["away"], v_match["home"], v_match["away"]):
                if v_match["prediction"] == target_prediction:
                    agreement_count += 1
                    matched_sites.append("Vitibet")
                break
                
        # Check against PredictZ
        for p_match in predictz_data:
            if teams_match(s_match["home"], s_match["away"], p_match["home"], p_match["away"]):
                if p_match["prediction"] == target_prediction:
                    agreement_count += 1
                    matched_sites.append("PredictZ")
                break
                
        if agreement_count >= 2:
            consensus_matches.append({
                "home": s_match["home"],
                "away": s_match["away"],
                "prediction": target_prediction,
                "agreeing_sites": agreement_count,
                "sources": ", ".join(matched_sites)
            })
            
    # Residual Check: Evaluate overlap strictly between Vitibet and PredictZ 
    # to find pairings skipped if Statarea missed that fixture entirely
    for v_match in vitibet_data:
        # Check if already processed via Statarea loop
        already_found = any(teams_match(v_match["home"], v_match["away"], c["home"], c["away"]) for c in consensus_matches)
        if already_found:
            continue
            
        for p_match in predictz_data:
            if teams_match(v_match["home"], v_match["away"], p_match["home"], p_match["away"]):
                if p_match["prediction"] == v_match["prediction"]:
                    consensus_matches.append({
                        "home": v_match["home"],
                        "away": v_match["away"],
                        "prediction": v_match["prediction"],
                        "agreeing_sites": 2,
                        "sources": "Vitibet, PredictZ"
                    })
                break
                
    return consensus_matches

def generate_and_send_tickets(consensus_matches, scraper_statuses):
    """Splits entries into custom risk hedges and forwards directly to Telegram."""
    token = os.getenv("TRACKER_TELEGRAM_TOKEN")
    chat_id = os.getenv("TRACKER_TELEGRAM_CHAT_ID")
    
    num_matches = len(consensus_matches)
    tickets = []

    # STRATEGY MATRIX: Splitting structure for deep hedging
    if num_matches > 4:
        # Ticket 1: Comprehensive Accumulator
        tickets.append({
            "title": "🏆 TICKET 1: MEGA ACCUMULATOR (All Selections)",
            "meta": "High Volatility | Full Board Matrix Combo",
            "data": consensus_matches
        })
        
        # Midpoint math partition
        midpoint = (num_matches + 1) // 2
        half_a = consensus_matches[:midpoint]
        half_b = consensus_matches[midpoint:]
        
        # Ticket 2: Top Block Split
        tickets.append({
            "title": f"🛡️ TICKET 2: SPLIT COMBO - HALF A ({len(half_a)} Matches)",
            "meta": "Risk Mitigation | Secondary Cover Slip",
            "data": half_a
        })
        
        # Ticket 3: Bottom Block Split
        tickets.append({
            "title": f"🛡️ TICKET 3: SPLIT COMBO - HALF B ({len(half_b)} Matches)",
            "meta": "Risk Mitigation | Tertiary Cover Slip",
            "data": half_b
        })
    elif num_matches > 0:
        tickets.append({
            "title": "📋 STANDARD CONSENSUS TICKET",
            "meta": "Baseline Consensus Accumulator Plan",
            "data": consensus_matches
        })

    # Design output string formatting
    output_message = "⚡ *TITAN QUANT CONSENSUS MATRIX* ⚡\n\n"
    
    if not tickets:
        output_message += "No matches identified with 2+ sites in mutual agreement for today's market windows.\n\n"
    else:
        for ticket in tickets:
            output_message += f"═ {ticket['title']} ═\n"
            output_message += f"ℹ️ _{ticket['meta']}_\n\n"
            
            for idx, match in enumerate(ticket['data'], 1):
                output_message += f"{idx}. ⚽ *{match['home']} vs {match['away']}*\n"
                output_message += f"   📌 *Pick:* Selection {match['prediction']} ({match['sources']})\n\n"
            output_message += "══════════════════════\n\n"

    # Append Diagnostics Dashboard
    output_message += "📊 *SCRAPER STATUS REPORT*\n"
    for site, report in scraper_statuses.items():
        output_message += f"↳ {site}: {report['state']} ({report['upcoming']} Upcoming | {report['played']} Played)\n"

    print(output_message)

    # Fire API request to Telegram Endpoint
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": output_message, "parse_mode": "Markdown"}
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as err:
            print(f"Error handling Telegram output pipe: {err}")

# =====================================================================
# 4. RUNTIME SYSTEM EXECUTION
# =====================================================================

if __name__ == "__main__":
    print("Initializing Data Collection Protocols...")
    
    statarea_picks, statarea_status = fetch_statarea()
    vitibet_picks, vitibet_status = fetch_vitibet()
    predictz_picks, predictz_status = fetch_predictz()
    
    statuses = {
        "Statarea": statarea_status,
        "Vitibet": vitibet_status,
        "PredictZ": predictz_status
    }
    
    print("Evaluating Scraped Sets Through Consensus Core...")
    confirmed_selections = run_consensus_matrix(statarea_picks, vitibet_picks, predictz_picks)
    
    print("Compiling Tickets and Broadcasting Results...")
    generate_and_send_tickets(confirmed_selections, statuses)
