#!/usr/bin/env python3
"""View Polymarket positions."""
import argparse
import json
import os
import sys
from urllib.request import urlopen, Request
from pathlib import Path

# Load env from secrets
def load_env():
    env_path = Path.home() / ".openclaw/.secrets/polymarket.env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if '=' in line and not line.startswith('#'):
                key, val = line.split('=', 1)
                os.environ.setdefault(key.strip(), val.strip())

def get_positions(wallet: str) -> list:
    url = f"https://data-api.polymarket.com/positions?user={wallet}"
    req = Request(url, headers={"User-Agent": "PolymarketSkill/1.0"})
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())

def format_position(p: dict) -> str:
    pnl = p.get('cashPnl', 0)
    pnl_pct = p.get('percentPnl', 0)
    symbol = "✅" if p.get('redeemable') else ("📈" if pnl > 0 else "📉")
    return f"{symbol} {p['title'][:50]}... | ${p['currentValue']:.2f} | P&L: ${pnl:+.2f} ({pnl_pct:+.1f}%)"

def main():
    parser = argparse.ArgumentParser(description='View Polymarket positions')
    parser.add_argument('--wallet', '-w', help='Wallet address')
    parser.add_argument('--json', action='store_true', help='JSON output')
    parser.add_argument('--redeemable', action='store_true', help='Only redeemable')
    parser.add_argument('--summary', action='store_true', help='Summary only')
    args = parser.parse_args()
    
    load_env()
    wallet = args.wallet or os.environ.get('POLYMARKET_WALLET')
    if not wallet:
        print("Error: No wallet specified", file=sys.stderr)
        sys.exit(1)
    
    positions = get_positions(wallet)
    
    if args.redeemable:
        positions = [p for p in positions if p.get('redeemable')]
    
    if args.json:
        print(json.dumps(positions, indent=2))
        return
    
    if args.summary:
        total_value = sum(p.get('currentValue', 0) for p in positions)
        total_invested = sum(p.get('initialValue', 0) for p in positions)
        total_pnl = sum(p.get('cashPnl', 0) for p in positions)
        redeemable_value = sum(p.get('currentValue', 0) for p in positions if p.get('redeemable'))
        print(f"📊 Portfolio Summary")
        print(f"   Positions: {len(positions)}")
        print(f"   Total Value: ${total_value:.2f}")
        print(f"   Total Invested: ${total_invested:.2f}")
        print(f"   Total P&L: ${total_pnl:+.2f}")
        print(f"   Redeemable: ${redeemable_value:.2f}")
        return
    
    print(f"📊 Positions for {wallet[:10]}...{wallet[-6:]}\n")
    for p in sorted(positions, key=lambda x: -x.get('currentValue', 0)):
        print(format_position(p))
    
    # Summary
    redeemable = [p for p in positions if p.get('redeemable')]
    if redeemable:
        total = sum(p.get('currentValue', 0) for p in redeemable)
        print(f"\n🎯 {len(redeemable)} positions redeemable (${total:.2f})")

if __name__ == '__main__':
    main()
