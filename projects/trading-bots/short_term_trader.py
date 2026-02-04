#!/usr/bin/env python3
"""
Short-Term BTC Trader - 15min & 1hour markets
Paper trading with different strategies per timeframe.

Strategies:
- 15min: Mean reversion (bet against majority if >55%)
- 1hour: Momentum (follow current trend)

Usage:
  python short_term_trader.py trade 15m   # Execute a 15min trade
  python short_term_trader.py trade 1h    # Execute a 1hour trade
  python short_term_trader.py status      # Show status
  python short_term_trader.py history     # Show trade history
"""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request

SCRIPT_DIR = Path(__file__).parent
STATE_FILE = SCRIPT_DIR / "state.json"
GAMMA_API = "https://gamma-api.polymarket.com"

# Configuration
CONFIG = {
    "15m": {
        "pool": 25.0,  # $25 for 15min
        "trade_size": 2.0,  # $2 per trade
        "strategy": "mean_reversion",  # Bet against majority
        "threshold": 0.55,  # Bet against if >55% one way
    },
    "1h": {
        "pool": 25.0,  # $25 for 1hour
        "trade_size": 3.0,  # $3 per trade
        "strategy": "momentum",  # Follow the trend
        "threshold": 0.55,  # Follow if >55% one way
    }
}


def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.load(open(STATE_FILE))
        except:
            pass
    return {
        "15m": {"balance": CONFIG["15m"]["pool"], "trades": [], "wins": 0, "losses": 0},
        "1h": {"balance": CONFIG["1h"]["pool"], "trades": [], "wins": 0, "losses": 0},
        "total_trades": 0,
    }


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def fetch_market(timeframe: str) -> dict | None:
    """Fetch current market for timeframe."""
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    }
    
    now = int(time.time())
    
    if timeframe == "15m":
        # 15min markets use timestamp-based slugs
        interval = 15 * 60
        current_start = (now // interval) * interval
        
        for ts in [current_start, current_start + interval]:
            slug = f"btc-updown-15m-{ts}"
            url = f"{GAMMA_API}/markets?slug={slug}"
            
            try:
                req = Request(url, headers=headers)
                with urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read())
                    if data:
                        m = data[0] if isinstance(data, list) else data
                        return parse_market(m)
            except:
                continue
    
    elif timeframe == "1h":
        # 1hour markets use date-based slugs
        # Format: bitcoin-up-or-down-february-4-1pm-et
        from datetime import datetime
        import pytz
        
        et = pytz.timezone('US/Eastern')
        now_et = datetime.now(et)
        
        # Current hour and next hour
        for hour_offset in [0, 1]:
            target = now_et.replace(minute=0, second=0, microsecond=0)
            if hour_offset:
                from datetime import timedelta
                target = target + timedelta(hours=1)
            
            month = target.strftime("%B").lower()
            day = target.day
            hour = target.hour
            
            # Convert to 12-hour format
            if hour == 0:
                hour_str = "12am"
            elif hour < 12:
                hour_str = f"{hour}am"
            elif hour == 12:
                hour_str = "12pm"
            else:
                hour_str = f"{hour-12}pm"
            
            slug = f"bitcoin-up-or-down-{month}-{day}-{hour_str}-et"
            url = f"{GAMMA_API}/markets?slug={slug}"
            
            try:
                req = Request(url, headers=headers)
                with urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read())
                    if data:
                        m = data[0] if isinstance(data, list) else data
                        return parse_market(m)
            except:
                continue
    
    return None


def parse_market(m: dict) -> dict:
    """Parse market data from API response."""
    prices_raw = m.get("outcomePrices", "[]")
    if isinstance(prices_raw, str):
        prices = json.loads(prices_raw)
    else:
        prices = prices_raw
    
    yes_price = float(prices[0]) if len(prices) > 0 else 0.5
    no_price = float(prices[1]) if len(prices) > 1 else 0.5
    
    return {
        "question": m.get("question", "Unknown"),
        "slug": m.get("slug", ""),
        "yes_price": yes_price,
        "no_price": no_price,
        "pair_cost": yes_price + no_price,
        "end_date": m.get("endDate", ""),
    }


def decide_trade(market: dict, timeframe: str) -> dict | None:
    """Decide whether and how to trade based on strategy."""
    cfg = CONFIG[timeframe]
    yes_price = market["yes_price"]
    threshold = cfg["threshold"]
    
    if cfg["strategy"] == "mean_reversion":
        # Bet AGAINST the majority
        if yes_price > threshold:
            return {"side": "NO", "price": market["no_price"], "reason": f"Mean reversion: YES at {yes_price:.1%}, betting NO"}
        elif yes_price < (1 - threshold):
            return {"side": "YES", "price": market["yes_price"], "reason": f"Mean reversion: YES at {yes_price:.1%}, betting YES"}
        else:
            # Market is balanced, default to DOWN (people tend to be optimistic)
            return {"side": "NO", "price": market["no_price"], "reason": f"Balanced market ({yes_price:.1%}), default NO bias"}
    
    elif cfg["strategy"] == "momentum":
        # Follow the majority
        if yes_price > threshold:
            return {"side": "YES", "price": market["yes_price"], "reason": f"Momentum: YES at {yes_price:.1%}, following trend"}
        elif yes_price < (1 - threshold):
            return {"side": "NO", "price": market["no_price"], "reason": f"Momentum: NO dominant, following trend"}
        else:
            # No clear momentum, skip or small bet
            return {"side": "YES", "price": market["yes_price"], "reason": f"No clear momentum ({yes_price:.1%}), small YES bet"}
    
    return None


def execute_paper_trade(state: dict, timeframe: str, market: dict, decision: dict) -> dict:
    """Execute a paper trade."""
    cfg = CONFIG[timeframe]
    tf_state = state[timeframe]
    
    trade_size = cfg["trade_size"]
    
    if tf_state["balance"] < trade_size:
        return {"error": f"Insufficient balance: ${tf_state['balance']:.2f}"}
    
    # Calculate shares
    price = decision["price"]
    shares = trade_size / price
    
    trade = {
        "id": state["total_trades"] + 1,
        "timestamp": datetime.now().isoformat(),
        "timeframe": timeframe,
        "market": market["question"][:50],
        "slug": market["slug"],
        "side": decision["side"],
        "price": price,
        "size": trade_size,
        "shares": shares,
        "reason": decision["reason"],
        "status": "open",
        "result": None,
        "pnl": None,
    }
    
    # Deduct from balance
    tf_state["balance"] -= trade_size
    tf_state["trades"].append(trade)
    state["total_trades"] += 1
    
    save_state(state)
    
    return trade


def cmd_trade(args):
    """Execute a trade for the specified timeframe."""
    timeframe = args.timeframe
    
    if timeframe not in ["15m", "1h"]:
        print(f"❌ Invalid timeframe: {timeframe}. Use '15m' or '1h'")
        return
    
    state = load_state()
    tf_state = state[timeframe]
    cfg = CONFIG[timeframe]
    
    log(f"🎯 {timeframe.upper()} Trade")
    log(f"   Strategy: {cfg['strategy']}")
    log(f"   Balance: ${tf_state['balance']:.2f}")
    
    # Fetch market
    market = fetch_market(timeframe)
    if not market:
        log("❌ Could not fetch market")
        return
    
    log(f"   Market: {market['question'][:50]}...")
    log(f"   Prices: YES {market['yes_price']:.1%} | NO {market['no_price']:.1%}")
    
    # Decide trade
    decision = decide_trade(market, timeframe)
    if not decision:
        log("❌ No trade decision")
        return
    
    log(f"   Decision: {decision['side']} @ {decision['price']:.3f}")
    log(f"   Reason: {decision['reason']}")
    
    # Execute
    trade = execute_paper_trade(state, timeframe, market, decision)
    
    if "error" in trade:
        log(f"❌ {trade['error']}")
        return
    
    log(f"✅ TRADE #{trade['id']} EXECUTED")
    log(f"   {trade['side']} {trade['shares']:.1f} shares @ ${trade['price']:.3f}")
    log(f"   New balance: ${tf_state['balance']:.2f}")
    
    # Output for parsing
    print(f"\n📊 TRADE: {timeframe} {trade['side']} ${trade['size']:.2f} @ {trade['price']:.1%}")


def cmd_status(args):
    """Show current status."""
    state = load_state()
    
    print("\n" + "="*50)
    print("📊 SHORT-TERM TRADER STATUS")
    print("="*50)
    
    for tf in ["15m", "1h"]:
        tf_state = state[tf]
        cfg = CONFIG[tf]
        open_trades = [t for t in tf_state["trades"] if t.get("status") == "open"]
        
        print(f"\n⏱️  {tf.upper()} ({cfg['strategy']})")
        print(f"   Balance: ${tf_state['balance']:.2f} / ${cfg['pool']:.2f}")
        print(f"   Trade size: ${cfg['trade_size']:.2f}")
        print(f"   Wins: {tf_state['wins']} | Losses: {tf_state['losses']}")
        print(f"   Open trades: {len(open_trades)}")
        
        # Win rate
        total = tf_state['wins'] + tf_state['losses']
        if total > 0:
            wr = tf_state['wins'] / total * 100
            print(f"   Win rate: {wr:.1f}%")
    
    print(f"\n📈 Total trades: {state['total_trades']}")
    print("="*50)


def cmd_history(args):
    """Show trade history."""
    state = load_state()
    
    print("\n📜 TRADE HISTORY")
    print("-"*70)
    
    all_trades = []
    for tf in ["15m", "1h"]:
        all_trades.extend(state[tf]["trades"])
    
    # Sort by timestamp
    all_trades.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    
    for trade in all_trades[:20]:  # Last 20
        status = trade.get("status", "?")
        pnl = trade.get("pnl")
        pnl_str = f"${pnl:+.2f}" if pnl is not None else "pending"
        emoji = "🟢" if pnl and pnl > 0 else "🔴" if pnl and pnl < 0 else "⏳"
        
        ts = trade.get("timestamp", "")[:16]
        print(f"{emoji} #{trade['id']:03d} | {trade['timeframe']:3s} | {trade['side']:3s} @ {trade['price']:.3f} | {pnl_str:>8s} | {ts}")
    
    if not all_trades:
        print("No trades yet.")


def cmd_reset(args):
    """Reset all state."""
    state = {
        "15m": {"balance": CONFIG["15m"]["pool"], "trades": [], "wins": 0, "losses": 0},
        "1h": {"balance": CONFIG["1h"]["pool"], "trades": [], "wins": 0, "losses": 0},
        "total_trades": 0,
    }
    save_state(state)
    print("✅ State reset. Ready for paper trading.")


def main():
    parser = argparse.ArgumentParser(description="Short-Term BTC Trader")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Trade command
    sub = subparsers.add_parser("trade", help="Execute a trade")
    sub.add_argument("timeframe", choices=["15m", "1h"], help="Timeframe")
    sub.set_defaults(func=cmd_trade)
    
    # Status command
    sub = subparsers.add_parser("status", help="Show status")
    sub.set_defaults(func=cmd_status)
    
    # History command
    sub = subparsers.add_parser("history", help="Show trade history")
    sub.set_defaults(func=cmd_history)
    
    # Reset command
    sub = subparsers.add_parser("reset", help="Reset state")
    sub.set_defaults(func=cmd_reset)
    
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
