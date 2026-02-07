# Multi-Market Trader — Quick Start

## What It Does
Discovers and trades across multiple Polymarket markets simultaneously (sports, politics, geopolitics, crypto). Runs alongside the existing BTC bot without interference.

## Usage

```bash
# Run a trading cycle (discover → manage → trade)
python multi_market_trader.py cycle

# Check positions and stats
python multi_market_trader.py report

# Analyze performance (after 10+ trades)
python multi_market_trader.py iterate

# Reset to $100 and start fresh
python multi_market_trader.py reset
```

## Quick Stats

**Markets Found:** 17 qualifying (50k+ volume, tradeable prices)  
**Categories:** Sports, Geopolitics, Politics, Crypto, Other  
**Pool Size:** $100  
**Position Size:** $5 max  
**Max Positions:** 10 concurrent  
**Take Profit:** +40%  
**Stop Loss:** -30%  

## Current Status

**Balance:** $70 / $100  
**Open Positions:** 6  
**Trades Made:** 6  

## Strategies

1. **Momentum** — Follow strong trends (60-75¢)
2. **Value** — Buy cheap (25-45¢)
3. **Reversion** — Fade spikes (coming soon)

## Files

- `multi_market_trader.py` — Main bot (602 lines)
- `state_multi.json` — State file
- `analysis_multi.json` — Performance logs
- `MULTI_MARKET_REPORT.md` — Full documentation

## Example Output

```
[16:52:20] 🔄 Starting cycle...
[16:52:20] 🔍 Discovering markets...
[16:52:20] ✓ Found 15 qualifying markets
[16:52:20] 📈 TRADE: NO on US strikes Iran by February 28, 2026?
[16:52:20]    Strategy: momentum | Entry: 0.745 | Cost: $5.00 | Shares: 6.71
[16:52:20]    Category: geopolitics | Vol: $1,079,454
[16:52:20] ✓ Cycle complete
```

## Next Steps

1. Run `cycle` every 1-2 hours
2. Monitor via `report`
3. Iterate after 10-20 trades
4. Consider cron job for automation

---
*Part of the trading/bots suite — runs independently from auto_trader_v2.py*
