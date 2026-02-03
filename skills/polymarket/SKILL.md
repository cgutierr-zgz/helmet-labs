---
name: polymarket
description: Interact with Polymarket prediction markets. View positions, redeem winnings, check markets, and trade. Use for checking portfolio status, redeeming resolved positions, or researching prediction markets.
---

# Polymarket

Interact with Polymarket prediction markets.

## Quick Start

### View positions
```bash
scripts/positions.py
```

### Redeem resolved positions
```bash
scripts/redeem.py --all  # Redeem all redeemable
scripts/redeem.py --condition-id 0x123...  # Redeem specific
```

### Check markets
```bash
scripts/markets.py "Trump"  # Search markets
scripts/markets.py --trending  # Top markets
```

## Commands

### positions.py
View current portfolio positions.

```bash
scripts/positions.py [options]

Options:
  --wallet, -w    Wallet address (default: from env)
  --json          Output as JSON
  --redeemable    Show only redeemable positions
  --summary       Show P&L summary only
```

### redeem.py
Redeem resolved positions.

```bash
scripts/redeem.py [options]

Options:
  --all           Redeem all redeemable positions
  --condition-id  Specific condition to redeem
  --dry-run       Show what would be redeemed without executing
```

### markets.py
Search and explore markets.

```bash
scripts/markets.py <query> [options]

Options:
  --trending      Show trending markets
  --category      Filter by category
  --limit, -n     Number of results (default: 10)
```

## Configuration

Requires environment variables (from `.secrets/polymarket.env`):
- `POLYMARKET_PRIVATE_KEY`
- `POLYMARKET_WALLET`
- `ALCHEMY_RPC`

Optional for CLOB API:
- `POLYMARKET_API_KEY`
- `POLYMARKET_SECRET`
- `POLYMARKET_PASSPHRASE`
