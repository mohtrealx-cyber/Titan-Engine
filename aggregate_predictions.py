import os
import glob
import json
from datetime import datetime
from collections import defaultdict
from difflib import SequenceMatcher

def normalize_name(name: str) -> str:
    """Cleans team names to enable accurate cross-platform matching."""
    name = name.lower().strip()
    replacements = {
        " utd": " united",
        " fc": "",
        " sc": "",
        " afc": "",
        " st ": " saint ",
        " & ": " and ",
    }
    for old, new in replacements.items():
        name = name.replace(old, new)
    return "".join(c for c in name if c.isalnum() or c.isspace()).strip()

def teams_match(team1: str, team2: str, threshold: float = 0.80) -> bool:
    """Fuzzy checks if two team names refer to the same club."""
    n1, n2 = normalize_name(team1), normalize_name(team2)
    if n1 == n2 or n1 in n2 or n2 in n1:
        return True
    return SequenceMatcher(None, n1, n2).ratio() >= threshold

def load_today_predictions():
    """Loads all prediction JSON files generated for today's date."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    pattern = f"data/predictions_*_{today_str}.json"
    files = glob.glob(pattern)
    
    all_source_data = {}
    for filepath in files:
        # Extract source name from filename: data/predictions_SOURCE_YYYY-MM-DD.json
        source_name = os.path.basename(filepath).split("_")[1]
        try:
            with open(filepath, "r") as f:
                all_source_data[source_name] = json.load(f)
            print(f"Loaded {len(all_source_data[source_name])} picks from [{source_name.upper()}]")
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
            
    return all_source_data

def aggregate_matches(source_data):
    """Groups predictions across sources by matching Home and Away teams."""
    matched_fixtures = []

    # Use the first source as the base benchmark
    sources = list(source_data.keys())
    if not sources:
        print("No prediction files found for today.")
        return []

    base_source = sources[0]
    base_matches = source_data[base_source]

    for base_m in base_matches:
        fixture_entry = {
            "Home": base_m["Home"],
            "Away": base_m["Away"],
            "Predictions": {
                base_source: {
                    "Pick": base_m.get("Prediction"),
                    "Score": base_m.get("Correct_Score"),
                    "Stake": base_m.get("Stake", "N/A"),
                    "Odds_1": base_m.get("Odds_1"),
                    "Odds_X": base_m.get("Odds_X"),
                    "Odds_2": base_m.get("Odds_2")
                }
            }
        }

        # Compare against all other available sources
        for other_source in sources[1:]:
            for other_m in source_data[other_source]:
                if teams_match(base_m["Home"], other_m["Home"]) and teams_match(base_m["Away"], other_m["Away"]):
                    fixture_entry["Predictions"][other_source] = {
                        "Pick": other_m.get("Prediction"),
                        "Score": other_m.get("Correct_Score"),
                        "Stake": other_m.get("Stake", "N/A"),
                        "Odds_1": other_m.get("Odds_1"),
                        "Odds_X": other_m.get("Odds_X"),
                        "Odds_2": other_m.get("Odds_2")
                    }
                    break

        matched_fixtures.append(fixture_entry)

    return matched_fixtures

def generate_consensus_report(matched_fixtures):
    """Filters fixtures to highlight high-consensus picks."""
    consensus_results = []

    for fixture in matched_fixtures:
        picks = [data["Pick"] for data in fixture["Predictions"].values() if data["Pick"]]
        if not picks:
            continue

        total_sources = len(fixture["Predictions"])
        pick_counts = defaultdict(int)
        for p in picks:
            pick_counts[p] += 1

        # Find majority outcome
        top_pick, max_votes = max(pick_counts.items(), key=lambda x: x[1])
        agreement_rate = round((max_votes / total_sources) * 100, 1)

        # Average available odds for the chosen outcome
        odd_key = f"Odds_{top_pick}"
        odds_list = [
            data[odd_key] for data in fixture["Predictions"].values() 
            if data.get(odd_key) is not None and isinstance(data.get(odd_key), (int, float))
        ]
        avg_odds = round(sum(odds_list) / len(odds_list), 2) if odds_list else None

        consensus_results.append({
            "Match": f"{fixture['Home']} vs {fixture['Away']}",
            "Consensus_Pick": top_pick,
            "Agreement_Rate": f"{agreement_rate}%",
            "Sources_Agreed": f"{max_votes}/{total_sources}",
            "Average_Odds": avg_odds,
            "Breakdown": fixture["Predictions"]
        })

    # Sort picks by highest agreement rate first
    consensus_results.sort(key=lambda x: float(x["Agreement_Rate"].replace("%", "")), reverse=True)
    return consensus_results

if __name__ == "__main__":
    print("========================================")
    print("    STARTING TITAN ENGINE AGGREGATOR    ")
    print("========================================")

    data = load_today_predictions()
    if data:
        fixtures = aggregate_matches(data)
        consensus = generate_consensus_report(fixtures)

        today_str = datetime.now().strftime("%Y-%m-%d")
        output_file = f"data/consensus_{today_str}.json"

        with open(output_file, "w") as f:
            json.dump(consensus, f, indent=4)

        print(f"\nSuccessfully generated consensus report for {len(consensus)} matches.")
        print(f"Saved aggregated report to {output_file}")
