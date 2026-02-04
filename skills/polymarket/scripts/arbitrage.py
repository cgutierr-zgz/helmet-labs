#!/usr/bin/env python3
"""
Detect pair cost arbitrage opportunities in Polymarket.
If YES + NO < $1.00, you can profit by buying both.
"""

import json
import argparse
from urllib.request import urlopen, Request


def fetch_markets(limit: int = 100) -> list:
    """Fetch active markets sorted by volume."""
    url = f"https://gamma-api.polymarket.com/markets?limit={limit}&active=true&closed=false&order=volume24hr&ascending=false"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Accept": "application/json",
        "Origin": "https://polymarket.com",
        "Referer": "https://polymarket.com/"
    }
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"Error fetching markets: {e}")
        return []


def check_arbitrage(market: dict, min_margin: float = 0.01) -> dict | None:
    """
    Check if market has pair cost arbitrage opportunity.
    
    Args:
        market: Market data from API
        min_margin: Minimum profit margin (default 1%)
    
    Returns:
        Opportunity dict if found, None otherwise
    """
    prices_raw = market.get('outcomePrices', '[]')
    
    try:
        if isinstance(prices_raw, str):
            prices = json.loads(prices_raw)
        else:
            prices = prices_raw
        
        if len(prices) < 2:
            return None
        
        yes_price = float(prices[0])
        no_price = float(prices[1])
        pair_cost = yes_price + no_price
        
        # Check for arbitrage opportunity
        if pair_cost < (1.0 - min_margin):
            profit_per_pair = 1.0 - pair_cost
            profit_pct = (profit_per_pair / pair_cost) * 100
            
            # Get liquidity info
            liquidity = float(market.get('liquidityNum', market.get('liquidity', 0)) or 0)
            volume_24h = float(market.get('volume24hr', 0) or 0)
            
            return {
                'question': market.get('question', 'Unknown')[:60],
                'slug': market.get('slug', ''),
                'yes_price': yes_price,
                'no_price': no_price,
                'pair_cost': pair_cost,
                'profit_per_pair': profit_per_pair,
                'profit_pct': profit_pct,
                'liquidity': liquidity,
                'volume_24h': volume_24h,
                'end_date': market.get('endDate', 'Unknown'),
            }
    except (ValueError, TypeError, json.JSONDecodeError):
        pass
    
    return None


def scan_arbitrage(limit: int = 200, min_margin: float = 0.01, min_liquidity: float = 1000) -> list:
    """
    Scan markets for arbitrage opportunities.
    
    Args:
        limit: Number of markets to scan
        min_margin: Minimum profit margin (default 1%)
        min_liquidity: Minimum liquidity required
    
    Returns:
        List of opportunities sorted by profit potential
    """
    markets = fetch_markets(limit)
    opportunities = []
    
    for market in markets:
        opp = check_arbitrage(market, min_margin)
        if opp and opp['liquidity'] >= min_liquidity:
            opportunities.append(opp)
    
    # Sort by profit percentage
    opportunities.sort(key=lambda x: x['profit_pct'], reverse=True)
    return opportunities


def main():
    parser = argparse.ArgumentParser(description='Scan for Polymarket arbitrage')
    parser.add_argument('--limit', '-n', type=int, default=200, help='Markets to scan')
    parser.add_argument('--margin', '-m', type=float, default=0.01, help='Min margin (default 0.01)')
    parser.add_argument('--liquidity', '-l', type=float, default=500, help='Min liquidity')
    parser.add_argument('--json', action='store_true', help='JSON output')
    args = parser.parse_args()
    
    opportunities = scan_arbitrage(args.limit, args.margin, args.liquidity)
    
    if args.json:
        print(json.dumps(opportunities, indent=2))
        return
    
    if not opportunities:
        print("🔍 No arbitrage opportunities found.")
        print(f"   (Scanned {args.limit} markets, min margin {args.margin*100:.1f}%)")
        return
    
    print(f"💰 Found {len(opportunities)} arbitrage opportunities:\n")
    
    for opp in opportunities[:10]:  # Top 10
        print(f"• {opp['question']}...")
        print(f"  YES: {opp['yes_price']*100:.1f}% + NO: {opp['no_price']*100:.1f}% = {opp['pair_cost']*100:.1f}%")
        print(f"  Profit: {opp['profit_pct']:.2f}% | Liq: ${opp['liquidity']:,.0f}")
        print()


if __name__ == '__main__':
    main()
