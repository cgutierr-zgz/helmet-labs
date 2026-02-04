#!/usr/bin/env python3
"""Quick trade script for Polymarket CLOB"""
import os
import sys
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.constants import POLYGON

# Load from env file
def load_env(path):
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                os.environ[key] = val

load_env('/Users/helmet/.openclaw/.secrets/polymarket.env')

PRIVATE_KEY = os.environ['POLYMARKET_PRIVATE_KEY']
API_KEY = os.environ['POLYMARKET_API_KEY']
API_SECRET = os.environ['POLYMARKET_SECRET']
PASSPHRASE = os.environ['POLYMARKET_PASSPHRASE']

def main():
    token_id = sys.argv[1]  # CLOB token ID
    side = sys.argv[2]      # BUY or SELL
    amount = float(sys.argv[3])  # Amount in USD
    price = float(sys.argv[4]) if len(sys.argv) > 4 else None  # Limit price (optional)
    
    print(f"Connecting to Polymarket CLOB...")
    client = ClobClient(
        host="https://clob.polymarket.com",
        key=API_KEY,
        secret=API_SECRET,
        passphrase=PASSPHRASE,
        chain_id=POLYGON,
        private_key=PRIVATE_KEY
    )
    
    # Get current price if not specified
    if price is None:
        book = client.get_order_book(token_id)
        if side == "BUY":
            price = float(book['asks'][0]['price']) if book['asks'] else 0.99
        else:
            price = float(book['bids'][0]['price']) if book['bids'] else 0.01
        print(f"Using market price: {price}")
    
    # Calculate size (shares = amount / price)
    size = round(amount / price, 2)
    
    print(f"Placing order: {side} {size} shares @ ${price} = ~${amount}")
    
    order_args = OrderArgs(
        price=price,
        size=size,
        side=side,
        token_id=token_id
    )
    
    # Create and sign order
    signed_order = client.create_order(order_args)
    
    # Post order
    result = client.post_order(signed_order, OrderType.GTC)
    print(f"Order result: {result}")
    return result

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: trade.py <token_id> <BUY|SELL> <amount_usd> [limit_price]")
        sys.exit(1)
    main()
