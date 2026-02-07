#!/usr/bin/env python3
"""
Bot B: Technical Indicators Trader (v2 - Confidence-Based)

Same as auto_trader_v2 BUT adds technical analysis from BTC price history.
Uses Binance REST API for candles, calculates RSI/EMA/MACD/Bollinger (pure Python).

NEW IN v2: Indicators MODIFY CONFIDENCE instead of VETO.
- Base confidence = market bias (e.g., 65% bias → 65% confidence)
- Indicators adjust ±15% (RSI) or ±10% (EMA/MACD/BTC)
- Trade only if final confidence > 50%

This prevents good momentum signals from being vetoed by single indicator disagreement.

Usage:
  python bot_b_technical.py cycle        # Full cycle: resolve → manage → trade
  python bot_b_technical.py report       # Summary
  python bot_b_technical.py iterate      # Analyze and adjust
  python bot_b_technical.py reset        # Reset pools
"""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request

SCRIPT_DIR = Path(__file__).parent
STATE_FILE = SCRIPT_DIR / "state_bot_b.json"
ANALYSIS_FILE = SCRIPT_DIR / "analysis_bot_b.json"
BTC_FEED_FILE = SCRIPT_DIR / "btc_feed.json"
CONFIG_OVERRIDE_FILE = SCRIPT_DIR / "config_override.json"

GAMMA_API = "https://gamma-api.polymarket.com"
BINANCE_API = "https://api.binance.com/api/v3/klines"

# Bot B Config — same pools as v2
CONFIG = {
    "15m": {
        "pool_size": 25.0,
        "trade_size": 2.0,
        "min_bias": 0.58,
        "max_price": 0.85,
        "take_profit": 0.50,
        "stop_loss": 0.25,
        "prefer_cheap": True,
        "strategies": ["momentum", "contrarian", "volatility"],
        "active_strategy": 0,
    },
    "1h": {
        "pool_size": 25.0,
        "trade_size": 3.0,
        "min_bias": 0.58,
        "max_price": 0.85,
        "take_profit": 0.40,
        "stop_loss": 0.25,
        "prefer_cheap": True,
        "strategies": ["momentum", "contrarian", "volatility"],
        "active_strategy": 0,
    },
    "iterate_every": 10,
    "auto_reset_on_empty": True,
    "min_confidence": 50,  # Minimum confidence to trade
}


OVERRIDES = {}  # Store full overrides for non-timeframe keys

def load_config_overrides():
    """Load and apply config overrides from shared config_override.json."""
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
                    # Apply any key (including new ones like min_price, enabled)
                    CONFIG[tf][key] = value
        
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
        "version": "bot_b_technical_v2",
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


# ==================== TECHNICAL INDICATORS ====================

def fetch_binance_candles(interval: str, limit: int) -> list:
    """Fetch BTC/USDT candles from Binance.
    
    Returns list of candles: [[openTime, open, high, low, close, volume, ...], ...]
    """
    try:
        url = f"{BINANCE_API}?symbol=BTCUSDT&interval={interval}&limit={limit}"
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data
    except Exception as e:
        log(f"⚠️ Binance API error: {e}")
        return []


def calculate_rsi(prices: list, period: int = 14) -> float:
    """Calculate RSI from price list (pure Python)."""
    if len(prices) < period + 1:
        return 50.0  # Neutral if not enough data
    
    changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains = [c if c > 0 else 0 for c in changes]
    losses = [-c if c < 0 else 0 for c in changes]
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_ema(prices: list, period: int) -> float:
    """Calculate EMA (Exponential Moving Average)."""
    if len(prices) < period:
        return sum(prices) / len(prices)  # Simple average if not enough data
    
    # Start with SMA for first period
    sma = sum(prices[:period]) / period
    multiplier = 2 / (period + 1)
    ema = sma
    
    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema
    
    return ema


def calculate_macd(prices: list, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    """Calculate MACD, signal line, and histogram."""
    if len(prices) < slow:
        return {"macd": 0, "signal": 0, "histogram": 0}
    
    ema_fast = calculate_ema(prices, fast)
    ema_slow = calculate_ema(prices, slow)
    macd_line = ema_fast - ema_slow
    
    # For signal line, we'd need to calculate EMA of MACD values
    # Simplified: use macd_line as approximation
    signal_line = macd_line * 0.9  # Rough approximation
    histogram = macd_line - signal_line
    
    return {
        "macd": round(macd_line, 2),
        "signal": round(signal_line, 2),
        "histogram": round(histogram, 2),
    }


def calculate_bollinger_bands(prices: list, period: int = 20, std_dev: int = 2) -> dict:
    """Calculate Bollinger Bands."""
    if len(prices) < period:
        avg = sum(prices) / len(prices)
        return {"upper": avg * 1.02, "middle": avg, "lower": avg * 0.98}
    
    recent = prices[-period:]
    middle = sum(recent) / period
    
    # Standard deviation
    variance = sum((p - middle) ** 2 for p in recent) / period
    std = variance ** 0.5
    
    upper = middle + (std_dev * std)
    lower = middle - (std_dev * std)
    
    return {
        "upper": round(upper, 2),
        "middle": round(middle, 2),
        "lower": round(lower, 2),
    }


def get_technical_indicators() -> dict:
    """Fetch candles and calculate all indicators."""
    # Fetch 1-min candles (last 100)
    candles_1m = fetch_binance_candles("1m", 100)
    # Fetch 5-min candles (last 50)
    candles_5m = fetch_binance_candles("5m", 50)
    
    if not candles_1m:
        return None
    
    # Extract close prices
    closes_1m = [float(c[4]) for c in candles_1m]  # Close is index 4
    closes_5m = [float(c[4]) for c in candles_5m] if candles_5m else []
    
    current_price = closes_1m[-1] if closes_1m else 0
    
    # Calculate indicators on 1-min data
    rsi = calculate_rsi(closes_1m, 14)
    ema9 = calculate_ema(closes_1m, 9)
    ema21 = calculate_ema(closes_1m, 21)
    macd = calculate_macd(closes_1m, 12, 26, 9)
    bollinger = calculate_bollinger_bands(closes_1m, 20, 2)
    
    return {
        "current_price": round(current_price, 2),
        "rsi": round(rsi, 2),
        "ema9": round(ema9, 2),
        "ema21": round(ema21, 2),
        "ema_cross": "bullish" if ema9 > ema21 else "bearish",
        "macd": macd,
        "macd_trend": "bullish" if macd["macd"] > macd["signal"] else "bearish",
        "bollinger": bollinger,
        "price_vs_bollinger": (
            "below_lower" if current_price < bollinger["lower"]
            else "above_upper" if current_price > bollinger["upper"]
            else "middle"
        ),
    }


# ==================== POLYMARKET FUNCTIONS ====================

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


# ==================== BTC FEED ====================

def load_btc_context() -> dict | None:
    """Load real-time BTC price context from WebSocket feed."""
    if not BTC_FEED_FILE.exists():
        return None
    try:
        with open(BTC_FEED_FILE) as f:
            data = json.load(f)
        last_updated = data.get("last_updated", "")
        if last_updated:
            updated_time = datetime.fromisoformat(last_updated)
            age_seconds = (datetime.now() - updated_time).total_seconds()
            if age_seconds > 60:
                return None
        return data.get("stats", {})
    except:
        return None


# ==================== TRADING LOGIC: CONFIDENCE-BASED (v2) ====================

def decide_trade(market: dict, timeframe: str, state: dict, indicators: dict) -> dict | None:
    """Decide whether to trade using CONFIDENCE-BASED system.
    
    NEW LOGIC (v2): Indicators MODIFY confidence, they don't VETO.
    
    1. Base confidence = bias strength (e.g., 65% bias → 65% confidence)
    2. Indicators adjust confidence:
       - RSI confirms direction: +15%
       - RSI contradicts direction: -15%
       - EMA/MACD confirm: +10%
       - EMA/MACD contradict: -10%
       - BTC feed confirms: +10%
       - BTC feed contradicts: -10%
    3. Trade only if final confidence > 50%
    
    This allows good momentum signals to go through even with some indicator disagreement.
    """
    cfg = CONFIG[timeframe]
    tf_state = state[timeframe]
    strategy = tf_state.get("strategy", "momentum")
    min_confidence = CONFIG.get("min_confidence", 50)
    
    # Load BTC real-time context
    btc = load_btc_context()

    dominant_side, bias = get_bias(market)
    yes_price = market["yes_price"]
    no_price = market["no_price"]

    # Check minimum bias (this is still a hard requirement)
    if bias < cfg["min_bias"]:
        return None

    # === CONFIDENCE-BASED SYSTEM ===
    # Start with base confidence from market bias
    # Bias 0.58 = 58% base confidence, bias 0.75 = 75% base confidence
    base_confidence = bias * 100  # Convert to percentage
    confidence = base_confidence
    confidence_log = [f"Base: {base_confidence:.0f}%"]
    
    # Default side follows momentum
    side = dominant_side
    price = yes_price if side == "YES" else no_price
    
    if indicators:
        rsi = indicators["rsi"]
        ema_cross = indicators["ema_cross"]
        macd_trend = indicators["macd_trend"]
        price_vs_bb = indicators["price_vs_bollinger"]
        
        # === RSI ADJUSTMENT (±15%) ===
        # RSI > 70 = overbought (bearish signal), RSI < 30 = oversold (bullish signal)
        if side == "YES":
            # Betting UP
            if rsi < 30:
                # Oversold = bullish signal, but betting UP here is risky (might already have bounced)
                confidence -= 15
                confidence_log.append(f"RSI oversold ({rsi:.0f}): -15%")
            elif rsi > 70:
                # Overbought = bearish signal, contradicts our UP bet
                confidence -= 15
                confidence_log.append(f"RSI overbought ({rsi:.0f}): -15%")
            elif 30 <= rsi <= 50:
                # RSI in neutral-bullish zone, confirms UP
                confidence += 15
                confidence_log.append(f"RSI bullish zone ({rsi:.0f}): +15%")
        else:
            # Betting DOWN (side == "NO")
            if rsi > 70:
                # Overbought = bearish signal, confirms DOWN bet
                confidence += 15
                confidence_log.append(f"RSI overbought ({rsi:.0f}): +15%")
            elif rsi < 30:
                # Oversold = bullish signal, contradicts DOWN bet
                confidence -= 15
                confidence_log.append(f"RSI oversold ({rsi:.0f}): -15%")
            elif 50 <= rsi <= 70:
                # RSI in neutral-bearish zone, confirms DOWN
                confidence += 15
                confidence_log.append(f"RSI bearish zone ({rsi:.0f}): +15%")
        
        # === EMA ADJUSTMENT (±10%) ===
        if side == "YES":
            if ema_cross == "bullish":
                confidence += 10
                confidence_log.append("EMA bullish: +10%")
            else:
                confidence -= 10
                confidence_log.append("EMA bearish: -10%")
        else:
            if ema_cross == "bearish":
                confidence += 10
                confidence_log.append("EMA bearish: +10%")
            else:
                confidence -= 10
                confidence_log.append("EMA bullish: -10%")
        
        # === MACD ADJUSTMENT (±10%) ===
        if side == "YES":
            if macd_trend == "bullish":
                confidence += 10
                confidence_log.append("MACD bullish: +10%")
            else:
                confidence -= 10
                confidence_log.append("MACD bearish: -10%")
        else:
            if macd_trend == "bearish":
                confidence += 10
                confidence_log.append("MACD bearish: +10%")
            else:
                confidence -= 10
                confidence_log.append("MACD bullish: -10%")
        
        # === BOLLINGER ADJUSTMENT (±5%) ===
        if side == "YES" and price_vs_bb == "below_lower":
            confidence += 5
            confidence_log.append("BB oversold: +5%")
        elif side == "NO" and price_vs_bb == "above_upper":
            confidence += 5
            confidence_log.append("BB overbought: +5%")
    
    # === BTC FEED ADJUSTMENT (±10%) ===
    if btc:
        change_key = "change_15min_pct" if timeframe == "15m" else "change_1h_pct"
        btc_change = btc.get(change_key)
        if btc_change is not None:
            if side == "YES":
                if btc_change > 0.3:
                    confidence += 10
                    confidence_log.append(f"BTC rising ({btc_change:+.1f}%): +10%")
                elif btc_change < -0.3:
                    confidence -= 10
                    confidence_log.append(f"BTC falling ({btc_change:+.1f}%): -10%")
            else:  # side == "NO"
                if btc_change < -0.3:
                    confidence += 10
                    confidence_log.append(f"BTC falling ({btc_change:+.1f}%): +10%")
                elif btc_change > 0.3:
                    confidence -= 10
                    confidence_log.append(f"BTC rising ({btc_change:+.1f}%): -10%")
    
    # === FINAL CONFIDENCE CHECK ===
    confidence_log.append(f"= {confidence:.0f}%")
    reason = " → ".join(confidence_log)
    
    # Only trade if confidence > min_confidence
    if confidence <= min_confidence:
        log(f"  ⏭️ {timeframe}: Confidence too low: {reason}")
        return None
    
    # === PRICE CHECK (prefer cheap side) ===
    if price > cfg["max_price"] and cfg.get("prefer_cheap"):
        alt_side = "NO" if side == "YES" else "YES"
        alt_price = no_price if side == "YES" else yes_price
        if alt_price <= cfg["max_price"]:
            # Flip to cheap side but reduce confidence
            side, price = alt_side, alt_price
            confidence -= 15
            reason += " → flipped to cheap: -15%"
            confidence_log[-1] = f"= {confidence:.0f}% (after flip)"
            
            # Re-check confidence after flip
            if confidence <= min_confidence:
                log(f"  ⏭️ {timeframe}: Confidence too low after flip: {reason}")
                return None
        else:
            return None

    # Calculate payout ratio
    max_payout = 1.0 - price
    max_loss = price
    payout_ratio = max_payout / max_loss if max_loss > 0 else 0
    
    trade_size = cfg["trade_size"]
    price_bucket = classify_price(price)
    
    return {
        "side": side,
        "price": price,
        "reason": reason,
        "confidence": round(confidence, 1),
        "size": trade_size,
        "payout_ratio": round(payout_ratio, 2),
        "price_bucket": price_bucket,
        "bias": round(bias, 3),
        "market_state": {
            "yes": round(yes_price, 3),
            "no": round(no_price, 3),
            "dominant": dominant_side,
        },
        "indicators": indicators,  # LOG ALL INDICATORS
        "btc_context": btc,  # LOG BTC FEED STATE
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
                    profit = trade["size"] * price_change
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
                    loss = trade["size"] * price_change
                    trade["status"] = "closed"
                    trade["close_reason"] = "stop_loss"
                    trade["result"] = "LOSS"
                    trade["pnl"] = loss
                    tf_state["losses"] += 1
                    tf_state["exits_loss"] += 1
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
    
    trade_size = decision.get("size", cfg["trade_size"])
    
    if tf_state["balance"] < trade_size:
        trade_size = tf_state["balance"]
    
    if trade_size < 0.50:
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
        "confidence": decision.get("confidence", 0),
        "payout_ratio": decision.get("payout_ratio", 0),
        "price_bucket": decision.get("price_bucket", classify_price(price)),
        "bias": decision.get("bias", 0),
        "market_state": decision.get("market_state", {}),
        "indicators": decision.get("indicators"),  # LOG INDICATORS
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

                strategies = cfg["strategies"]
                current_idx = strategies.index(strategy) if strategy in strategies else -1
                next_idx = (current_idx + 1) % len(strategies)
                next_strategy = strategies[next_idx]

                tf_state["balance"] = cfg["pool_size"]
                tf_state["trades"] = []
                tf_state["wins"] = 0
                tf_state["losses"] = 0
                tf_state["exits_profit"] = 0
                tf_state["exits_loss"] = 0
                tf_state["strategy"] = next_strategy
                tf_state["generation"] = gen + 1
                state["total_resets"] = state.get("total_resets", 0) + 1

                resets.append(f"🔄 BOT B {tf} RESET: Gen {gen} ({strategy}, {wr:.0f}% WR) → Gen {gen+1} ({next_strategy})")

    if resets:
        save_state(state)
    return resets


def auto_iterate(state: dict) -> list:
    """Data-driven strategy iteration."""
    changes = []
    for tf in ["15m", "1h"]:
        tf_state = state[tf]
        cfg = CONFIG[tf]
        total = tf_state["wins"] + tf_state["losses"]

        if total <= 0 or total % CONFIG["iterate_every"] != 0:
            continue
            
        wr = tf_state["wins"] / total
        strategy = tf_state.get("strategy", "?")
        pnl = tf_state["balance"] - cfg["pool_size"]
        
        if wr < 0.40:
            strategies = cfg["strategies"]
            current_idx = strategies.index(strategy) if strategy in strategies else -1
            next_idx = (current_idx + 1) % len(strategies)
            next_strategy = strategies[next_idx]
            tf_state["strategy"] = next_strategy
            changes.append(f"⚡ BOT B ROTATE {tf}: {strategy}→{next_strategy} (WR {wr:.0%})")
        elif wr >= 0.60 and pnl < 0:
            changes.append(f"⚠️ BOT B {tf}: WR {wr:.0%} but P&L ${pnl:+.2f}")
        elif wr >= 0.55 and pnl >= 0:
            changes.append(f"✅ BOT B {tf}: {strategy} strong ({wr:.0%}, ${pnl:+.2f})")
        else:
            changes.append(f"📊 BOT B {tf}: {strategy} ({wr:.0%}, ${pnl:+.2f})")

    if changes:
        save_state(state)
    return changes


# ==================== CLI COMMANDS ====================

def check_btc_feed_fresh(max_age_seconds: int = 300) -> bool:
    """Check if btc_feed.json is fresh (updated within max_age_seconds)."""
    if not BTC_FEED_FILE.exists():
        return False
    try:
        import time
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
        log("😴 BOT B: Outside trading hours (6-14 ET), managing existing only")
        state = load_state()
        actions = manage_open_trades(state)
        for a in actions:
            log(f"  {a}")
        save_state(state)
        return
    
    state = load_state()
    
    # Check if paused
    if state.get("paused"):
        reason = state.get("paused_reason", "unknown")
        log(f"⏸️ BOT B PAUSED: {reason}")
        log("   Managing existing positions only, no new entries")
        # Still manage open trades
        actions = manage_open_trades(state)
        for a in actions:
            log(f"  {a}")
        save_state(state)
        return
    
    log("🔄 BOT B (Technical - Confidence v2) CYCLE START")

    # Step 1: Manage open trades
    actions = manage_open_trades(state)
    for a in actions:
        log(f"  {a}")

    # Step 2: Auto-reset
    resets = check_auto_reset(state)
    for r in resets:
        log(f"  {r}")

    # Step 3: Auto-iterate
    iterations = auto_iterate(state)
    for i in iterations:
        log(f"  {i}")

    # Step 4: Get technical indicators
    indicators = get_technical_indicators()
    if indicators:
        log(f"  📊 Indicators: RSI={indicators['rsi']:.1f}, EMA={indicators['ema_cross']}, MACD={indicators['macd_trend']}, BB={indicators['price_vs_bollinger']}")
    else:
        log(f"  ⚠️ Could not fetch indicators")

    # Step 5: Place new trades
    for tf in ["15m", "1h"]:
        cfg = CONFIG[tf]
        
        # Check if timeframe is disabled via override
        if not cfg.get("enabled", True):
            continue
        if (OVERRIDES.get("pause_1h_all") or OVERRIDES.get("bot_b_pause_1h")) and tf == "1h":
            log(f"  ⏸️ 1h PAUSED (override)")
            continue
            
        if state[tf]["balance"] < cfg["trade_size"]:
            continue

        market = fetch_market(tf)
        if not market:
            continue

        if has_open_trade(state, tf, market["slug"]):
            continue

        decision = decide_trade(market, tf, state, indicators)
        if decision:
            trade = execute_trade(state, tf, market, decision)
            if trade:
                conf = decision.get('confidence', 0)
                log(f"  🎯 {tf}: {trade['side']} @ {trade['price']:.3f} (${trade['size']:.2f}) | Conf: {conf:.0f}%")
                log(f"      {decision['reason']}")

    # Status
    total_pnl = (state["15m"]["balance"] - 25) + (state["1h"]["balance"] - 25)
    total_w = state["15m"]["wins"] + state["1h"]["wins"]
    total_l = state["15m"]["losses"] + state["1h"]["losses"]
    log(f"\n💰 BOT B Balance: 15m=${state['15m']['balance']:.2f} | 1h=${state['1h']['balance']:.2f}")
    log(f"📊 BOT B Record: {total_w}W-{total_l}L | P&L=${total_pnl:+.2f}")
    log("🔄 BOT B CYCLE COMPLETE")


def cmd_report(args):
    state = load_state()
    total_pnl = (state["15m"]["balance"] - 25) + (state["1h"]["balance"] - 25)
    total_w = state["15m"]["wins"] + state["1h"]["wins"]
    total_l = state["15m"]["losses"] + state["1h"]["losses"]
    total = total_w + total_l
    wr = (total_w / total * 100) if total > 0 else 0

    print(f"📊 BOT B (Technical - Confidence v2) REPORT")
    print(f"Record: {total_w}W-{total_l}L ({wr:.0f}% WR) | P&L: ${total_pnl:+.2f}")
    print(f"Resets: {state.get('total_resets', 0)}")
    print()
    for tf in ["15m", "1h"]:
        s = state[tf]
        t = s['wins'] + s['losses']
        tfwr = (s['wins'] / t * 100) if t > 0 else 0
        print(f"{tf} Gen{s.get('generation',1)} ({s['strategy']}): {s['wins']}W-{s['losses']}L ({tfwr:.0f}%) | ${s['balance']:.2f}")
        
        # Show last 3 trades with confidence
        for tr in s["trades"][-3:]:
            pnl = tr.get("pnl")
            p = f"${pnl:+.2f}" if pnl is not None else "open"
            conf = tr.get("confidence", 0)
            print(f"  {tr['side']} @ {tr['price']:.0%} → {p} | Conf: {conf:.0f}%")


def cmd_reset(args):
    state = new_state()
    save_state(state)
    print("✅ BOT B reset. Both pools at $25.")


def cmd_iterate(args):
    state = load_state()
    changes = auto_iterate(state)
    for c in changes:
        log(c)
    if not changes:
        log("BOT B: No changes needed.")


def main():
    parser = argparse.ArgumentParser(description="Bot B: Technical Indicators Trader (Confidence v2)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("cycle", help="Full trading cycle").set_defaults(func=cmd_cycle)
    subparsers.add_parser("report", help="Generate report").set_defaults(func=cmd_report)
    subparsers.add_parser("reset", help="Reset pools").set_defaults(func=cmd_reset)
    subparsers.add_parser("iterate", help="Analyze and adjust").set_defaults(func=cmd_iterate)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
