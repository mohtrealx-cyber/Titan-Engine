import os
import requests
from google import genai
from datetime import datetime

def main():
    # 1. Load keys from the secure GitHub environment
    rapidapi_key = os.environ.get("RAPIDAPI_KEY")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    bot_token = os.environ.get("MATCH_BOT_TOKEN")
    channel_id = os.environ.get("MATCH_CHANNEL_ID")

    # Configure the new GenAI Client
    client = genai.Client(api_key=gemini_key)
    model_id = 'gemini-3.5-flash'

    # 2. Fetch today's matches
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"https://sportapi7.p.rapidapi.com/api/v1/category/1/scheduled-events/{today}"

    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": "sportapi7.p.rapidapi.com"
    }

    print(f"Fetching match data for {today}...")
    response = requests.get(url, headers=headers)
    match_data = response.text 
    print(f"API RAW RESPONSE: {match_data[:500]}")
    # 3. Agent 1: The Statistical Analyst
    print("Filter 1: Analyzing raw statistics...")
    analyst_prompt = f"""
    You are a purely data-driven sports analyst. 
    Review this raw API match data for today: {match_data[:10000]} 
    Ignore team names, biases, or external news. Based solely on the statistics provided, write a brief analysis of the 3 most statistically likely outcomes.
    """
    analyst_response = client.models.generate_content(
        model=model_id,
        contents=analyst_prompt
    ).text

    # 4. Agent 2: The Judge / Strategy Refiner
    print("Filter 2: Refining strategy...")
    refiner_prompt = f"""
    You are the lead strategist for a 30-round betting performance challenge. 
    Review this statistical analysis: 
    {analyst_response}
    
    Your job is to stress-test these picks, filter out the noise, and select the single best prediction. 
    Output the final prediction formatted cleanly for a Telegram message. You must include a confidence percentage and a suggested point-allocation for the challenge's point-based tracking system.
    """
    final_prediction = client.models.generate_content(
        model=model_id,
        contents=refiner_prompt
    ).text

    # 5. Send to Telegram
    print("Sending prediction to Telegram...")
    telegram_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": channel_id,
        "text": f"🤖 **Daily Prediction Pipeline**\n\n{final_prediction}",
        "parse_mode": "Markdown"
    }
    requests.post(telegram_url, json=payload)
    print("Automation complete!")

if __name__ == "__main__":
    main()
