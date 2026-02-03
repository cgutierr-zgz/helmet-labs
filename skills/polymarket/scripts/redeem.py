#!/usr/bin/env python3
"""Redeem resolved Polymarket positions."""
import argparse
import json
import os
import sys
import subprocess
from pathlib import Path
from urllib.request import urlopen, Request

def load_env():
    env_path = Path.home() / ".openclaw/.secrets/polymarket.env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if '=' in line and not line.startswith('#'):
                key, val = line.split('=', 1)
                os.environ.setdefault(key.strip(), val.strip())

def get_redeemable_positions(wallet: str) -> list:
    url = f"https://data-api.polymarket.com/positions?user={wallet}"
    req = Request(url, headers={"User-Agent": "PolymarketSkill/1.0"})
    with urlopen(req, timeout=30) as resp:
        positions = json.loads(resp.read())
    return [p for p in positions if p.get('redeemable')]

def redeem_position(condition_id: str, private_key: str, rpc_url: str, dry_run: bool = False) -> str:
    """Execute redemption using viem via Node.js"""
    script = f'''
const {{ createWalletClient, http, parseAbi }} = require("viem");
const {{ polygon }} = require("viem/chains");
const {{ privateKeyToAccount }} = require("viem/accounts");

const CTF_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045";
const USDC = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174";

async function main() {{
  const account = privateKeyToAccount("{private_key}");
  const client = createWalletClient({{
    account,
    chain: polygon,
    transport: http("{rpc_url}"),
  }});
  
  const hash = await client.writeContract({{
    address: CTF_ADDRESS,
    abi: parseAbi(["function redeemPositions(address,bytes32,bytes32,uint256[]) external"]),
    functionName: "redeemPositions",
    args: [USDC, "0x" + "0".repeat(64), "{condition_id}", [1, 2]],
  }});
  
  console.log(hash);
}}

main().catch(e => {{ console.error(e.message); process.exit(1); }});
'''
    if dry_run:
        return f"DRY RUN: Would redeem {condition_id}"
    
    # Write temp script and execute
    tmp_path = Path("/tmp/redeem_poly.js")
    tmp_path.write_text(script)
    result = subprocess.run(["node", str(tmp_path)], capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(result.stderr)
    return result.stdout.strip()

def main():
    parser = argparse.ArgumentParser(description='Redeem Polymarket positions')
    parser.add_argument('--all', action='store_true', help='Redeem all redeemable')
    parser.add_argument('--condition-id', help='Specific condition ID')
    parser.add_argument('--dry-run', action='store_true', help='Show without executing')
    args = parser.parse_args()
    
    load_env()
    wallet = os.environ.get('POLYMARKET_WALLET')
    private_key = os.environ.get('POLYMARKET_PRIVATE_KEY')
    rpc_url = os.environ.get('ALCHEMY_RPC')
    
    if not all([wallet, private_key, rpc_url]):
        print("Error: Missing credentials in .secrets/polymarket.env", file=sys.stderr)
        sys.exit(1)
    
    if args.condition_id:
        # Redeem specific
        print(f"Redeeming {args.condition_id}...")
        tx = redeem_position(args.condition_id, private_key, rpc_url, args.dry_run)
        print(f"✅ {tx}")
    elif args.all:
        # Redeem all
        positions = get_redeemable_positions(wallet)
        if not positions:
            print("No redeemable positions found")
            return
        
        print(f"Found {len(positions)} redeemable positions:\n")
        total = 0
        for p in positions:
            print(f"  • {p['title'][:50]}... (${p['currentValue']:.2f})")
            total += p.get('currentValue', 0)
        
        print(f"\nTotal value: ${total:.2f}\n")
        
        for p in positions:
            cid = p['conditionId']
            print(f"Redeeming {p['title'][:30]}...")
            try:
                tx = redeem_position(cid, private_key, rpc_url, args.dry_run)
                print(f"  ✅ {tx}")
            except Exception as e:
                print(f"  ❌ Error: {e}")
    else:
        print("Specify --all or --condition-id")
        sys.exit(1)

if __name__ == '__main__':
    main()
