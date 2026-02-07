#!/usr/bin/env python3
"""
Multi-Market Trader v1.0 — Discover and trade across multiple Polymarket markets

Strategy:
- Dynamically discovers high-volume markets with tradeable prices
- Evaluates markets for: momentum, value, mean reversion
- Paper trades with $100 pool, max $5 per position, max 10 open positions
- Logs rich data for learning: category, volume, strategy, price movement

Usage:
  python multi_market_trader.py cycle      # Discover, manage, trade
  python multi_market_trader.py report     # Show positions & stats
  python multi_market_trader.py iterate    # Analyze and adjust
  python multi_market_trader.py reset      # Reset to $100
"""

import argparse
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import urlopen, Request
from collections import Counter

SCRIPT_DIR = Path(__file__).parent
STATE_FILE = SCRIPT_DIR / "state_multi.json"
ANALYSIS_FILE = SCRIPT_DIR / "analysis_multi.json"

GAMMA_API = "https://gamma-api.polymarket.com"

CONFIG = {
    "pool_size": 100.0,
    "max_position_size": 5.0,
    "max_open_positions": 10,
    "min_volume_24h": 50000,
    "min_price": 0.20,
    "max_price": 0.80,
    "max_days_out": 30,
    "take_profit": 0.40,        # Exit at +40% gain
    "stop_loss": 0.30,          # Exit at -30% loss
    
    # Strategy thresholds
    "momentum_threshold": 0.10,  # >10% price move in recent period
    "value_price_min": 0.25,     # Value buys between 25-45¢
    "value_price_max": 0.45,
    "reversion_spike": 0.20,     # >20% spike then reversal
    
    # Filters
    "exclude_slugs": ["btc-updown", "bitcoin-up-or-down", "bitcoin-above"],
}


def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.load(open(STATE_FILE))
        except:
            pass
    return new_state()


def new_state() -> dict:
    return {
        "balance": CONFIG["pool_size"],
        "positions": [],
        "closed_trades": [],
        "total_trades": 0,
        "wins": 0,
        "losses": 0,
        "generation": 1,
        "strategies_used": {"momentum": 0, "value": 0, "reversion": 0},
        "last_discovery": 0,
        "discovered_markets": [],
    }


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def save_analysis(entry: dict):
    log_data = []
    if ANALYSIS_FILE.exists():
        try:
            log_data = json.load(open(ANALYSIS_FILE))
        except:
            pass
    log_data.append(entry)
    with open(ANALYSIS_FILE, "w") as f:
        json.dump(log_data, f, indent=2)


def fetch_json(url: str, timeout: int = 10) -> dict | list | None:
    """Fetch JSON from URL with error handling."""
    try:
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        req = Request(url, headers=headers)
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        log(f"⚠️  Fetch error: {e}")
        return None


def discover_markets() -> list[dict]:
    """Discover active, liquid markets with tradeable prices."""
    log("🔍 Discovering markets...")
    
    # Fetch top 100 by volume
    data = fetch_json(f"{GAMMA_API}/markets?active=true&closed=false&limit=100&order=volume24hr&ascending=false")
    if not data:
        return []
    
    now = datetime.now()
    promising = []
    
    for m in data:
        slug = m.get('slug', '')
        
        # Skip excluded markets
        if any(excl in slug for excl in CONFIG["exclude_slugs"]):
            continue
        
        # Check volume
        vol = m.get('volume24hr', 0)
        if vol < CONFIG["min_volume_24h"]:
            continue
        
        # Parse prices
        prices_str = m.get('outcomePrices', '[]')
        try:
            prices = json.loads(prices_str) if isinstance(prices_str, str) else prices_str
            p1, p2 = float(prices[0]), float(prices[1])
        except:
            continue
        
        # Check if at least one side is tradeable
        has_tradeable = (CONFIG["min_price"] <= p1 <= CONFIG["max_price"]) or \
                       (CONFIG["min_price"] <= p2 <= CONFIG["max_price"])
        
        if not has_tradeable:
            continue
        
        # Check time horizon
        end_str = m.get('endDate', '')
        days_left = 999
        if end_str:
            try:
                end = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                days_left = (end - now.replace(tzinfo=end.tzinfo)).days
                if days_left > CONFIG["max_days_out"]:
                    continue
            except:
                continue
        
        # Categorize market
        category = categorize_market(slug, m.get('question', ''))
        
        promising.append({
            'id': m.get('id', ''),
            'slug': slug,
            'question': m.get('question', ''),
            'yes_price': p1,
            'no_price': p2,
            'volume_24h': vol,
            'days_left': days_left,
            'category': category,
            'end_date': end_str,
        })
    
    log(f"✓ Found {len(promising)} qualifying markets")
    return promising


def categorize_market(slug: str, question: str) -> str:
    """Categorize market for tracking."""
    slug_lower = slug.lower()
    q_lower = question.lower()
    
    if any(x in slug_lower for x in ['nba-', 'nhl-', 'nfl-', 'cbb-']):
        return 'sports'
    elif 'iran' in slug_lower or 'iran' in q_lower:
        return 'geopolitics'
    elif any(x in slug_lower for x in ['election', 'nominate', 'trump', 'president']):
        return 'politics'
    elif any(x in q_lower for x in ['bitcoin', 'crypto', 'solana', 'ethereum']):
        return 'crypto'
    else:
        return 'other'


def evaluate_market(market: dict, state: dict) -> dict | None:
    """Evaluate market and return trade signal if any."""
    
    # Don't trade if we're at max positions
    if len(state["positions"]) >= CONFIG["max_open_positions"]:
        return None
    
    # Don't trade if insufficient balance
    if state["balance"] < CONFIG["max_position_size"]:
        return None
    
    # Check if we already have a position in this market
    if any(p["slug"] == market["slug"] for p in state["positions"]):
        return None
    
    yes_price = market["yes_price"]
    no_price = market["no_price"]
    
    # Strategy 1: Momentum (follow the trend)
    # If one side is strongly favored (>60%) but not extreme, follow it
    if yes_price >= 0.60 and yes_price <= 0.75:
        return {
            "market": market,
            "side": "YES",
            "price": yes_price,
            "strategy": "momentum",
            "reason": f"YES momentum at {yes_price:.2f}"
        }
    elif no_price >= 0.60 and no_price <= 0.75:
        return {
            "market": market,
            "side": "NO",
            "price": no_price,
            "strategy": "momentum",
            "reason": f"NO momentum at {no_price:.2f}"
        }
    
    # Strategy 2: Value (buy cheap)
    # If a side is in value range (25-45¢), buy it
    if CONFIG["value_price_min"] <= yes_price <= CONFIG["value_price_max"]:
        return {
            "market": market,
            "side": "YES",
            "price": yes_price,
            "strategy": "value",
            "reason": f"YES value at {yes_price:.2f}"
        }
    elif CONFIG["value_price_min"] <= no_price <= CONFIG["value_price_max"]:
        return {
            "market": market,
            "side": "NO",
            "price": no_price,
            "strategy": "value",
            "reason": f"NO value at {no_price:.2f}"
        }
    
    # Strategy 3: Mean reversion (advanced, needs historical data)
    # For now, skip - would require tracking price history
    
    return None


def execute_trade(signal: dict, state: dict) -> bool:
    """Execute paper trade."""
    market = signal["market"]
    side = signal["side"]
    price = signal["price"]
    strategy = signal["strategy"]
    
    # Calculate shares
    cost = CONFIG["max_position_size"]
    shares = cost / price
    
    # Deduct from balance
    state["balance"] -= cost
    
    # Create position
    position = {
        "slug": market["slug"],
        "question": market["question"],
        "category": market["category"],
        "side": side,
        "entry_price": price,
        "shares": shares,
        "cost": cost,
        "strategy": strategy,
        "reason": signal["reason"],
        "opened_at": time.time(),
        "volume_at_entry": market["volume_24h"],
        "days_left_at_entry": market["days_left"],
    }
    
    state["positions"].append(position)
    state["total_trades"] += 1
    state["strategies_used"][strategy] += 1
    
    log(f"📈 TRADE: {side} on {market['question'][:50]}")
    log(f"   Strategy: {strategy} | Entry: {price:.3f} | Cost: ${cost:.2f} | Shares: {shares:.2f}")
    log(f"   Category: {market['category']} | Vol: ${market['volume_24h']:,.0f}")
    
    return True


def manage_positions(state: dict):
    """Check open positions for exits (TP/SL) or resolution."""
    if not state["positions"]:
        return
    
    log(f"📊 Managing {len(state['positions'])} open positions...")
    
    closed = []
    
    for pos in state["positions"]:
        # Fetch current market data
        market_data = fetch_json(f"{GAMMA_API}/markets?slug={pos['slug']}")
        if not market_data:
            continue
        
        m = market_data[0] if isinstance(market_data, list) else market_data
        
        # Parse current prices
        prices_str = m.get('outcomePrices', '[]')
        try:
            prices = json.loads(prices_str) if isinstance(prices_str, str) else prices_str
            current_yes = float(prices[0])
            current_no = float(prices[1])
        except:
            continue
        
        current_price = current_yes if pos["side"] == "YES" else current_no
        
        # Calculate P&L
        entry_price = pos["entry_price"]
        shares = pos["shares"]
        current_value = shares * current_price
        pnl = current_value - pos["cost"]
        pnl_pct = (pnl / pos["cost"]) * 100
        
        # Check for TP/SL
        should_close = False
        exit_reason = None
        
        if pnl_pct >= (CONFIG["take_profit"] * 100):
            should_close = True
            exit_reason = "take_profit"
        elif pnl_pct <= -(CONFIG["stop_loss"] * 100):
            should_close = True
            exit_reason = "stop_loss"
        
        # Check if market is closed/resolved
        if not m.get('active', True) or m.get('closed', False):
            should_close = True
            exit_reason = "resolved"
        
        if should_close:
            # Close position
            state["balance"] += current_value
            
            closed_trade = {
                **pos,
                "exit_price": current_price,
                "exit_value": current_value,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "exit_reason": exit_reason,
                "closed_at": time.time(),
                "hold_time_hours": (time.time() - pos["opened_at"]) / 3600,
            }
            
            state["closed_trades"].append(closed_trade)
            
            if pnl > 0:
                state["wins"] += 1
                log(f"✅ WIN: {pos['side']} {pos['question'][:40]} | P&L: ${pnl:+.2f} ({pnl_pct:+.1f}%) | {exit_reason}")
            else:
                state["losses"] += 1
                log(f"❌ LOSS: {pos['side']} {pos['question'][:40]} | P&L: ${pnl:+.2f} ({pnl_pct:+.1f}%) | {exit_reason}")
            
            # Log to analysis
            save_analysis({
                "timestamp": time.time(),
                "category": pos["category"],
                "strategy": pos["strategy"],
                "side": pos["side"],
                "entry_price": entry_price,
                "exit_price": current_price,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "exit_reason": exit_reason,
                "hold_time_hours": closed_trade["hold_time_hours"],
                "volume_at_entry": pos["volume_at_entry"],
            })
            
            closed.append(pos)
    
    # Remove closed positions
    for pos in closed:
        state["positions"].remove(pos)
    
    if closed:
        log(f"📝 Closed {len(closed)} positions")


def cycle(state: dict):
    """Full cycle: discover → manage → trade."""
    log("🔄 Starting cycle...")
    
    # Step 1: Manage existing positions
    manage_positions(state)
    
    # Step 2: Discover markets (cache for 5 minutes)
    now = time.time()
    if now - state.get("last_discovery", 0) > 300:  # 5 min cache
        markets = discover_markets()
        state["discovered_markets"] = markets
        state["last_discovery"] = now
    else:
        markets = state.get("discovered_markets", [])
        log(f"📋 Using cached markets ({len(markets)} available)")
    
    # Step 3: Evaluate and trade
    if state["balance"] < CONFIG["max_position_size"]:
        log(f"⚠️  Insufficient balance: ${state['balance']:.2f}")
    elif len(state["positions"]) >= CONFIG["max_open_positions"]:
        log(f"⚠️  At max positions: {len(state['positions'])}/{CONFIG['max_open_positions']}")
    else:
        # Sort markets by volume (trade highest volume first)
        markets.sort(key=lambda m: m["volume_24h"], reverse=True)
        
        trades_made = 0
        for market in markets:
            if trades_made >= 3:  # Max 3 new trades per cycle
                break
            
            signal = evaluate_market(market, state)
            if signal:
                if execute_trade(signal, state):
                    trades_made += 1
                    save_state(state)
        
        if trades_made == 0:
            log("💤 No trading opportunities found")
    
    save_state(state)
    log("✓ Cycle complete")


def report(state: dict):
    """Show current status."""
    print("\n" + "="*70)
    print(f"💼 MULTI-MARKET TRADER v1.0 — Gen {state['generation']}")
    print("="*70)
    
    print(f"\n💰 Balance: ${state['balance']:.2f} / ${CONFIG['pool_size']:.2f}")
    print(f"📊 Total Trades: {state['total_trades']} | W: {state['wins']} | L: {state['losses']}")
    
    if state['total_trades'] > 0:
        wr = (state['wins'] / state['total_trades']) * 100
        print(f"📈 Win Rate: {wr:.1f}%")
    
    # Show strategy breakdown
    print(f"\n🎯 Strategies Used:")
    for strat, count in state["strategies_used"].items():
        print(f"   {strat}: {count}")
    
    # Show open positions
    if state["positions"]:
        print(f"\n📍 Open Positions ({len(state['positions'])}):")
        for pos in state["positions"]:
            hours = (time.time() - pos["opened_at"]) / 3600
            print(f"   • {pos['side']:3} {pos['question'][:50]}")
            print(f"     Strategy: {pos['strategy']:10} | Entry: {pos['entry_price']:.3f} | Open: {hours:.1f}h")
    else:
        print("\n📍 No open positions")
    
    # Show recent closed trades
    if state["closed_trades"]:
        recent = state["closed_trades"][-5:]
        print(f"\n📝 Recent Closed Trades (last {len(recent)}):")
        for trade in recent:
            pnl_str = f"${trade['pnl']:+.2f} ({trade['pnl_pct']:+.1f}%)"
            result = "✅" if trade['pnl'] > 0 else "❌"
            print(f"   {result} {trade['side']:3} {trade['question'][:45]}")
            print(f"      {trade['strategy']:10} | {pnl_str:>18} | {trade['exit_reason']}")
    
    # Category performance
    if state["closed_trades"]:
        print(f"\n📂 Category Performance:")
        cat_stats = {}
        for trade in state["closed_trades"]:
            cat = trade["category"]
            if cat not in cat_stats:
                cat_stats[cat] = {"trades": 0, "wins": 0, "pnl": 0}
            cat_stats[cat]["trades"] += 1
            if trade["pnl"] > 0:
                cat_stats[cat]["wins"] += 1
            cat_stats[cat]["pnl"] += trade["pnl"]
        
        for cat, stats in sorted(cat_stats.items(), key=lambda x: x[1]["pnl"], reverse=True):
            wr = (stats["wins"] / stats["trades"]) * 100 if stats["trades"] > 0 else 0
            print(f"   {cat:12} | {stats['trades']:2} trades | WR: {wr:5.1f}% | P&L: ${stats['pnl']:+.2f}")
    
    print("\n" + "="*70 + "\n")


def iterate(state: dict):
    """Analyze performance and adjust."""
    log("🔬 Analyzing performance...")
    
    if state["total_trades"] < 10:
        log(f"⏳ Need at least 10 trades (have {state['total_trades']})")
        return
    
    # Analyze by strategy
    print("\n📊 Strategy Analysis:")
    strat_stats = {}
    for trade in state["closed_trades"]:
        strat = trade["strategy"]
        if strat not in strat_stats:
            strat_stats[strat] = {"trades": 0, "wins": 0, "pnl": 0}
        strat_stats[strat]["trades"] += 1
        if trade["pnl"] > 0:
            strat_stats[strat]["wins"] += 1
        strat_stats[strat]["pnl"] += trade["pnl"]
    
    for strat, stats in strat_stats.items():
        if stats["trades"] > 0:
            wr = (stats["wins"] / stats["trades"]) * 100
            avg_pnl = stats["pnl"] / stats["trades"]
            print(f"   {strat:10} | {stats['trades']:2} trades | WR: {wr:5.1f}% | Avg P&L: ${avg_pnl:+.2f}")
    
    # Analyze by category
    print("\n📂 Category Analysis:")
    cat_stats = {}
    for trade in state["closed_trades"]:
        cat = trade["category"]
        if cat not in cat_stats:
            cat_stats[cat] = {"trades": 0, "wins": 0, "pnl": 0}
        cat_stats[cat]["trades"] += 1
        if trade["pnl"] > 0:
            cat_stats[cat]["wins"] += 1
        cat_stats[cat]["pnl"] += trade["pnl"]
    
    for cat, stats in sorted(cat_stats.items(), key=lambda x: x[1]["pnl"], reverse=True):
        if stats["trades"] > 0:
            wr = (stats["wins"] / stats["trades"]) * 100
            avg_pnl = stats["pnl"] / stats["trades"]
            print(f"   {cat:12} | {stats['trades']:2} trades | WR: {wr:5.1f}% | Avg P&L: ${avg_pnl:+.2f}")
    
    # Check if we should reset
    if state["balance"] < CONFIG["max_position_size"]:
        log("\n⚠️  Balance too low to continue — consider reset")
    
    state["generation"] += 1
    save_state(state)
    log(f"\n✓ Iteration complete — Gen {state['generation']}")


def reset(state: dict):
    """Reset to initial state."""
    log(f"🔄 Resetting to ${CONFIG['pool_size']:.2f}...")
    
    # Save final state to closed trades
    if state["positions"]:
        log(f"⚠️  Closing {len(state['positions'])} open positions")
        for pos in state["positions"]:
            state["closed_trades"].append({
                **pos,
                "exit_reason": "reset",
                "closed_at": time.time(),
                "pnl": -pos["cost"],  # Count as loss
            })
    
    # Create new state but preserve trade history
    old_closed = state.get("closed_trades", [])
    new = new_state()
    new["closed_trades"] = old_closed
    
    save_state(new)
    log("✓ Reset complete")


def main():
    parser = argparse.ArgumentParser(description="Multi-Market Trader")
    parser.add_argument("action", choices=["cycle", "report", "iterate", "reset"])
    args = parser.parse_args()
    
    state = load_state()
    
    if args.action == "cycle":
        cycle(state)
    elif args.action == "report":
        report(state)
    elif args.action == "iterate":
        iterate(state)
    elif args.action == "reset":
        reset(state)
    
    if args.action in ["cycle", "report", "iterate"]:
        report(state)


if __name__ == "__main__":
    main()
