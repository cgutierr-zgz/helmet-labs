#!/usr/bin/env python3
"""Quick buy script for Polymarket CLOB"""
import os
import sys
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, OrderArgs, OrderType
from dotenv import load_dotenv

# Load credentials
load_dotenv("/Users/helmet/.openclaw/.secrets/polymarket.env")

PRIVATE_KEY = os.getenv("POLYMARKET_PRIVATE_KEY")
API_KEY = os.getenv("POLYMARKET_API_KEY")
API_SECRET = os.getenv("POLYMARKET_SECRET")
PASSPHRASE = os.getenv("POLYMARKET_PASSPHRASE")

# BTC Up token ID (from the market data)
BTC_UP_TOKEN = "35830065018591052958462068529728046849588964848195745735498863345430492033591"

def main():
    # Initialize client
    creds = ApiCreds(
        api_key=API_KEY,
        api_secret=API_SECRET,
        api_passphrase=PASSPHRASE
    )
    
    client = ClobClient(
        host="https://clob.polymarket.com",
        key=PRIVATE_KEY,
        chain_id=137,  # Polygon
        creds=creds
    )
    
    # Get current price
    book = client.get_order_book(BTC_UP_TOKEN)
    print(f"Order book for BTC Up:")
    print(f"  Best bid: {book.bids[0].price if book.bids else 'N/A'}")
    print(f"  Best ask: {book.asks[0].price if book.asks else 'N/A'}")
    
    # Market buy - $1 worth at market price
    # Min size is 5 shares, so we need at least ~$3 at current prices
    # Let's try with $1 and see what happens
    
    best_ask = float(book.asks[0].price) if book.asks else 0.60
    shares = 1.0 / best_ask  # How many shares for $1
    
    print(f"\nAttempting to buy ~{shares:.2f} shares at {best_ask}")
    print(f"Cost: ~${shares * best_ask:.2f}")
    
    # Create order - using GTC limit order at slightly above market
    order_args = OrderArgs(
        token_id=BTC_UP_TOKEN,
        price=min(best_ask + 0.01, 0.99),  # Slightly above ask to fill
        size=max(shares, 5),  # Min 5 shares
        side="BUY"
    )
    
    print(f"\nOrder args: {order_args}")
    
    try:
        # Build and sign the order
        signed_order = client.create_order(order_args)
        print(f"Signed order created")
        
        # Submit to CLOB
        result = client.post_order(signed_order, OrderType.GTC)
        print(f"\n✅ Order submitted!")
        print(f"Result: {result}")
        return True
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
