# ==============================================================================
# MODULE D: LIVE ODDS VALUE EXPLOITER (LOGIC TEST)
# ==============================================================================

def calculate_value_exploit(ai_win_probability_pct, bookmaker_odds):
    """
    Compares the AI's mathematical probability against the bookmaker's payout
    to identify profitable market inefficiencies (+EV).
    """
    # Convert AI percentage to a decimal
    bot_prob_decimal = ai_win_probability_pct / 100
    
    # Calculate True Odds (What the odds SHOULD be to break even)
    true_odds = 1 / bot_prob_decimal if bot_prob_decimal > 0 else 0
    
    # Calculate Expected Value (EV) Percentage
    ev_percentage = (bot_prob_decimal * bookmaker_odds) - 1
    
    # Logic Gate: Is the bookie paying more than the mathematical True Odds?
    if bookmaker_odds > true_odds:
        return True, true_odds, (ev_percentage * 100)
    else:
        return False, true_odds, (ev_percentage * 100)

# ==============================================================================
# SIMULATION SEQUENCE
# ==============================================================================
if __name__ == "__main__":
    print("[*] Initializing Value Exploit Scanner...\n")

    # Scenario 1: A match where Betika offers great odds
    match_1 = "Spain vs Austria"
    ai_confidence_1 = 65.0      # Fortress calculated a 65% win probability
    betika_odds_1 = 1.95        # Betika is paying 1.95 for the win

    print(f"--- SCENARIO 1: {match_1} ---")
    is_exploit_1, true_odds_1, ev_1 = calculate_value_exploit(ai_confidence_1, betika_odds_1)
    print(f"Fortress True Odds: {true_odds_1:.2f} (Required to break even)")
    print(f"Betika Live Odds:   {betika_odds_1}")
    
    if is_exploit_1:
        print(f"🚨 [VALUE EXPLOIT] +{ev_1:.1f}% Expected Value. The bookie is wrong. PLAY IT!\n")
    else:
        print(f"❌ [BAD VALUE] {ev_1:.1f}% Expected Value. The house wins. SKIP IT.\n")


    # Scenario 2: A match where the team will probably win, but the payout is terrible
    match_2 = "Chelsea vs Arsenal"
    ai_confidence_2 = 80.0      # Fortress is highly confident Chelsea wins
    betika_odds_2 = 1.15        # But Betika is only paying a tiny 1.15

    print(f"--- SCENARIO 2: {match_2} ---")
    is_exploit_2, true_odds_2, ev_2 = calculate_value_exploit(ai_confidence_2, betika_odds_2)
    print(f"Fortress True Odds: {true_odds_2:.2f} (Required to break even)")
    print(f"Betika Live Odds:   {betika_odds_2}")
    
    if is_exploit_2:
        print(f"🚨 [VALUE EXPLOIT] +{ev_2:.1f}% Expected Value. The bookie is wrong. PLAY IT!\n")
    else:
        print(f"❌ [BAD VALUE] {ev_2:.1f}% Expected Value. The house wins. SKIP IT.\n")
