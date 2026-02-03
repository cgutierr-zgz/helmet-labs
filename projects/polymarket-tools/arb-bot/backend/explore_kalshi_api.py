import requests
import json
import datetime
import pytz

def explore_kalshi(ticker_prefix):
    url = "https://api.elections.kalshi.com/trade-api/v2/markets"
    # The main API might be api.kalshi.com, but let's try the one often used for public data.
    # Or https://api.kalshi.com/trade-api/v2/markets
    
    # Let's try the elections one, it often works for public data
    url = "https://api.elections.kalshi.com/trade-api/v2/markets"
    
    params = {
        "limit": 100,
        "event_ticker": ticker_prefix # Try filtering by event ticker
    }
    
    try:
        print(f"Fetching markets for event: {ticker_prefix}")
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        markets = data.get('markets', [])
        print(f"Found {len(markets)} markets.")
        
        for market in markets[:5]: # Print first 5
            print(f"Ticker: {market.get('ticker')}")
            print(f"Subtitle: {market.get('subtitle')}") # Often contains the strike price
            print(f"Yes Bid/Ask: {market.get('yes_bid')} / {market.get('yes_ask')}")
            print(f"No Bid/Ask: {market.get('no_bid')} / {market.get('no_ask')}")
            print(f"Last Price: {market.get('last_price')}")
            print("-" * 20)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Use the ticker for the current/next hour.
    # From previous steps: kxbtcd-25nov2614 (for 2 PM ET, which is now active/resolving?)
    # Wait, if it's 2:15 PM ET, the 2 PM market (ending at 3 PM?) is active.
    # The user's image shows "Current: $89,821".
    # Let's use the ticker logic from get_current_markets.py
    
    # Re-implement logic briefly or hardcode for test
    # kxbtcd-25nov2614 corresponds to Nov 26, 14:00 ET.
    explore_kalshi("KXBTCD-25NOV2614") 
