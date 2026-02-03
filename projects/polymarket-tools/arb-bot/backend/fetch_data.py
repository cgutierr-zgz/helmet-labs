import requests
import time
import datetime

# Configuration
POLYMARKET_EVENT_SLUG = "bitcoin-up-or-down-november-25-6pm-et"
POLYMARKET_URL = "https://gamma-api.polymarket.com/events"
BINANCE_PRICE_URL = "https://api.binance.com/api/v3/ticker/price"
BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
SYMBOL = "BTCUSDT"

# Target Candle Start Time: November 25, 2025, 6PM ET = 23:00 UTC
# Timestamp in milliseconds
TARGET_CANDLE_TIMESTAMP = 1764111600000 

def get_polymarket_data():
    try:
        response = requests.get(POLYMARKET_URL, params={"slug": POLYMARKET_EVENT_SLUG})
        response.raise_for_status()
        data = response.json()
        
        if not data:
            return None, "Event not found"

        event = data[0]
        markets = event.get("markets", [])
        if not markets:
            return None, "Markets not found in event"
            
        market = markets[0]
        outcomes = eval(market.get("outcomes", "[]"))
        outcome_prices = eval(market.get("outcomePrices", "[]"))
        
        prices = {}
        for outcome, price in zip(outcomes, outcome_prices):
            prices[outcome] = float(price)
            
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

def get_binance_open_price():
    try:
        # Fetch 1h kline for the specific timestamp
        params = {
            "symbol": SYMBOL,
            "interval": "1h",
            "startTime": TARGET_CANDLE_TIMESTAMP,
            "limit": 1
        }
        response = requests.get(BINANCE_KLINES_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        if not data:
            return None, "Candle not found yet (future?)"
            
        # Kline format: [Open time, Open, High, Low, Close, Volume, ...]
        open_price = float(data[0][1])
        return open_price, None
    except Exception as e:
        return None, str(e)

def main():
    # print(f"Starting data fetch for {POLYMARKET_EVENT_SLUG}...")
    # print(f"Target Candle Time: {datetime.datetime.fromtimestamp(TARGET_CANDLE_TIMESTAMP/1000, datetime.timezone.utc)}")
    # print("-" * 50)

    while True:
        try:
            # Fetch Data
            poly_prices, poly_err = get_polymarket_data()
            current_price, curr_err = get_binance_current_price()
            price_to_beat, beat_err = get_binance_open_price()

            # Clear screen (optional, or just print new lines)
            # print("\033[H\033[J", end="") 
            
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}]")
            
            if beat_err:
                print(f"PRICE TO BEAT: Error ({beat_err})")
            else:
                print(f"PRICE TO BEAT: ${price_to_beat:,.2f}")

            if curr_err:
                print(f"CURRENT PRICE: Error ({curr_err})")
            else:
                print(f"CURRENT PRICE: ${current_price:,.2f}")
            
            if poly_err:
                print(f"BUY: Error ({poly_err})")
            else:
                up_price = poly_prices.get("Up", 0)
                down_price = poly_prices.get("Down", 0)
                print(f"BUY: UP ${up_price:.3f} & DOWN ${down_price:.3f}")
            
            # print("-" * 30)
            print() # Add a newline for separation instead of a line
            
            time.sleep(1)
            
        except KeyboardInterrupt:
            print("\nStopping...")
            break
        except Exception as e:
            print(f"Unexpected Error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()
