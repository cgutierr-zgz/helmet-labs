import requests
import time
import datetime
import pytz
from get_current_markets import get_current_market_urls

# Configuration
POLYMARKET_API_URL = "https://gamma-api.polymarket.com/events"
BINANCE_PRICE_URL = "https://api.binance.com/api/v3/ticker/price"
BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
SYMBOL = "BTCUSDT"

CLOB_API_URL = "https://clob.polymarket.com/book"

def get_clob_price(token_id):
    try:
        response = requests.get(CLOB_API_URL, params={"token_id": token_id})
        response.raise_for_status()
        data = response.json()
        
        # data structure: {'bids': [{'price': '0.38', 'size': '...'}, ...], 'asks': ...}
        bids = data.get('bids', [])
        asks = data.get('asks', [])
        
        best_bid = 0.0
        best_ask = 0.0
        
        if bids:
            # Bids: We want the HIGHEST price someone is willing to pay
            best_bid = max(float(b['price']) for b in bids)
            
        if asks:
            # Asks: We want the LOWEST price someone is willing to sell for
            best_ask = min(float(a['price']) for a in asks)
            
        return best_ask if best_ask > 0 else 0.0 # Return Ask as the "Buy" price
    except Exception as e:
        return None

def get_polymarket_data(slug):
    try:
        # 1. Get Event Details to find Token IDs
        response = requests.get(POLYMARKET_API_URL, params={"slug": slug})
        response.raise_for_status()
        data = response.json()
        
        if not data:
            return None, "Event not found"

        event = data[0]
        markets = event.get("markets", [])
        if not markets:
            return None, "Markets not found in event"
            
        market = markets[0]
        
        # Get Token IDs
        # clobTokenIds is a list of strings
        clob_token_ids = eval(market.get("clobTokenIds", "[]"))
        outcomes = eval(market.get("outcomes", "[]"))
        
        if len(clob_token_ids) != 2:
            return None, "Unexpected number of tokens"
            
        # 2. Fetch Price for each Token from CLOB
        prices = {}
        # Assuming order is [Up, Down] or matches outcomes
        # Usually outcomes are ["Up", "Down"] and clobTokenIds correspond.
        
        for outcome, token_id in zip(outcomes, clob_token_ids):
            price = get_clob_price(token_id)
            if price is not None:
                prices[outcome] = price
            else:
                prices[outcome] = 0.0
            
        return prices, None
    except Exception as e:
        return None, str(e)

def get_binance_current_price():
    try:
        response = requests.get(BINANCE_PRICE_URL, params={"symbol": SYMBOL})
        response.raise_for_status()
        data = response.json()
        return float(data["price"]), None
    except Exception as e:
        return None, str(e)

def get_binance_open_price(target_time_utc):
    try:
        # Timestamp in milliseconds
        timestamp_ms = int(target_time_utc.timestamp() * 1000)
        
        # Fetch 1h kline for the specific timestamp
        params = {
            "symbol": SYMBOL,
            "interval": "1h",
            "startTime": timestamp_ms,
            "limit": 1
        }
        response = requests.get(BINANCE_KLINES_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        if not data:
            return None, "Candle not found yet"
            
        # Kline format: [Open time, Open, High, Low, Close, Volume, ...]
        open_price = float(data[0][1])
        return open_price, None
    except Exception as e:
        return None, str(e)

def fetch_polymarket_data_struct():
    """
    Fetches current Polymarket data and returns a structured dictionary.
    """
    try:
        # Get current market info
        market_info = get_current_market_urls()
        polymarket_url = market_info["polymarket"]
        target_time_utc = market_info["target_time_utc"]
        
        # Extract slug from URL
        slug = polymarket_url.split("/")[-1]
        
        # Fetch Data
        poly_prices, poly_err = get_polymarket_data(slug)
        current_price, curr_err = get_binance_current_price()
        price_to_beat, beat_err = get_binance_open_price(target_time_utc)
        
        if poly_err:
            return None, f"Polymarket Error: {poly_err}"
            
        return {
            "price_to_beat": price_to_beat,
            "current_price": current_price,
            "prices": poly_prices, # {'Up': 0.xx, 'Down': 0.xx}
            "slug": slug,
            "target_time_utc": target_time_utc
        }, None
        
    except Exception as e:
        return None, str(e)

def main():
    data, err = fetch_polymarket_data_struct()
    
    if err:
        print(f"Error: {err}")
        return

    print(f"Fetching data for: {data['slug']}")
    print(f"Target Time (UTC): {data['target_time_utc']}")
    print("-" * 50)
    
    if data['price_to_beat'] is None:
         print("PRICE TO BEAT: Error")
    else:
        print(f"PRICE TO BEAT: ${data['price_to_beat']:,.2f}")

    if data['current_price'] is None:
        print("CURRENT PRICE: Error")
    else:
        print(f"CURRENT PRICE: ${data['current_price']:,.2f}")
    
    up_price = data['prices'].get("Up", 0)
    down_price = data['prices'].get("Down", 0)
    print(f"BUY: UP ${up_price:.3f} & DOWN ${down_price:.3f}")

if __name__ == "__main__":
    main()
