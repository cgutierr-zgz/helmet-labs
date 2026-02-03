#!/usr/bin/env python3
"""Search Polymarket markets."""
import argparse
import json
from urllib.request import urlopen, Request
from urllib.parse import quote

def search_markets(query: str = None, limit: int = 10, trending: bool = False) -> list:
    if trending:
        url = f"https://gamma-api.polymarket.com/markets?limit={limit}&active=true&order=volume24hr&ascending=false"
    elif query:
        url = f"https://gamma-api.polymarket.com/markets?limit={limit}&active=true&tag_all={quote(query)}"
    else:
        url = f"https://gamma-api.polymarket.com/markets?limit={limit}&active=true"
    
    req = Request(url, headers={"User-Agent": "PolymarketSkill/1.0"})
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except:
        # Fallback to clob API
        if query:
            url = f"https://clob.polymarket.com/markets?next_cursor=&tag={quote(query)}"
        else:
            url = "https://clob.polymarket.com/markets"
        req = Request(url, headers={"User-Agent": "PolymarketSkill/1.0"})
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return data.get('data', data)[:limit]

def format_market(m: dict) -> str:
    question = m.get('question', m.get('title', 'Unknown'))[:60]
    volume = m.get('volume', m.get('volume24hr', 0))
    # Convert volume to float if it's a string
    try:
        volume = float(volume) if volume else 0
    except (ValueError, TypeError):
        volume = 0
    # Get best price if available
    outcomes = m.get('outcomes', [])
    prices = m.get('outcomePrices', [])
    price_str = ""
    if prices and len(prices) >= 1:
        try:
            price_str = f" | Yes: {float(prices[0])*100:.0f}%"
        except:
            pass
    return f"• {question}...{price_str} | Vol: ${volume:,.0f}"

def main():
    parser = argparse.ArgumentParser(description='Search Polymarket markets')
    parser.add_argument('query', nargs='?', help='Search query')
    parser.add_argument('--trending', action='store_true', help='Show trending')
    parser.add_argument('--limit', '-n', type=int, default=10, help='Results limit')
    parser.add_argument('--json', action='store_true', help='JSON output')
    args = parser.parse_args()
    
    markets = search_markets(args.query, args.limit, args.trending)
    
    if args.json:
        print(json.dumps(markets, indent=2))
        return
    
    title = "🔥 Trending Markets" if args.trending else f"🔍 Markets: {args.query or 'all'}"
    print(f"{title}\n")
    
    for m in markets:
        print(format_market(m))

if __name__ == '__main__':
    main()
