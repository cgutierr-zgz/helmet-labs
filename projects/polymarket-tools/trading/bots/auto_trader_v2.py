#!/usr/bin/env python3
"""
Auto Trader v2.2 — Always Active + Data-Driven Learning

v2.2 Changes (Feb 5, 2026):
Philosophy: Trade ALWAYS, collect data, learn, iterate automatically.
Volume of data > perfect risk/reward. WR can drop below 80% if P&L compensates.

Changes from v2.1:
1. Removed restrictive max_price/payout_ratio filters (were blocking all trades)
2. Added rich data logging per trade (entry_price, payout_ratio, bias, market_state)
3. Auto-iteration every 10 trades: analyzes what works, adjusts params
4. Tracks price buckets (cheap <40¢, mid 40-60¢, expensive >60¢) to learn which work
5. Keeps tighter SL (25%) and wider TP (50%/40%) from v2.1

---

v2.0 Features:
- Intra-period exits (take profit / stop loss)
- Only enter with bias >60% (learned from 46 trades)
- Track mid-period price evolution
- Auto-iterate every 15 trades
- Auto-reset when funds < trade_size

Usage:
  python auto_trader_v2.py cycle        # Full cycle: resolve → manage → trade
  python auto_trader_v2.py report       # Summary
  python auto_trader_v2.py iterate      # Analyze and adjust
  python auto_trader_v2.py reset        # Reset pools
"""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request

SCRIPT_DIR = Path(__file__).parent
STATE_FILE = SCRIPT_DIR / "state_v2.json"
ANALYSIS_FILE = SCRIPT_DIR / "analysis_log.json"
BTC_FEED_FILE = SCRIPT_DIR / "btc_feed.json"
CONFIG_OVERRIDE_FILE = SCRIPT_DIR / "config_override.json"

GAMMA_API = "https://gamma-api.polymarket.com"

# v2.2 Config — Always trade, learn from data, iterate
CONFIG = {
    "15m": {
        "pool_size": 25.0,
        "trade_size": 2.0,
        "min_bias": 0.58,       # Slightly relaxed — more trades = more data
        "max_price": 0.85,      # Allow most entries (only skip extreme 85¢+)
        "min_payout_ratio": 0.0, # No ratio filter — we track it and learn which ranges work
        "take_profit": 0.50,    # Let winners run (from v2.1)
        "stop_loss": 0.25,      # Cut losses fast (from v2.1)
        "prefer_cheap": True,   # When both sides qualify, prefer the cheaper one
        "strategies": ["momentum", "contrarian", "volatility"],
        "active_strategy": 0,
    },
    "1h": {
        "pool_size": 25.0,
        "trade_size": 3.0,
        "min_bias": 0.58,
        "max_price": 0.85,
        "min_payout_ratio": 0.0,
        "take_profit": 0.40,
        "stop_loss": 0.25,
        "prefer_cheap": True,
        "strategies": ["momentum", "contrarian", "volatility"],
        "active_strategy": 0,
    },
    "iterate_every": 10,        # Auto-adjust every 10 trades (faster learning)
    "auto_reset_on_empty": True,
}


OVERRIDES = {}  # Store full overrides for non-timeframe keys

def load_config_overrides():
    """Load and apply config overrides from learner.py."""
    global OVERRIDES
    if not CONFIG_OVERRIDE_FILE.exists():
        return
    
    try:
        with open(CONFIG_OVERRIDE_FILE) as f:
            OVERRIDES = json.load(f)
        
        for tf in ["15m", "1h"]:
            if tf in OVERRIDES and tf in CONFIG:
                tf_overrides = OVERRIDES[tf]
                for key, value in tf_overrides.items():
                    # Handle special cases
                    if key == "preferred_strategy":
                        # Map strategy name to index
                        strategies = CONFIG[tf].get("strategies", [])
                        if value in strategies:
                            CONFIG[tf]["active_strategy"] = strategies.index(value)
                    else:
                        # Apply any key (including new ones like min_price, enabled)
                        CONFIG[tf][key] = value
        
        # Log that overrides were applied
        print(f"[CONFIG] Loaded overrides from {CONFIG_OVERRIDE_FILE.name}")
    except Exception as e:
        print(f"[CONFIG] Failed to load overrides: {e}")


# Apply config overrides on import
load_config_overrides()


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
        "15m": {"balance": 25.0, "trades": [], "wins": 0, "losses": 0, "exits_profit": 0, "exits_loss": 0,
                "strategy": "momentum", "generation": 1},
        "1h": {"balance": 25.0, "trades": [], "wins": 0, "losses": 0, "exits_profit": 0, "exits_loss": 0,
                "strategy": "momentum", "generation": 1},
        "total_trades": 0,
        "total_resets": 0,
        "version": "2.0",
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


def fetch_market(timeframe: str) -> dict | None:
    """Fetch current active market."""
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
                        end = m.get("endDate", "")
                        if end:
                            end_ts = datetime.fromisoformat(end.replace("Z", "+00:00")).timestamp()
                            if end_ts > now:
                                return parse_market(m)
            except:
                continue

    elif timeframe == "1h":
        import pytz
        from datetime import timedelta
        et = pytz.timezone('US/Eastern')
        now_et = datetime.now(et)

        for hour_offset in [0, 1]:
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
                            end_ts = datetime.fromisoformat(end.replace("Z", "+00:00")).timestamp()
                            if end_ts > now:
                                return parse_market(m)
            except:
                continue

    return None


def fetch_market_by_slug(slug: str) -> dict | None:
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


def get_bias(market: dict) -> tuple[str, float]:
    """Return dominant side and bias strength."""
    yes = market["yes_price"]
    if yes >= 0.5:
        return "YES", yes
    else:
        return "NO", market["no_price"]


def classify_price(price: float) -> str:
    """Classify entry price into bucket for learning."""
    if price <= 0.35: return "cheap"
    elif price <= 0.55: return "mid"
    else: return "expensive"


def load_btc_context() -> dict | None:
    """Load real-time BTC price context from WebSocket feed."""
    if not BTC_FEED_FILE.exists():
        return None
    
    try:
        with open(BTC_FEED_FILE) as f:
            data = json.load(f)
        
        # Check if data is fresh (< 60 seconds old)
        last_updated = data.get("last_updated", "")
        if last_updated:
            updated_time = datetime.fromisoformat(last_updated)
            age_seconds = (datetime.now() - updated_time).total_seconds()
            if age_seconds > 60:
                return None  # Stale data
        
        return data.get("stats", {})
    except:
        return None


def decide_trade(market: dict, timeframe: str, state: dict) -> dict | None:
    """Decide whether to trade. Always tries to enter — learning from data.
    
    v2.2: Trade always, log everything, learn which setups work.
    v2.3: Integrated with real-time BTC price feed for better timing and confirmation.
    Only skips if bias below minimum or no balance.
    """
    cfg = CONFIG[timeframe]
    tf_state = state[timeframe]
    strategy = tf_state.get("strategy", "momentum")

    dominant_side, bias = get_bias(market)
    yes_price = market["yes_price"]
    no_price = market["no_price"]

    # Load BTC context
    btc = load_btc_context()
    btc_direction_15m = btc.get("direction_15min") if btc else None
    btc_direction_1h = btc.get("direction_1h") if btc else None
    btc_change_5m = btc.get("change_5min_pct", 0) if btc else 0
    btc_change_15m = btc.get("change_15min_pct", 0) if btc else 0
    btc_change_1h = btc.get("change_1h_pct", 0) if btc else 0
    btc_volatility = btc.get("volatility_15min", 0) if btc else 0

    # Don't trade without minimum bias
    if bias < cfg["min_bias"]:
        return None
    
    # v5: min_price filter - only trade sides priced above threshold (buy expensive/likely)
    min_price = cfg.get("min_price", 0)
    if min_price > 0:
        # Check if EITHER side is above min_price
        if yes_price < min_price and no_price < min_price:
            return None  # Neither side is expensive enough

    # Determine which side to buy based on strategy
    if strategy == "momentum":
        # Follow dominant side
        side = dominant_side
        price = yes_price if side == "YES" else no_price
        
        # v5: If min_price is set, prefer the expensive (likely) side
        min_price = cfg.get("min_price", 0)
        if min_price > 0:
            if price < min_price:
                # Dominant side is too cheap, check if other side qualifies
                alt_side = "NO" if side == "YES" else "YES"
                alt_price = no_price if side == "YES" else yes_price
                if alt_price >= min_price:
                    side, price = alt_side, alt_price
                else:
                    return None  # Neither side meets min_price
        
        # BTC momentum confirmation for 15m markets
        if timeframe == "15m" and btc_direction_15m:
            # If we're betting UP but BTC is falling in last 15min, reduce confidence
            if side == "YES" and btc_direction_15m == "down" and btc_change_15m < -0.5:
                # Strong BTC down move contradicts UP bet
                if bias < 0.70:  # Only proceed if very strong bias
                    return None
            # If we're betting DOWN but BTC is rising strongly, caution
            elif side == "NO" and btc_direction_15m == "up" and btc_change_15m > 0.5:
                if bias < 0.70:
                    return None
        
        # BTC momentum confirmation for 1h markets
        if timeframe == "1h" and btc_direction_1h:
            if side == "YES" and btc_direction_1h == "down" and btc_change_1h < -1.0:
                if bias < 0.70:
                    return None
            elif side == "NO" and btc_direction_1h == "up" and btc_change_1h > 1.0:
                if bias < 0.70:
                    return None
        
        # Better entry timing: if BTC just dumped >1% in 5min, DOWN side more likely
        if btc and btc_change_5m < -1.0 and side == "YES":
            # Recent dump favors DOWN
            if bias < 0.75:  # Need very strong bias to override
                return None
        
        # If dominant side is too expensive AND cheap side has decent bias, flip
        if price > cfg["max_price"] and cfg.get("prefer_cheap"):
            alt_side = "NO" if side == "YES" else "YES"
            alt_price = no_price if side == "YES" else yes_price
            if alt_price <= cfg["max_price"]:
                side, price = alt_side, alt_price
                reason = f"Momentum flip→{side} ({bias:.0%}, cheap side)"
            else:
                return None  # Both sides too expensive (shouldn't happen normally)
        else:
            reason = f"Momentum {side} ({bias:.0%})"

    elif strategy == "contrarian":
        if bias > 0.70:
            # Go contrarian: buy the OPPOSITE (cheaper) side
            side = "NO" if dominant_side == "YES" else "YES"
            price = no_price if dominant_side == "YES" else yes_price
            
            # Contrarian signal: BTC dropped >3% in 1h but is bouncing in last 5min
            if btc and btc_change_1h < -3.0 and btc_change_5m > 0.3:
                # Mean reversion opportunity - BTC bouncing after big drop
                if side == "YES":  # Betting on UP, BTC is bouncing
                    reason = f"Contrarian + BTC bounce ({bias:.0%})"
                else:
                    reason = f"Contrarian vs {dominant_side} ({bias:.0%})"
            else:
                reason = f"Contrarian vs {dominant_side} ({bias:.0%})"
        else:
            # Not extreme enough, follow momentum
            side = dominant_side
            price = yes_price if side == "YES" else no_price
            if price > cfg["max_price"] and cfg.get("prefer_cheap"):
                alt_side = "NO" if side == "YES" else "YES"
                alt_price = no_price if side == "YES" else yes_price
                if alt_price <= cfg["max_price"]:
                    side, price = alt_side, alt_price
            reason = f"Weak contrarian→momentum {side} ({bias:.0%})"

    elif strategy == "volatility":
        # Only trade strong bias (>70%)
        if bias < 0.70:
            return None
        side = dominant_side
        price = yes_price if side == "YES" else no_price
        if price > cfg["max_price"] and cfg.get("prefer_cheap"):
            alt_side = "NO" if side == "YES" else "YES"
            alt_price = no_price if side == "YES" else yes_price
            if alt_price <= cfg["max_price"]:
                side, price = alt_side, alt_price
        reason = f"Volatility {side} ({bias:.0%})"
    else:
        return None

    # Calculate payout ratio (for data logging, not filtering)
    max_payout = 1.0 - price
    max_loss = price
    payout_ratio = max_payout / max_loss if max_loss > 0 else 0
    
    # Optional: skip if ratio filter is set and not met
    if cfg["min_payout_ratio"] > 0 and payout_ratio < cfg["min_payout_ratio"]:
        return None
    
    # Position sizing by conviction and volatility
    base_size = cfg["trade_size"]
    
    # Conviction-based sizing
    if bias >= 0.80:
        size_multiplier = 1.25
    elif bias >= 0.70:
        size_multiplier = 1.1
    else:
        size_multiplier = 1.0
    
    # Volatility-based sizing: reduce size in high volatility
    if btc and btc_volatility > 2.0:
        # High volatility (>2% in 15min) → smaller positions
        size_multiplier *= 0.75
    elif btc and btc_volatility > 3.0:
        # Extreme volatility → even smaller
        size_multiplier *= 0.6
    
    trade_size = min(base_size * size_multiplier, tf_state["balance"])
    
    price_bucket = classify_price(price)
    
    return {
        "side": side, 
        "price": price, 
        "reason": reason,
        "size": trade_size,
        "payout_ratio": round(payout_ratio, 2),
        "price_bucket": price_bucket,
        "bias": round(bias, 3),
        "market_state": {
            "yes": round(yes_price, 3),
            "no": round(no_price, 3),
            "dominant": dominant_side,
        },
        "btc_context": {
            "price": round(btc.get("current_price", 0), 2) if btc else None,
            "change_5m": round(btc_change_5m, 2),
            "change_15m": round(btc_change_15m, 2),
            "change_1h": round(btc_change_1h, 2),
            "direction_15m": btc_direction_15m,
            "direction_1h": btc_direction_1h,
            "volatility": round(btc_volatility, 2),
        } if btc else None
    }


def manage_open_trades(state: dict) -> list:
    """Check open trades for take profit / stop loss / resolution."""
    actions = []

    for tf in ["15m", "1h"]:
        cfg = CONFIG[tf]
        tf_state = state[tf]

        for trade in tf_state["trades"]:
            if trade.get("status") != "open":
                continue

            market = fetch_market_by_slug(trade["slug"])
            if not market:
                continue

            yes = market["yes_price"]
            no = market["no_price"]

            # Check resolution
            if yes > 0.99 or yes < 0.01:
                won_side = "YES" if yes > 0.99 else "NO"
                trade["status"] = "closed"
                trade["close_reason"] = "resolved"

                if trade["side"] == won_side:
                    shares = trade["size"] / trade["price"]
                    trade["pnl"] = shares * 1.0 - trade["size"]
                    trade["result"] = "WIN"
                    tf_state["wins"] += 1
                    tf_state["balance"] += trade["size"] + trade["pnl"]
                else:
                    trade["pnl"] = -trade["size"]
                    trade["result"] = "LOSS"
                    tf_state["losses"] += 1

                actions.append(f"{'✅' if trade['result']=='WIN' else '❌'} {tf} {trade['side']} resolved → {trade['result']} (${trade['pnl']:+.2f})")
                continue

            # Check intra-period price movement
            current_price = market["yes_price"] if trade["side"] == "YES" else market["no_price"]
            entry_price = trade["price"]

            if entry_price > 0 and current_price > 0:
                price_change = (current_price - entry_price) / entry_price

                # Take profit
                if price_change >= cfg["take_profit"]:
                    profit = trade["size"] * price_change  # Approximate
                    trade["status"] = "closed"
                    trade["close_reason"] = "take_profit"
                    trade["result"] = "WIN"
                    trade["pnl"] = profit
                    tf_state["wins"] += 1
                    tf_state["exits_profit"] += 1
                    tf_state["balance"] += trade["size"] + profit

                    actions.append(f"💰 {tf} {trade['side']} TAKE PROFIT @ {current_price:.0%} (${profit:+.2f})")
                    continue

                # Stop loss
                if price_change <= -cfg["stop_loss"]:
                    loss = trade["size"] * price_change  # Negative
                    trade["status"] = "closed"
                    trade["close_reason"] = "stop_loss"
                    trade["result"] = "LOSS"
                    trade["pnl"] = loss
                    tf_state["losses"] += 1
                    tf_state["exits_loss"] += 1
                    # Return remaining value
                    remaining = trade["size"] + loss
                    if remaining > 0:
                        tf_state["balance"] += remaining

                    actions.append(f"🛑 {tf} {trade['side']} STOP LOSS @ {current_price:.0%} (${loss:+.2f})")

    if actions:
        save_state(state)

    return actions


def execute_trade(state: dict, timeframe: str, market: dict, decision: dict) -> dict | None:
    tf_state = state[timeframe]
    cfg = CONFIG[timeframe]
    
    # Use size from decision (for position sizing by conviction)
    trade_size = decision.get("size", cfg["trade_size"])
    
    # Ensure we have enough balance
    if tf_state["balance"] < trade_size:
        trade_size = tf_state["balance"]
    
    if trade_size < 0.50:  # Minimum trade size
        return None

    price = decision["price"]
    if price <= 0.01 or price >= 0.99:
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
        "payout_ratio": decision.get("payout_ratio", 0),
        "price_bucket": decision.get("price_bucket", classify_price(price)),
        "bias": decision.get("bias", 0),
        "market_state": decision.get("market_state", {}),
        "btc_context": decision.get("btc_context"),  # Real-time BTC context at entry
        "status": "open",
        "result": None,
        "pnl": None,
        "close_reason": None,
        "strategy": tf_state.get("strategy", "unknown"),
        "generation": tf_state.get("generation", 1),
    }

    tf_state["balance"] -= trade_size
    tf_state["trades"].append(trade)
    state["total_trades"] += 1
    save_state(state)
    return trade


def has_open_trade(state: dict, timeframe: str, slug: str) -> bool:
    for trade in state[timeframe]["trades"]:
        if trade.get("status") == "open" and trade.get("slug") == slug:
            return True
    return False


def check_auto_reset(state: dict) -> list:
    """Reset pools that are out of funds."""
    resets = []
    for tf in ["15m", "1h"]:
        cfg = CONFIG[tf]
        tf_state = state[tf]
        if tf_state["balance"] < cfg["trade_size"]:
            open_trades = [t for t in tf_state["trades"] if t.get("status") == "open"]
            if not open_trades:
                # Save analysis before reset
                gen = tf_state.get("generation", 1)
                wins = tf_state["wins"]
                losses = tf_state["losses"]
                strategy = tf_state.get("strategy", "?")
                total = wins + losses
                wr = (wins / total * 100) if total > 0 else 0

                save_analysis({
                    "timestamp": datetime.now().isoformat(),
                    "timeframe": tf,
                    "generation": gen,
                    "strategy": strategy,
                    "wins": wins,
                    "losses": losses,
                    "win_rate": wr,
                    "exits_profit": tf_state.get("exits_profit", 0),
                    "exits_loss": tf_state.get("exits_loss", 0),
                    "final_balance": tf_state["balance"],
                })

                # Determine next strategy
                strategies = cfg["strategies"]
                current_idx = strategies.index(strategy) if strategy in strategies else -1
                next_idx = (current_idx + 1) % len(strategies)
                next_strategy = strategies[next_idx]

                # Reset
                tf_state["balance"] = cfg["pool_size"]
                tf_state["trades"] = []
                tf_state["wins"] = 0
                tf_state["losses"] = 0
                tf_state["exits_profit"] = 0
                tf_state["exits_loss"] = 0
                tf_state["strategy"] = next_strategy
                tf_state["generation"] = gen + 1
                state["total_resets"] = state.get("total_resets", 0) + 1

                resets.append(f"🔄 {tf} RESET: Gen {gen} ({strategy}, {wr:.0f}% WR) → Gen {gen+1} ({next_strategy})")

    if resets:
        save_state(state)
    return resets


def analyze_trades_by_bucket(trades: list) -> dict:
    """Analyze closed trades grouped by price bucket."""
    buckets = {"cheap": {"w": 0, "l": 0, "pnl": 0.0}, 
               "mid": {"w": 0, "l": 0, "pnl": 0.0}, 
               "expensive": {"w": 0, "l": 0, "pnl": 0.0}}
    
    for t in trades:
        if t.get("status") != "closed":
            continue
        bucket = t.get("price_bucket", classify_price(t.get("price", 0.5)))
        pnl = t.get("pnl", 0)
        if t.get("result") == "WIN":
            buckets[bucket]["w"] += 1
        elif t.get("result") == "LOSS":
            buckets[bucket]["l"] += 1
        buckets[bucket]["pnl"] += pnl
    
    return buckets


def auto_iterate(state: dict) -> list:
    """Data-driven strategy iteration. Analyzes what works, adjusts accordingly.
    
    v2.2: Learns from price buckets, bias ranges, and close reasons.
    Triggers every iterate_every trades per timeframe.
    """
    changes = []
    for tf in ["15m", "1h"]:
        tf_state = state[tf]
        cfg = CONFIG[tf]
        total = tf_state["wins"] + tf_state["losses"]

        if total <= 0 or total % CONFIG["iterate_every"] != 0:
            continue
            
        wr = tf_state["wins"] / total
        strategy = tf_state.get("strategy", "?")
        trades = tf_state["trades"]
        
        # --- Analyze by price bucket ---
        buckets = analyze_trades_by_bucket(trades)
        bucket_insights = []
        for bname, bdata in buckets.items():
            bt = bdata["w"] + bdata["l"]
            if bt >= 3:  # Need minimum sample
                bwr = bdata["w"] / bt
                bucket_insights.append(f"{bname}:{bwr:.0%}({bt}t,${bdata['pnl']:+.2f})")
        
        # --- Analyze by close reason ---
        sl_count = sum(1 for t in trades if t.get("close_reason") == "stop_loss" and t.get("status") == "closed")
        tp_count = sum(1 for t in trades if t.get("close_reason") == "take_profit" and t.get("status") == "closed")
        resolved_w = sum(1 for t in trades if t.get("close_reason") == "resolved" and t.get("result") == "WIN")
        resolved_l = sum(1 for t in trades if t.get("close_reason") == "resolved" and t.get("result") == "LOSS")
        
        # --- Calculate avg win/loss ---
        wins_pnl = [t["pnl"] for t in trades if t.get("result") == "WIN" and "pnl" in t]
        losses_pnl = [t["pnl"] for t in trades if t.get("result") == "LOSS" and "pnl" in t]
        avg_win = sum(wins_pnl) / len(wins_pnl) if wins_pnl else 0
        avg_loss = sum(losses_pnl) / len(losses_pnl) if losses_pnl else 0
        
        pnl = tf_state["balance"] - cfg["pool_size"]
        
        # --- Decision logic ---
        # 1. Strategy rotation if WR is bad
        if wr < 0.40:
            strategies = cfg["strategies"]
            current_idx = strategies.index(strategy) if strategy in strategies else -1
            next_idx = (current_idx + 1) % len(strategies)
            next_strategy = strategies[next_idx]
            tf_state["strategy"] = next_strategy
            changes.append(f"⚡ ROTATE {tf}: {strategy}→{next_strategy} (WR {wr:.0%} too low)")
        # 2. P&L negative despite good WR = risk/reward problem
        elif wr >= 0.60 and pnl < 0:
            changes.append(f"⚠️ {tf}: WR {wr:.0%} but P&L ${pnl:+.2f} — risk/reward issue. AvgW=${avg_win:+.2f} AvgL=${avg_loss:+.2f}")
            # Log which buckets are profitable
            if bucket_insights:
                changes.append(f"  📊 Buckets: {', '.join(bucket_insights)}")
        # 3. Good WR + positive P&L = keep going
        elif wr >= 0.55 and pnl >= 0:
            changes.append(f"✅ {tf}: {strategy} strong ({wr:.0%}, ${pnl:+.2f})")
        else:
            changes.append(f"📊 {tf}: {strategy} ({wr:.0%}, ${pnl:+.2f}) — gathering data")
        
        # Always log close reason analysis
        changes.append(f"  📋 {tf} exits: TP={tp_count} SL={sl_count} Resolved={resolved_w}W/{resolved_l}L")
        
        # --- Save iteration to analysis log ---
        save_analysis({
            "timestamp": datetime.now().isoformat(),
            "timeframe": tf,
            "generation": tf_state.get("generation", 1),
            "strategy": strategy,
            "wins": tf_state["wins"],
            "losses": tf_state["losses"],
            "win_rate": round(wr * 100),
            "pnl": round(pnl, 2),
            "avg_win": round(avg_win, 3),
            "avg_loss": round(avg_loss, 3),
            "buckets": buckets,
            "exits": {"tp": tp_count, "sl": sl_count, "resolved_w": resolved_w, "resolved_l": resolved_l},
        })

    if changes:
        save_state(state)
    return changes


def check_btc_feed_fresh(max_age_seconds: int = 300) -> bool:
    """Check if btc_feed.json is fresh (updated within max_age_seconds)."""
    if not BTC_FEED_FILE.exists():
        return False
    try:
        file_mtime = BTC_FEED_FILE.stat().st_mtime
        age = time.time() - file_mtime
        return age <= max_age_seconds
    except:
        return False


def check_trading_hours() -> bool:
    """Check if current time is within trading hours (from config_override)."""
    if not CONFIG_OVERRIDE_FILE.exists():
        return True
    
    try:
        with open(CONFIG_OVERRIDE_FILE) as f:
            config = json.load(f)
        
        hours = config.get("trading_hours")
        if not hours:
            return True  # No restriction
        
        from datetime import datetime
        import pytz
        
        tz = pytz.timezone(hours.get("timezone", "UTC"))
        now = datetime.now(tz)
        start = hours.get("start", 0)
        end = hours.get("end", 24)
        return start <= now.hour < end
    except:
        return True  # On error, allow trading


def cmd_cycle(args):
    """Full trading cycle."""
    # Check btc_feed freshness first
    if not check_btc_feed_fresh(300):
        log("⚠️ btc_feed.json stale (>5min old), skipping cycle")
        return
    
    # Check trading hours
    if not check_trading_hours():
        log("😴 Outside trading hours, skipping new entries (managing existing only)")
        # Still manage existing trades
        state = load_state()
        actions = manage_open_trades(state)
        for a in actions:
            log(f"  {a}")
        save_state(state)
        return
    
    state = load_state()
    log("🔄 CYCLE v2 START")

    # Step 1: Manage open trades (TP/SL/resolve)
    actions = manage_open_trades(state)
    for a in actions:
        log(f"  {a}")

    # Step 2: Auto-reset empty pools
    resets = check_auto_reset(state)
    for r in resets:
        log(f"  {r}")

    # Step 3: Auto-iterate strategy
    iterations = auto_iterate(state)
    for i in iterations:
        log(f"  {i}")

    # Step 4: Place new trades
    for tf in ["15m", "1h"]:
        cfg = CONFIG[tf]
        
        # Check if timeframe is disabled via override
        if not cfg.get("enabled", True):
            continue
        if OVERRIDES.get("pause_1h_all") and tf == "1h":
            log(f"  ⏸️ {tf} PAUSED (global override)")
            continue
            
        if state[tf]["balance"] < cfg["trade_size"]:
            continue

        market = fetch_market(tf)
        if not market:
            continue

        if has_open_trade(state, tf, market["slug"]):
            continue

        decision = decide_trade(market, tf, state)
        if decision:
            trade = execute_trade(state, tf, market, decision)
            if trade:
                ratio = decision.get('payout_ratio', 0)
                size = trade['size']
                btc_ctx = decision.get('btc_context')
                btc_str = ""
                if btc_ctx and btc_ctx.get('price'):
                    btc_change = btc_ctx.get('change_15m', 0) if tf == '15m' else btc_ctx.get('change_1h', 0)
                    btc_str = f" | BTC ${btc_ctx['price']:,.0f} ({btc_change:+.1f}%)"
                log(f"  🎯 {tf}: {trade['side']} @ {trade['price']:.3f} (${size:.2f}, {ratio:.1f}:1){btc_str} — {decision['reason']}")
        else:
            log(f"  ⏭️ {tf}: No edge (bias/price/ratio)")

    # Status
    total_pnl = (state["15m"]["balance"] - 25) + (state["1h"]["balance"] - 25)
    total_w = state["15m"]["wins"] + state["1h"]["wins"]
    total_l = state["15m"]["losses"] + state["1h"]["losses"]
    log(f"\n💰 Balance: 15m=${state['15m']['balance']:.2f} | 1h=${state['1h']['balance']:.2f}")
    log(f"📊 Record: {total_w}W-{total_l}L | P&L=${total_pnl:+.2f}")
    log(f"🏷️ Strategies: 15m={state['15m']['strategy']} | 1h={state['1h']['strategy']}")

    notable = bool(resets or iterations or [a for a in actions if "TAKE PROFIT" in a])
    if notable:
        log(f"\n📢 NOTABLE — should deliver to Telegram")

    log("🔄 CYCLE v2 COMPLETE")


def cmd_report(args):
    state = load_state()
    total_pnl = (state["15m"]["balance"] - 25) + (state["1h"]["balance"] - 25)
    total_w = state["15m"]["wins"] + state["1h"]["wins"]
    total_l = state["15m"]["losses"] + state["1h"]["losses"]
    total = total_w + total_l
    wr = (total_w / total * 100) if total > 0 else 0

    print(f"📊 TRADER v2 REPORT")
    print(f"Record: {total_w}W-{total_l}L ({wr:.0f}% WR) | P&L: ${total_pnl:+.2f}")
    print(f"Resets: {state.get('total_resets', 0)}")
    print()
    for tf in ["15m", "1h"]:
        s = state[tf]
        cfg = CONFIG[tf]
        t = s['wins'] + s['losses']
        tfwr = (s['wins'] / t * 100) if t > 0 else 0
        print(f"{tf} Gen{s.get('generation',1)} ({s['strategy']}): {s['wins']}W-{s['losses']}L ({tfwr:.0f}%) | ${s['balance']:.2f}")
        print(f"  TP exits: {s.get('exits_profit',0)} | SL exits: {s.get('exits_loss',0)}")
        # Last 3 trades
        for tr in s["trades"][-3:]:
            pnl = tr.get("pnl")
            p = f"${pnl:+.2f}" if pnl is not None else "open"
            reason = tr.get("close_reason", "")
            print(f"  {tr['side']} @ {tr['price']:.0%} → {p} {reason}")
    print()

    # Price bucket analysis
    for tf in ["15m", "1h"]:
        buckets = analyze_trades_by_bucket(state[tf]["trades"])
        has_data = any(b["w"] + b["l"] > 0 for b in buckets.values())
        if has_data:
            print(f"📊 {tf} by price bucket:")
            for bname in ["cheap", "mid", "expensive"]:
                b = buckets[bname]
                bt = b["w"] + b["l"]
                if bt > 0:
                    bwr = b["w"] / bt * 100
                    print(f"  {bname}: {b['w']}W-{b['l']}L ({bwr:.0f}%) ${b['pnl']:+.2f}")

    # Avg win/loss
    all_trades = state["15m"]["trades"] + state["1h"]["trades"]
    wins_pnl = [t["pnl"] for t in all_trades if t.get("result") == "WIN" and t.get("pnl")]
    losses_pnl = [t["pnl"] for t in all_trades if t.get("result") == "LOSS" and t.get("pnl")]
    if wins_pnl or losses_pnl:
        avg_w = sum(wins_pnl) / len(wins_pnl) if wins_pnl else 0
        avg_l = sum(losses_pnl) / len(losses_pnl) if losses_pnl else 0
        ratio = abs(avg_w / avg_l) if avg_l != 0 else 0
        print(f"\n💡 Avg win: ${avg_w:+.2f} | Avg loss: ${avg_l:+.2f} | Ratio: {ratio:.1f}:1")

    # Show analysis log if exists
    if ANALYSIS_FILE.exists():
        try:
            analysis = json.load(open(ANALYSIS_FILE))
            if analysis:
                print("\n📜 Generation history:")
                for a in analysis[-5:]:
                    pnl_str = f"${a.get('pnl', 0):+.2f}" if 'pnl' in a else ""
                    print(f"  Gen{a['generation']} {a['timeframe']} ({a['strategy']}): {a['wins']}W-{a['losses']}L ({a['win_rate']:.0f}%) {pnl_str}")
        except:
            pass


def cmd_reset(args):
    state = load_state()
    # Preserve analysis
    total_resets = state.get("total_resets", 0)
    state = new_state()
    state["total_resets"] = total_resets
    save_state(state)
    print("✅ Full reset. Both pools at $25. v2 ready.")


def cmd_iterate(args):
    state = load_state()
    changes = auto_iterate(state)
    for c in changes:
        log(c)
    if not changes:
        log("No changes needed. Keep trading for more data.")


def main():
    parser = argparse.ArgumentParser(description="Auto Trader v2")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("cycle", help="Full trading cycle").set_defaults(func=cmd_cycle)
    subparsers.add_parser("report", help="Generate report").set_defaults(func=cmd_report)
    subparsers.add_parser("reset", help="Reset pools").set_defaults(func=cmd_reset)
    subparsers.add_parser("iterate", help="Analyze and adjust").set_defaults(func=cmd_iterate)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
