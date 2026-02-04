#!/usr/bin/env python3
"""
Track known whale wallets on Polymarket.
Shows their current positions and recent activity.
"""

import json
import argparse
from urllib.request import urlopen, Request

DATA_API = "https://data-api.polymarket.com"

# Known whale wallets - focus on smart money / info edge traders
WHALES = {
    # Active political traders with good track records
    "aenews2": "0x44c1dfe43260c94ed4f1d00de2e1f80fb113ebc1",  # Rank #11, political bets
    "Theo5": "0x8a4c788f043023b8b28a762216d037e9f148532b",  # $332k positions
    "TheGuru": "0x9f47f1fcb1701bf9eaf31236ad39875e5d60af93",  # $489k positions
    "ForesightOracle": "0x7072dd52161bae614bec6905846a53c9a3a53413",  # $964k positions
    
    # Big money players
    "Hunter-Biden": "0xe29aaa4696b824ae186075a4a1220262f2f7612f",  # $5M - biggest
    "abeautifulmind": "0x53d2d3c78597a78402d4db455a680da7ef560c3f",  # $1.7M
    
    # Active commenters with good insights
    "Apsalar": "0xd42f6a1634a3707e27cbae14ca966068e5d1047d",  # $300k, 1244 likes
    "RememberAmalek": "0x6139c42e48cf190e67a0a85d492413b499336b7a",  # $521k
}


def fetch_positions(wallet: str) -> list:
    """Fetch positions for a wallet."""
    url = f"{DATA_API}/positions?user={wallet.lower()}"
    try:
        req = Request(url, headers={"User-Agent": "WhaleTracker/1.0"})
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception:
        return []


def get_whale_summary(name: str, wallet: str) -> dict:
    """Get summary of whale's positions."""
    positions = fetch_positions(wallet)
    
    if not positions:
        return {"name": name, "wallet": wallet, "positions": 0, "total_value": 0}
    
    total_value = 0
    active_positions = []
    
    for p in positions:
        size = float(p.get('size', 0))
        price = float(p.get('curPrice', p.get('currentPrice', 0)))
        value = size * price
        total_value += value
        
        if value > 100:  # Only show positions > $100
            active_positions.append({
                'market': p.get('title', p.get('market', 'Unknown'))[:40],
                'outcome': p.get('outcome', '?'),
                'size': size,
                'value': value,
            })
    
    # Sort by value
    active_positions.sort(key=lambda x: x['value'], reverse=True)
    
    return {
        "name": name,
        "wallet": wallet[:10] + "..." + wallet[-6:],
        "positions": len(positions),
        "total_value": total_value,
        "top_positions": active_positions[:5],
    }


def main():
    parser = argparse.ArgumentParser(description='Track Polymarket whales')
    parser.add_argument('--wallet', '-w', help='Track specific wallet')
    parser.add_argument('--json', action='store_true', help='JSON output')
    args = parser.parse_args()
    
    if args.wallet:
        summary = get_whale_summary("Custom", args.wallet)
        whales = [summary]
    else:
        whales = [get_whale_summary(name, addr) for name, addr in WHALES.items()]
    
    if args.json:
        print(json.dumps(whales, indent=2))
        return
    
    print("🐋 Whale Tracker\n")
    
    for w in whales:
        if w['positions'] == 0:
            print(f"• {w['name']}: No data")
            continue
            
        print(f"• {w['name']} ({w['wallet']})")
        print(f"  Positions: {w['positions']} | Value: ${w['total_value']:,.0f}")
        
        if w.get('top_positions'):
            print("  Top bets:")
            for p in w['top_positions'][:3]:
                print(f"    - {p['market']}... [{p['outcome']}] ${p['value']:,.0f}")
        print()


if __name__ == '__main__':
    main()
