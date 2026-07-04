import os
import time
import requests
from google import genai
from google.genai import errors
from datetime import datetime

def safe_generate(client, model_id, prompt, max_retries=3):
    """Wraps the Gemini API call in a protective retry loop to survive 429 Rate Limits."""
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model_id,
                contents=prompt
            )
            return response.text
        except errors.ClientError as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                print(f"⚠️ API Rate Limit hit! (Attempt {attempt + 1}/{max_retries}). Sleeping for 45 seconds to let the quota reset...")
                time.sleep(45)
            else:
                raise e
    return "⚠️ Error: Max retries exceeded due to rate limits."

def main():
    # 1. Load keys from the secure GitHub environment
    rapidapi_key = os.environ.get("RAPIDAPI_KEY")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    bot_token = os.environ.get("MATCH_BOT_TOKEN")
    channel_id = os.environ.get("MATCH_CHANNEL_ID")

    # Configure the new GenAI Client
    client = genai.Client(api_key=gemini_key)
    model_id = 'gemini-2.5-flash'

    # 2. Fetch today's matches with the "Hunter" Loop
    today = datetime.now().strftime("%Y-%m-%d")
    
    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": "sportapi7.p.rapidapi.com"
    }

    match_data = None
    
    print(f"Scanning for active markets for {today}...")
    
    # Loop through categories 1 to 5 to find the first one with active events
    for category_id in range(1, 6):
        print(f"Checking Category {category_id}...")
        url = f"https://sportapi7.p.rapidapi.com/api/v1/category/{category_id}/scheduled-events/{today}"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.text
            if data and '"events":[]' not in data.replace(" ", ""):
                print(f"✅ Active payload secured in Category {category_id}!")
                match_data = data
                break

    if not match_data:
        print("Complete market blackout across all scanned categories today. Exiting safely.")
        return

    print(f"API RAW RESPONSE (First 500 chars): {match_data[:500]}")

    # 3. Agent 1: The Statistical Analyst
    print("\nFilter 1: Analyzing raw statistics...")
    analyst_prompt = f"""
    You are a data-driven sports analyst. 
    Review this raw API match data for today: {match_data[:12000]} 
    Identify the 3 matches with the clearest statistical data. 
    
    CRITICAL INSTRUCTION: For each of the 3 matches, you MUST explicitly state:
    1. The exact Tournament or League Name.
    2. The exact Home Team (or Player) name.
    3. The exact Away Team (or Player) name.
    
    Then, write a brief analysis of their most statistically likely outcomes. Do not use generic terms like "Home Team" if the actual names are available in the JSON.
    """
    
    analyst_response = safe_generate(client, model_id, analyst_prompt)
    
    if "⚠️ Error" in analyst_response:
        print("Pipeline aborted due to persistent API rate limits.")
        return

    print("\n⏳ Initiating standard 45-second cooldown between agents...")
    time.sleep(45)

    # 4. Agent 2: The Judge / Strategy Refiner
    print("Filter 2: Refining strategy...")
    refiner_prompt = f"""
    You are the lead strategist for a 30-round betting performance challenge. 
    Review this statistical analysis: 
    {analyst_response}
    
    Your job is to select the single best prediction for the day across any active sport or league found in the data. Do not select a 'null' or 'no bet' option.
    
    CRITICAL CONSTRAINTS: 
    1. You MUST NOT include any analysis, reasoning, conversational filler, text introductions, or text conclusions. Output ONLY the raw final details.
    2. You MUST use the exact team/player names and tournament names provided in the analysis. DO NOT write generic terms like "Home", "Away", "1", "X", or "2".
    
    Format the message strictly as follows:
    ⚽ **Match:** [Home Name vs Away Name]
    🏆 **League:** [Exact League / Tournament Name]
    🎯 **Selection:** [Actual Team/Player Name to Win/Draw or Specific Market]
    📊 **Confidence:** [1-100]%
    💰 **Allocation:** [1 to 5] Points (Strictly use a 1-5 scale based on confidence)
    """
    
    final_prediction = safe_generate(client, model_id, refiner_prompt)

    if "⚠️ Error" in final_prediction:
        print("Pipeline aborted due to persistent API rate limits.")
        return

    # 5. Send to Telegram
    print("\nSending prediction to Telegram...")
    telegram_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": channel_id,
        "text": f"🤖 **Daily Prediction Pipeline**\n\n{final_prediction.strip()}",
        "parse_mode": "Markdown"
    }
    requests.post(telegram_url, json=payload)
    print("Automation complete!")

if __name__ == "__main__":
    main()
