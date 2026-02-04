#!/usr/bin/env python3
"""
BTC 15-Minute Market Strategy
Monitors BTC price via WebSocket and Polymarket 15min markets.
Detects arbitrage (pair cost < $0.98) and momentum opportunities.
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

try:
    import websockets
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets", "--break-system-packages", "-q"])
    import websockets

SCRIPT_DIR = Path(__file__).parent.parent
STATE_FILE = SCRIPT_DIR / "state" / "btc15m_state.json"
TRADES_FILE = SCRIPT_DIR / "state" / "btc15m_trades.json"

BINANCE_WS = "wss://stream.binance.com:9443/ws/btcusdt@trade"
GAMMA_API = "https://gamma-api.polymarket.com"

# Strategy parameters
PAIR_COST_THRESHOLD = 0.98  # Arbitrage if YES + NO < this
MOMENTUM_THRESHOLD = 0.01   # 1% move to trigger momentum signal
MOMENTUM_WINDOW = 120       # Seconds to measure momentum
MIN_EDGE = 0.05             # 5% minimum edge for momentum trade


def log(msg: str):
    """Log with timestamp."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def load_state() -> dict:
    """Load state from file."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except:
            pass
    return {
        "balance": 50.0,
        "in_position": False,
        "position": None,
        "price_history": [],
        "trades": []
    }


def save_state(state: dict):
    """Save state to file."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def fetch_15m_market() -> dict | None:
    """Fetch current BTC 15-minute market from Polymarket."""
    import time
    
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Origin": "https://polymarket.com",
        "Referer": "https://polymarket.com/"
    }
    
    # Calculate timestamps for current and adjacent 15min intervals
    now = int(time.time())
    interval = 15 * 60
    current_start = (now // interval) * interval
    
    # Try current interval and previous (in case we're at the edge)
    for ts in [current_start, current_start - interval, current_start + interval]:
        slug = f"btc-updown-15m-{ts}"
        url = f"{GAMMA_API}/markets?slug={slug}"
        
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                
                if data:
                    m = data[0] if isinstance(data, list) else data
                    prices_raw = m.get("outcomePrices", "[]")
                    if isinstance(prices_raw, str):
                        prices = json.loads(prices_raw)
                    else:
                        prices = prices_raw
                    
                    if len(prices) >= 2:
                        yes_price = float(prices[0])
                        no_price = float(prices[1])
                        return {
                            "question": m.get("question"),
                            "slug": m.get("slug"),
                            "yes_price": yes_price,
                            "no_price": no_price,
                            "pair_cost": yes_price + no_price,
                            "end_date": m.get("endDate"),
                            "volume": float(m.get("volume24hr", 0) or 0),
                            "timestamp": ts,
                        }
        except Exception:
            continue
    
    return None


def check_arbitrage(market: dict) -> dict | None:
    """Check if there's an arbitrage opportunity."""
    if not market:
        return None
    
    pair_cost = market["pair_cost"]
    if pair_cost < PAIR_COST_THRESHOLD:
        profit_per_pair = 1.0 - pair_cost
        profit_pct = (profit_per_pair / pair_cost) * 100
        
        return {
            "type": "arbitrage",
            "market": market["question"],
            "yes_price": market["yes_price"],
            "no_price": market["no_price"],
            "pair_cost": pair_cost,
            "profit_pct": profit_pct,
            "signal": f"BUY BOTH: YES @ {market['yes_price']:.3f} + NO @ {market['no_price']:.3f} = {pair_cost:.3f}"
        }
    
    return None


def check_momentum(price_history: list, current_price: float, market: dict) -> dict | None:
    """Check if there's a momentum opportunity."""
    if not price_history or not market:
        return None
    
    # Get price from MOMENTUM_WINDOW seconds ago
    cutoff_time = datetime.now().timestamp() - MOMENTUM_WINDOW
    old_prices = [p for p in price_history if p["time"] < cutoff_time]
    
    if not old_prices:
        return None
    
    old_price = old_prices[-1]["price"]
    price_change = (current_price - old_price) / old_price
    
    if abs(price_change) < MOMENTUM_THRESHOLD:
        return None
    
    # Price moved significantly
    direction = "UP" if price_change > 0 else "DOWN"
    
    # Check if market reflects this
    if direction == "UP":
        # If BTC pumped, YES should be high
        # Edge = our expectation - market price
        # After 1%+ pump, YES should be ~70%+
        expected_yes = 0.70 if price_change > 0.02 else 0.65
        edge = expected_yes - market["yes_price"]
        
        if edge > MIN_EDGE:
            return {
                "type": "momentum",
                "direction": "UP",
                "price_change": price_change * 100,
                "btc_price": current_price,
                "market_yes": market["yes_price"],
                "expected_yes": expected_yes,
                "edge": edge * 100,
                "signal": f"BUY YES @ {market['yes_price']:.3f} (expect {expected_yes:.2f}, edge {edge*100:.1f}%)"
            }
    else:
        # If BTC dumped, NO should be high (YES should be low)
        expected_no = 0.70 if price_change < -0.02 else 0.65
        edge = expected_no - market["no_price"]
        
        if edge > MIN_EDGE:
            return {
                "type": "momentum",
                "direction": "DOWN",
                "price_change": price_change * 100,
                "btc_price": current_price,
                "market_no": market["no_price"],
                "expected_no": expected_no,
                "edge": edge * 100,
                "signal": f"BUY NO @ {market['no_price']:.3f} (expect {expected_no:.2f}, edge {edge*100:.1f}%)"
            }
    
    return None


def cmd_scan(args):
    """One-time scan for opportunities."""
    log("Scanning BTC 15min market...")
    
    # Get current BTC price
    from pathlib import Path
    prices_file = Path(__file__).parent.parent / "state" / "prices.json"
    btc_price = None
    if prices_file.exists():
        try:
            with open(prices_file) as f:
                prices = json.load(f)
                btc_price = prices.get("BTCUSDT", {}).get("price")
        except:
            pass
    
    if btc_price:
        log(f"BTC Price: ${btc_price:,.2f}")
    else:
        log("BTC Price: Unknown (monitor not running?)")
    
    # Get 15min market
    market = fetch_15m_market()
    if not market:
        log("❌ Could not find active BTC 15min market")
        return
    
    log(f"Market: {market['question']}")
    log(f"  YES: {market['yes_price']*100:.1f}% | NO: {market['no_price']*100:.1f}%")
    log(f"  Pair Cost: ${market['pair_cost']:.3f}")
    
    # Check arbitrage
    arb = check_arbitrage(market)
    if arb:
        log(f"🎯 ARBITRAGE OPPORTUNITY!")
        log(f"  {arb['signal']}")
        log(f"  Profit: {arb['profit_pct']:.2f}%")
    else:
        log(f"  No arbitrage (pair cost >= ${PAIR_COST_THRESHOLD})")
    
    # Load state for momentum check
    state = load_state()
    if btc_price and state.get("price_history"):
        mom = check_momentum(state["price_history"], btc_price, market)
        if mom:
            log(f"🎯 MOMENTUM OPPORTUNITY!")
            log(f"  BTC moved {mom['price_change']:.2f}% in {MOMENTUM_WINDOW}s")
            log(f"  {mom['signal']}")
    
    log("Scan complete.")


def cmd_status(args):
    """Show current status."""
    state = load_state()
    
    print(f"\n📊 BTC 15min Strategy Status")
    print(f"  Balance: ${state['balance']:.2f}")
    print(f"  In Position: {'Yes' if state.get('in_position') else 'No'}")
    
    if state.get('position'):
        p = state['position']
        print(f"  Position: {p.get('side')} @ ${p.get('entry_price', 0):.3f}")
    
    print(f"  Trades: {len(state.get('trades', []))}")
    
    # Show recent trades
    trades = state.get('trades', [])[-5:]
    if trades:
        print(f"\n  Recent trades:")
        for t in trades:
            pnl = t.get('pnl', 0)
            emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
            print(f"    {emoji} {t.get('side')} @ ${t.get('entry', 0):.3f} → ${pnl:+.2f}")


def cmd_reset(args):
    """Reset state (paper trading)."""
    state = {
        "balance": 50.0,
        "in_position": False,
        "position": None,
        "price_history": [],
        "trades": []
    }
    save_state(state)
    log("✅ State reset. Balance: $50.00")


async def monitor_loop():
    """Main monitoring loop - WebSocket + market scanning."""
    state = load_state()
    log(f"Starting BTC 15min monitor. Balance: ${state['balance']:.2f}")
    
    async with websockets.connect(BINANCE_WS) as ws:
        log("Connected to Binance WebSocket")
        
        last_scan = 0
        scan_interval = 30  # Scan market every 30 seconds
        
        async for message in ws:
            try:
                trade = json.loads(message)
                price = float(trade.get("p", 0))
                now = datetime.now().timestamp()
                
                # Update price history
                state["price_history"].append({"time": now, "price": price})
                
                # Keep only last 5 minutes of history
                cutoff = now - 300
                state["price_history"] = [p for p in state["price_history"] if p["time"] > cutoff]
                
                # Periodic market scan
                if now - last_scan > scan_interval:
                    last_scan = now
                    
                    market = fetch_15m_market()
                    if market:
                        # Check opportunities
                        arb = check_arbitrage(market)
                        mom = check_momentum(state["price_history"], price, market)
                        
                        if arb:
                            log(f"🎯 ARB: {arb['signal']}")
                            # TODO: Execute paper trade
                        
                        if mom:
                            log(f"🎯 MOM: {mom['signal']}")
                            # TODO: Execute paper trade
                    
                    # Save state periodically
                    save_state(state)
                    
            except Exception as e:
                log(f"Error: {e}")


def cmd_monitor(args):
    """Start live monitoring."""
    try:
        asyncio.run(monitor_loop())
    except KeyboardInterrupt:
        log("Stopped.")


def main():
    parser = argparse.ArgumentParser(description="BTC 15min Strategy")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    sub = subparsers.add_parser("scan", help="One-time scan")
    sub.set_defaults(func=cmd_scan)
    
    sub = subparsers.add_parser("status", help="Show status")
    sub.set_defaults(func=cmd_status)
    
    sub = subparsers.add_parser("reset", help="Reset paper trading")
    sub.set_defaults(func=cmd_reset)
    
    sub = subparsers.add_parser("monitor", help="Start live monitoring")
    sub.set_defaults(func=cmd_monitor)
    
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
