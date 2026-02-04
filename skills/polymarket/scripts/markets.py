#!/usr/bin/env python3
"""Search Polymarket markets."""
import argparse
import json
from urllib.request import urlopen, Request
from urllib.parse import quote

def search_markets(query: str = None, limit: int = 10, trending: bool = False) -> list:
    """
    Search markets. For trending, sorts by 24h volume.
    For text search, downloads active markets and filters locally (API has no text search).
    """
    # Always fetch more for filtering, sort by recent activity
    fetch_limit = 200 if query else limit
    url = f"https://gamma-api.polymarket.com/markets?limit={fetch_limit}&active=true&closed=false&order=volume24hr&ascending=false"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Accept": "application/json",
        "Origin": "https://polymarket.com",
        "Referer": "https://polymarket.com/"
    }
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=30) as resp:
            markets = json.loads(resp.read())
    except Exception as e:
        print(f"API error: {e}")
        return []
    
    if trending:
        return markets[:limit]
    
    if query:
        # Filter locally by question text (case-insensitive)
        query_lower = query.lower()
        filtered = [
            m for m in markets 
            if query_lower in m.get('question', '').lower() 
            or query_lower in m.get('description', '').lower()
        ]
        # Sort filtered by volume
        filtered.sort(key=lambda x: float(x.get('volume24hr', 0) or 0), reverse=True)
        return filtered[:limit]
    
    return markets[:limit]

def format_market(m: dict) -> str:
    question = m.get('question', m.get('title', 'Unknown'))[:50]
    volume = m.get('volume24hr', m.get('volume', 0))
    # Convert volume to float if it's a string
    try:
        volume = float(volume) if volume else 0
    except (ValueError, TypeError):
        volume = 0
    
    # Get prices - outcomePrices is a JSON string, need to parse it
    prices_raw = m.get('outcomePrices', '[]')
    price_str = ""
    try:
        if isinstance(prices_raw, str):
            prices = json.loads(prices_raw)
        else:
            prices = prices_raw
        if prices and len(prices) >= 1:
            yes_price = float(prices[0]) * 100
            price_str = f" | YES: {yes_price:.1f}%"
    except:
        pass
    
    # Format volume nicely
    if volume >= 1_000_000:
        vol_str = f"${volume/1_000_000:.1f}M"
    elif volume >= 1_000:
        vol_str = f"${volume/1_000:.0f}k"
    else:
        vol_str = f"${volume:.0f}"
    
    return f"• {question}...{price_str} | {vol_str}"

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
