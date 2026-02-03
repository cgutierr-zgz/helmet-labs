import requests
import json

def search_markets():
    url = "https://gamma-api.polymarket.com/events"
    try:
        # Search for events with "bitcoin" in the slug or title
        # The API might not support free text search easily on this endpoint, 
        # but let's try listing active events or using a known tag if possible.
        # Alternatively, we can check the 'markets' endpoint.
        
        url_markets = "https://clob.polymarket.com/markets"
        response = requests.get(url_markets, params={"limit": 50, "active": True})
        response.raise_for_status()
        data = response.json()
        
        print(f"Found {len(data['data'])} markets.")
        
        for market in data['data']:
            question = market.get('question', '').lower()
            if 'bitcoin' in question and 'up or down' in question:
                print(f"Question: {market['question']}")
                print(f"Slug: {market.get('market_slug')}")
                # Try to find price
                tokens = market.get('tokens', [])
                for token in tokens:
                    print(f"  Outcome: {token.get('outcome')}, Price: {token.get('price')}")
                print("-" * 30)
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    search_markets()
