import asyncio
import os
import django
from django.conf import settings

# Setup Django standalone
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentinel_core.settings')
django.setup()

from src.ingestion.multi_source import fetch_stock
from src.chatbot.anand_bot import get_chatbot

async def test_analysis():
    ticker = "TCS"
    print(f"\n--- Testing Fetch: {ticker} ---")
    data = await fetch_stock(ticker)
    print(f"Data Success: {data.get('success')}")
    if data.get('success'):
        print(f"Price: {data.get('price')}")
    else:
        print(f"Error: {data.get('error')}")
        return

    print(f"\n--- Testing Bot Analysis: {ticker} ---")
    bot = get_chatbot()
    try:
        result = await bot.analyze(ticker)
        print(f"Analysis Success: {result.get('success')}")
        if result.get('success'):
            print("Analysis Snippet:", result.get('analysis')[:100])
        else:
            print("Analysis Error:", result.get('error'))
    except Exception as e:
        print(f"Bot Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_analysis())
