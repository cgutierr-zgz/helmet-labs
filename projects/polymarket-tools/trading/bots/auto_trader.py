#!/usr/bin/env python3
"""
Auto Trader - Autonomous short-term trading bot
Trades, resolves, learns, and iterates without human input.

Usage:
  python auto_trader.py cycle        # Full cycle: resolve old → trade new → log
  python auto_trader.py report       # Summary report for Telegram
  python auto_trader.py iterate      # Analyze results and adjust strategy
"""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request

SCRIPT_DIR = Path(__file__).parent
STATE_FILE = SCRIPT_DIR / "state.json"
STRATEGY_LOG = SCRIPT_DIR / "strategy_log.json"

GAMMA_API = "https://gamma-api.polymarket.com"

def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.load(open(STATE_FILE))
        except:
            pass
    return {
        "15m": {"balance": 25.0, "trades": [], "wins": 0, "losses": 0, "strategy": "momentum", "params": {"threshold": 0.55}},
        "1h": {"balance": 25.0, "trades": [], "wins": 0, "losses": 0, "strategy": "momentum", "params": {"threshold": 0.55}},
        "total_trades": 0,
        "version": "0.2",
    }


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def load_strategy_log() -> list:
    if STRATEGY_LOG.exists():
        try:
            return json.load(open(STRATEGY_LOG))
        except:
            pass
    return []


def save_strategy_log(entries: list):
    with open(STRATEGY_LOG, "w") as f:
        json.dump(entries, f, indent=2)


def fetch_market(timeframe: str) -> dict | None:
    """Fetch current active market for timeframe."""
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    now = int(time.time())
    
    if timeframe == "15m":
        interval = 15 * 60
        current_start = (now // interval) * interval
        for ts in [current_start, current_start + interval]:
            slug = f"btc-updown-15m-{ts}"
            try:
                req = Request(f"{GAMMA_API}/markets?slug={slug}", headers=headers)
                with urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read())
                    if data:
                        m = data[0] if isinstance(data, list) else data
                        # Only return if market hasn't ended
                        end = m.get("endDate", "")
                        if end:
                            from datetime import datetime as dt
                            end_ts = dt.fromisoformat(end.replace("Z", "+00:00")).timestamp()
                            if end_ts > now:
                                return parse_market(m)
            except:
                continue
    
    elif timeframe == "1h":
        import pytz
        et = pytz.timezone('US/Eastern')
        now_et = datetime.now(et)
        
        for hour_offset in [0, 1]:
            from datetime import timedelta
            target = now_et.replace(minute=0, second=0, microsecond=0) + timedelta(hours=hour_offset)
            
            month = target.strftime("%B").lower()
            day = target.day
            hour = target.hour
            
            if hour == 0: hour_str = "12am"
            elif hour < 12: hour_str = f"{hour}am"
            elif hour == 12: hour_str = "12pm"
            else: hour_str = f"{hour-12}pm"
            
            slug = f"bitcoin-up-or-down-{month}-{day}-{hour_str}-et"
            try:
                req = Request(f"{GAMMA_API}/markets?slug={slug}", headers=headers)
                with urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read())
                    if data:
                        m = data[0] if isinstance(data, list) else data
                        end = m.get("endDate", "")
                        if end:
                            from datetime import datetime as dt
                            end_ts = dt.fromisoformat(end.replace("Z", "+00:00")).timestamp()
                            if end_ts > now:
                                return parse_market(m)
            except:
                continue
    
    return None


def fetch_market_by_slug(slug: str) -> dict | None:
    """Fetch a specific market by slug."""
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    try:
        req = Request(f"{GAMMA_API}/markets?slug={slug}", headers=headers)
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            if data:
                m = data[0] if isinstance(data, list) else data
                return parse_market(m)
    except:
        return None


def parse_market(m: dict) -> dict:
    prices_raw = m.get("outcomePrices", "[]")
    prices = json.loads(prices_raw) if isinstance(prices_raw, str) else prices_raw
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


def get_btc_price() -> float | None:
    """Get current BTC price."""
    try:
        req = Request("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
                      headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return float(data["price"])
    except:
        return None


def decide_trade(market: dict, timeframe: str, state: dict) -> dict | None:
    """Decide trade based on current strategy."""
    tf_state = state[timeframe]
    strategy = tf_state.get("strategy", "momentum")
    params = tf_state.get("params", {"threshold": 0.55})
    threshold = params.get("threshold", 0.55)
    
    yes_price = market["yes_price"]
    
    if strategy == "momentum":
        if yes_price > threshold:
            return {"side": "YES", "price": yes_price, "reason": f"Momentum UP ({yes_price:.0%})"}
        elif yes_price < (1 - threshold):
            return {"side": "NO", "price": market["no_price"], "reason": f"Momentum DOWN ({yes_price:.0%})"}
        else:
            # Weak signal — bet with slight lean
            if yes_price > 0.5:
                return {"side": "YES", "price": yes_price, "reason": f"Weak momentum UP ({yes_price:.0%})"}
            else:
                return {"side": "NO", "price": market["no_price"], "reason": f"Weak momentum DOWN ({yes_price:.0%})"}
    
    elif strategy == "mean_reversion":
        if yes_price > threshold:
            return {"side": "NO", "price": market["no_price"], "reason": f"MR: YES too high ({yes_price:.0%})"}
        elif yes_price < (1 - threshold):
            return {"side": "YES", "price": yes_price, "reason": f"MR: YES too low ({yes_price:.0%})"}
        else:
            return {"side": "NO", "price": market["no_price"], "reason": f"MR: Balanced, default NO"}
    
    elif strategy == "btc_momentum":
        # Use actual BTC price movement to decide
        btc = get_btc_price()
        if btc is None:
            return {"side": "YES" if yes_price > 0.5 else "NO", 
                    "price": yes_price if yes_price > 0.5 else market["no_price"],
                    "reason": "BTC price unavailable, following market"}
        
        # Compare with market expectation
        if yes_price > 0.6 and btc:
            return {"side": "YES", "price": yes_price, "reason": f"BTC ${btc:,.0f}, market bullish ({yes_price:.0%})"}
        elif yes_price < 0.4:
            return {"side": "NO", "price": market["no_price"], "reason": f"BTC ${btc:,.0f}, market bearish ({yes_price:.0%})"}
        else:
            return {"side": "YES", "price": yes_price, "reason": f"BTC ${btc:,.0f}, neutral lean UP"}
    
    return None


def resolve_trades(state: dict) -> list:
    """Check and resolve open trades."""
    resolved = []
    
    for tf in ["15m", "1h"]:
        tf_state = state[tf]
        for trade in tf_state["trades"]:
            if trade.get("status") != "open":
                continue
            
            # Fetch the market
            market = fetch_market_by_slug(trade["slug"])
            if not market:
                continue
            
            yes = market["yes_price"]
            no = market["no_price"]
            
            # Check if resolved (price at 0 or 1)
            if yes > 0.99 or yes < 0.01:
                won_side = "YES" if yes > 0.99 else "NO"
                trade["status"] = "closed"
                
                if trade["side"] == won_side:
                    # Won: payout = shares * $1
                    shares = trade["size"] / trade["price"]
                    trade["pnl"] = shares * 1.0 - trade["size"]
                    trade["result"] = "WIN"
                    tf_state["wins"] += 1
                    tf_state["balance"] += trade["size"] + trade["pnl"]
                else:
                    trade["pnl"] = -trade["size"]
                    trade["result"] = "LOSS"
                    tf_state["losses"] += 1
                
                resolved.append(trade)
    
    if resolved:
        save_state(state)
    
    return resolved


def execute_trade(state: dict, timeframe: str, market: dict, decision: dict) -> dict | None:
    """Execute a paper trade."""
    tf_state = state[timeframe]
    
    # Trade size based on balance
    if timeframe == "15m":
        trade_size = 2.0
    else:
        trade_size = 3.0
    
    if tf_state["balance"] < trade_size:
        return None
    
    price = decision["price"]
    if price <= 0 or price >= 1:
        return None
    
    shares = trade_size / price
    
    trade = {
        "id": state["total_trades"] + 1,
        "timestamp": datetime.now().isoformat(),
        "timeframe": timeframe,
        "market": market["question"][:60],
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
    
    tf_state["balance"] -= trade_size
    tf_state["trades"].append(trade)
    state["total_trades"] += 1
    save_state(state)
    
    return trade


def has_open_trade_for_market(state: dict, timeframe: str, slug: str) -> bool:
    """Check if we already have an open trade on this market."""
    for trade in state[timeframe]["trades"]:
        if trade.get("status") == "open" and trade.get("slug") == slug:
            return True
    return False


def cmd_cycle(args):
    """Full trading cycle: resolve → trade → report."""
    state = load_state()
    
    log("🔄 TRADING CYCLE START")
    
    # Step 1: Resolve old trades
    resolved = resolve_trades(state)
    for r in resolved:
        emoji = "✅" if r["result"] == "WIN" else "❌"
        log(f"  {emoji} {r['timeframe']} {r['side']} → {r['result']} (${r['pnl']:+.2f})")
    
    # Step 2: Place new trades
    for tf in ["15m", "1h"]:
        market = fetch_market(tf)
        if not market:
            log(f"  ⏭️ {tf}: No active market found")
            continue
        
        # Don't double-bet on same market
        if has_open_trade_for_market(state, tf, market["slug"]):
            log(f"  ⏭️ {tf}: Already have trade on {market['slug'][:30]}")
            continue
        
        # Check balance
        min_size = 2.0 if tf == "15m" else 3.0
        if state[tf]["balance"] < min_size:
            log(f"  💸 {tf}: Insufficient balance (${state[tf]['balance']:.2f})")
            continue
        
        decision = decide_trade(market, tf, state)
        if decision:
            trade = execute_trade(state, tf, market, decision)
            if trade:
                log(f"  🎯 {tf}: {trade['side']} @ {trade['price']:.3f} — {decision['reason']}")
            else:
                log(f"  ⚠️ {tf}: Trade execution failed")
    
    # Step 3: Quick status
    total_pnl = (state["15m"]["balance"] - 25) + (state["1h"]["balance"] - 25)
    log(f"\n💰 Balance: 15m=${state['15m']['balance']:.2f} | 1h=${state['1h']['balance']:.2f} | P&L=${total_pnl:+.2f}")
    log(f"📊 Record: 15m={state['15m']['wins']}W-{state['15m']['losses']}L | 1h={state['1h']['wins']}W-{state['1h']['losses']}L")
    
    log("🔄 CYCLE COMPLETE")


def cmd_report(args):
    """Generate report for Telegram."""
    state = load_state()
    
    total_pnl = (state["15m"]["balance"] - 25) + (state["1h"]["balance"] - 25)
    total_w = state["15m"]["wins"] + state["1h"]["wins"]
    total_l = state["15m"]["losses"] + state["1h"]["losses"]
    total = total_w + total_l
    wr = (total_w / total * 100) if total > 0 else 0
    
    # Recent trades (last 5)
    all_trades = []
    for tf in ["15m", "1h"]:
        all_trades.extend(state[tf]["trades"])
    all_trades.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    
    print(f"📊 SHORT-TERM TRADING REPORT")
    print(f"")
    print(f"Record: {total_w}W-{total_l}L ({wr:.0f}% WR)")
    print(f"P&L: ${total_pnl:+.2f}")
    print(f"")
    print(f"15min ({state['15m'].get('strategy', '?')}): {state['15m']['wins']}W-{state['15m']['losses']}L | ${state['15m']['balance']:.2f}")
    print(f"1hora ({state['1h'].get('strategy', '?')}): {state['1h']['wins']}W-{state['1h']['losses']}L | ${state['1h']['balance']:.2f}")
    print(f"")
    print(f"Últimos trades:")
    for t in all_trades[:5]:
        pnl = t.get("pnl")
        status = f"${pnl:+.2f}" if pnl is not None else "⏳"
        emoji = "🟢" if pnl and pnl > 0 else "🔴" if pnl and pnl < 0 else "⏳"
        print(f"  {emoji} {t['timeframe']} {t['side']} @ {t['price']:.0%} → {status}")


def cmd_iterate(args):
    """Analyze results and adjust strategy."""
    state = load_state()
    strategy_log = load_strategy_log()
    
    changes = []
    
    for tf in ["15m", "1h"]:
        tf_state = state[tf]
        wins = tf_state["wins"]
        losses = tf_state["losses"]
        total = wins + losses
        strategy = tf_state.get("strategy", "momentum")
        
        if total < 3:
            log(f"  {tf}: Only {total} trades, need more data (min 3)")
            continue
        
        wr = wins / total
        
        log(f"  {tf}: {strategy} → {wins}W-{losses}L ({wr:.0%} WR)")
        
        if wr < 0.4:
            # Strategy not working, try something different
            if strategy == "momentum":
                new_strategy = "mean_reversion"
            elif strategy == "mean_reversion":
                new_strategy = "btc_momentum"
            else:
                new_strategy = "momentum"
            
            tf_state["strategy"] = new_strategy
            changes.append(f"{tf}: {strategy} → {new_strategy} (WR was {wr:.0%})")
            log(f"  ⚡ CHANGED {tf}: {strategy} → {new_strategy}")
        
        elif wr > 0.6:
            log(f"  ✅ {tf}: {strategy} working well, keeping it")
        
        else:
            log(f"  ⚠️ {tf}: {strategy} neutral, keeping for now")
    
    if changes:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "changes": changes,
            "15m_record": f"{state['15m']['wins']}W-{state['15m']['losses']}L",
            "1h_record": f"{state['1h']['wins']}W-{state['1h']['losses']}L",
        }
        strategy_log.append(entry)
        save_strategy_log(strategy_log)
        save_state(state)
        log(f"\n📝 Strategy changes logged: {len(changes)}")
    else:
        log(f"\n📝 No changes needed yet")


def main():
    parser = argparse.ArgumentParser(description="Auto Trader")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    sub = subparsers.add_parser("cycle", help="Full trading cycle")
    sub.set_defaults(func=cmd_cycle)
    
    sub = subparsers.add_parser("report", help="Generate report")
    sub.set_defaults(func=cmd_report)
    
    sub = subparsers.add_parser("iterate", help="Analyze and adjust strategy")
    sub.set_defaults(func=cmd_iterate)
    
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
