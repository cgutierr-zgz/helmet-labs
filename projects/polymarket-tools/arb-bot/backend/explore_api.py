import requests
import json
import datetime
import pytz

def fetch_event(slug):
    url = "https://gamma-api.polymarket.com/events"
    try:
        print(f"Fetching: {slug}")
        response = requests.get(url, params={"slug": slug})
        response.raise_for_status()
        data = response.json()
        if data:
            event = data[0]
            market = event['markets'][0]
            print(f"Active: {market['active']}")
            print(f"Closed: {market['closed']}")
            print(f"Outcome Prices: {market['outcomePrices']}")
            print(f"Best Bid: {market.get('bestBid')}")
            print(f"Best Ask: {market.get('bestAsk')}")
            print(f"Last Trade Price: {market.get('lastTradePrice')}")
            print("-" * 20)
        else:
            print("No data found.")
    except Exception as e:
        print(f"Error fetching event: {e}")

if __name__ == "__main__":
    # Current time is approx 2:08 PM ET (19:08 UTC)
    # Check 2pm (expired?) and 3pm (active?)
    
    fetch_event("bitcoin-up-or-down-november-26-2pm-et")
    fetch_event("bitcoin-up-or-down-november-26-3pm-et")
