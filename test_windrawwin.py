import os
import sys
import json
import google.generativeai as genai

print("========================================")
print("  STARTING TITAN ENGINE LLM PARSER")
print("========================================")

# Make sure to set your GEMINI_API_KEY environment variable!
API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    print("ERROR: GEMINI_API_KEY environment variable not found!")
    sys.exit(1)

genai.configure(api_key=API_KEY)

# We use 1.5 Flash for speed, and strictly enforce JSON output
model = genai.GenerativeModel(
    "gemini-1.5-flash",
    generation_config={"response_mime_type": "application/json"}
)

def parse_predictions(input_file="windrawwin_ready_for_llm.json", output_file="titan_engine_final.json"):
    if not os.path.exists(input_file):
        print(f"ERROR: {input_file} not found.")
        return

    with open(input_file, "r") as f:
        raw_matches = json.load(f)

    print(f"Loaded {len(raw_matches)} raw matches.")
    
    # We will test the first 3 matches first to verify the schema is working perfectly
    test_batch = raw_matches[:3]
    print(f"Sending batch of {len(test_batch)} to the LLM for parsing...\n")

    system_prompt = """
    You are a sports data extraction engine. 
    I will provide a JSON array of football matches. Each match contains a 'Raw_Data_Block' of unstructured text.
    Your job is to extract the betting prediction and odds, and return a JSON array of objects following this exact schema:
    [
      {
        "Home": "Home Team Name",
        "Away": "Away Team Name",
        "Prediction": "1" for Home Win, "X" for Draw, "2" for Away Win,
        "Correct_Score": "e.g., 1-1 or 2-0",
        "Stake": "Small, Medium, or Large",
        "Odds_1": "Convert fractional home odds to decimal float (e.g., 13/10 = 2.30)",
        "Odds_X": "Convert fractional draw odds to decimal float",
        "Odds_2": "Convert fractional away odds to decimal float"
      }
    ]
    Extract the odds immediately following the '1 X 2' text in the block.
    """

    prompt = system_prompt + "\n\nRaw Match Data:\n" + json.dumps(test_batch, indent=2)

    try:
        response = model.generate_content(prompt)
        parsed_data = json.loads(response.text)
        
        print("--- LLM PARSING SUCCESSFUL ---")
        print(json.dumps(parsed_data, indent=4))
        
        with open(output_file, "w") as f:
            json.dump(parsed_data, f, indent=4)
        print(f"\nSaved structured data to {output_file}")
        
    except Exception as e:
        print(f"Error during LLM parsing: {e}")

if __name__ == "__main__":
    parse_predictions()
