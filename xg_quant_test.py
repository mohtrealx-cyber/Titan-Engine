# ==============================================================================
# MODULE F: RAW STATISTICAL QUANT ENGINE (xG LOGIC TEST)
# ==============================================================================

def calculate_pure_probability(home_xg, away_xg):
    """
    Converts rolling Expected Goals (xG) averages into a match probability.
    In a production model, this uses advanced Poisson Distribution math.
    For this module test, we use a weighted power ratio.
    """
    print(f"[*] Analyzing Raw Data: Home xG [{home_xg}] vs Away xG [{away_xg}]")
    
    # Calculate the total expected action in the match
    total_xg = home_xg + away_xg
    
    if total_xg == 0:
        return 33.3, 33.3, 33.3 # Dead heat prediction if no data
        
    # Standardize the raw metrics into raw percentages
    home_raw_pct = (home_xg / total_xg) * 100
    away_raw_pct = (away_xg / total_xg) * 100
    
    # Apply a standard Home Field Advantage modifier (+5% baseline)
    home_advantage_pct = home_raw_pct + 5.0
    away_adjusted_pct = away_raw_pct - 5.0
    
    # Estimate the Draw probability (usually hovers around 24% in elite football,
    # but increases if the teams have very similar xG ratings)
    xg_difference = abs(home_xg - away_xg)
    draw_pct = 28.0 - (xg_difference * 5) 
    draw_pct = max(15.0, min(draw_pct, 35.0)) # Hard limits for football reality
    
    # Finalize the probabilities
    remaining_pct = 100.0 - draw_pct
    total_adjusted_strength = home_advantage_pct + away_adjusted_pct
    
    home_final_prob = (home_advantage_pct / total_adjusted_strength) * remaining_pct
    away_final_prob = (away_adjusted_pct / total_adjusted_strength) * remaining_pct
    
    return home_final_prob, draw_pct, away_final_prob

# ==============================================================================
# SIMULATION SEQUENCE
# ==============================================================================
if __name__ == "__main__":
    print("=== INITIATING PHASE 3: PURE STATISTICAL QUANT ENGINE ===\n")
    
    # Test 1: A massive mismatch
    match_1 = "Spain vs Austria"
    spain_xg = 2.45   # Spain is incredibly dangerous right now
    austria_xg = 0.82 # Austria struggles to create quality chances
    
    print(f"--- MATCHUP: {match_1} ---")
    h_prob, d_prob, a_prob = calculate_pure_probability(spain_xg, austria_xg)
    print(f"Prediction Output:")
    print(f"1 (Home): {h_prob:.1f}% | X (Draw): {d_prob:.1f}% | 2 (Away): {a_prob:.1f}%\n")

    # Test 2: A highly contested match
    match_2 = "Chelsea vs Liverpool"
    chelsea_xg = 1.65
    liverpool_xg = 1.70
    
    print(f"--- MATCHUP: {match_2} ---")
    h_prob, d_prob, a_prob = calculate_pure_probability(chelsea_xg, liverpool_xg)
    print(f"Prediction Output:")
    print(f"1 (Home): {h_prob:.1f}% | X (Draw): {d_prob:.1f}% | 2 (Away): {a_prob:.1f}%\n")
