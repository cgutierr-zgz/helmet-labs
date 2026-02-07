#!/usr/bin/env python3
"""
Bot C: AI Decision Maker

Same markets as auto_trader_v2 BUT uses an LLM (gpt-4o-mini) to make trading decisions.

Collects ALL data:
- Polymarket prices + bias
- BTC price changes (1min, 5min, 15min, 1h)
- Technical indicators (RSI, EMA, MACD, Bollinger)
- Recent trade history

Builds a prompt, calls OpenAI API, parses JSON response, executes trade.

Logs full prompt, response, and reasoning with each trade for learning.

Usage:
  python bot_c_ai.py cycle        # Full cycle: resolve → manage → trade
  python bot_c_ai.py report       # Summary
  python bot_c_ai.py iterate      # Analyze and adjust
  python bot_c_ai.py reset        # Reset pools
"""

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

SCRIPT_DIR = Path(__file__).parent
STATE_FILE = SCRIPT_DIR / "state_bot_c.json"
ANALYSIS_FILE = SCRIPT_DIR / "analysis_bot_c.json"
BTC_FEED_FILE = SCRIPT_DIR / "btc_feed.json"
CONFIG_OVERRIDE_FILE = SCRIPT_DIR / "config_override.json"

GAMMA_API = "https://gamma-api.polymarket.com"
BINANCE_API = "https://api.binance.com/api/v3/klines"
ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
OPENAI_API = "https://api.openai.com/v1/chat/completions"
AI_MODEL = "claude-sonnet-4-5-20250514"  # Sonnet 4.5 for trading decisions

# Get API keys from environment
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Try reading Anthropic key from secrets
if not ANTHROPIC_API_KEY:
    secrets_file = Path.home() / ".openclaw" / ".secrets" / "anthropic.env"
    if secrets_file.exists():
        for line in secrets_file.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                ANTHROPIC_API_KEY = line.split("=", 1)[1].strip().strip('"')

if not ANTHROPIC_API_KEY and not OPENAI_API_KEY:
    # Try reading from .env file
    env_file = Path.home() / ".openclaw" / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                ANTHROPIC_API_KEY = line.split("=", 1)[1].strip().strip('"')
            elif line.startswith("OPENAI_API_KEY="):
                OPENAI_API_KEY = line.split("=", 1)[1].strip()
                break

# Bot C Config — same pools as v2
CONFIG = {
    "15m": {
        "pool_size": 25.0,
        "trade_size": 2.0,
        "min_bias": 0.58,
        "max_price": 0.85,
        "take_profit": 0.50,
        "stop_loss": 0.25,
        "prefer_cheap": True,
        "strategies": ["ai"],  # Only AI strategy
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
        "strategies": ["ai"],
        "active_strategy": 0,
    },
    "iterate_every": 10,
    "auto_reset_on_empty": True,
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
                "strategy": "ai", "generation": 1},
        "1h": {"balance": 25.0, "trades": [], "wins": 0, "losses": 0, "exits_profit": 0, "exits_loss": 0,
                "strategy": "ai", "generation": 1},
        "total_trades": 0,
        "total_resets": 0,
        "version": "bot_c_ai",
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


# ==================== TECHNICAL INDICATORS (reused from Bot B) ====================

def fetch_binance_candles(interval: str, limit: int) -> list:
    """Fetch BTC/USDT candles from Binance."""
    try:
        url = f"{BINANCE_API}?symbol=BTCUSDT&interval={interval}&limit={limit}"
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data
    except Exception as e:
        return []


def calculate_rsi(prices: list, period: int = 14) -> float:
    """Calculate RSI from price list (pure Python)."""
    if len(prices) < period + 1:
        return 50.0
    
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
        return sum(prices) / len(prices)
    
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
    
    signal_line = macd_line * 0.9
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
    candles_1m = fetch_binance_candles("1m", 100)
    candles_5m = fetch_binance_candles("5m", 50)
    
    if not candles_1m:
        return None
    
    closes_1m = [float(c[4]) for c in candles_1m]
    closes_5m = [float(c[4]) for c in candles_5m] if candles_5m else []
    
    current_price = closes_1m[-1] if closes_1m else 0
    
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


# ==================== AI DECISION MAKING ====================

def get_recent_trades(state: dict, timeframe: str, limit: int = 5) -> list:
    """Get last N closed trades for context."""
    tf_state = state[timeframe]
    closed = [t for t in tf_state["trades"] if t.get("status") == "closed"]
    return closed[-limit:] if closed else []


def call_anthropic_api(prompt: str, retry: bool = True) -> dict | None:
    """Call Anthropic Claude API for trading decisions."""
    if not ANTHROPIC_API_KEY:
        return None
    
    payload = {
        "model": AI_MODEL,
        "max_tokens": 300,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "system": "You are a BTC short-term trading assistant. Respond ONLY with valid JSON, no markdown.",
    }
    
    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
    }
    
    try:
        req = Request(
            ANTHROPIC_API,
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
            method='POST'
        )
        with urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            content = result.get("content", [{}])[0].get("text", "")
            return _parse_ai_response(content)
    except Exception as e:
        log(f"⚠️ Anthropic API error: {e}")
        if retry:
            time.sleep(1)
            return call_anthropic_api(prompt, retry=False)
    return None


def call_openai_api(prompt: str, retry: bool = True) -> dict | None:
    """Call OpenAI API as fallback."""
    if not OPENAI_API_KEY:
        return None
    
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You are a BTC short-term trading assistant. Respond only with valid JSON."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 300,
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}",
    }
    
    try:
        req = Request(
            OPENAI_API,
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
            method='POST'
        )
        with urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            return _parse_ai_response(content)
    except Exception as e:
        log(f"⚠️ OpenAI API error: {e}")
        if retry:
            time.sleep(1)
            return call_openai_api(prompt, retry=False)
    return None


def _parse_ai_response(content: str) -> dict | None:
    """Parse JSON from AI response, handling markdown wrapping."""
    try:
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content.strip())
    except json.JSONDecodeError:
        log(f"⚠️ Failed to parse AI response: {content[:100]}")
        return None


def call_ai(prompt: str) -> dict | None:
    """Call AI — use OpenAI (gpt-4o-mini) by default."""
    result = call_openai_api(prompt)
    if result:
        return result
    # Fallback to Anthropic if OpenAI fails
    return call_anthropic_api(prompt)


def decide_trade_with_ai(market: dict, timeframe: str, state: dict, indicators: dict, btc_context: dict) -> dict | None:
    """Use AI to decide whether to trade.
    
    Gathers all context, builds prompt, calls OpenAI, parses response.
    """
    cfg = CONFIG[timeframe]
    tf_state = state[timeframe]
    
    dominant_side, bias = get_bias(market)
    yes_price = market["yes_price"]
    no_price = market["no_price"]
    
    # Check minimum bias
    # Bot C: very low bias filter — let the AI decide, not hard rules
    if bias < 0.51:  # Only skip true 50/50 coinflips
        return None
    
    # Get recent trades
    recent_trades = get_recent_trades(state, timeframe, 5)
    trade_summary = f"{tf_state['wins']}W-{tf_state['losses']}L"
    if recent_trades:
        last_result = recent_trades[-1].get("result", "?")
        last_side = recent_trades[-1].get("side", "?")
        trade_summary += f", last: {last_side} {last_result}"
    
    # Build the prompt
    prompt = f"""You are a BTC short-term trading assistant. Decide whether to trade this Polymarket market.

MARKET: {market['question']}
Timeframe: {timeframe}
YES price: ${yes_price:.2f} (market thinks {yes_price*100:.0f}% chance UP)
NO price: ${no_price:.2f}
Bias: {dominant_side} at {bias*100:.0f}%

BTC PRICE: ${btc_context.get('current_price', 0):,.0f}
- 1min: {btc_context.get('change_1min_pct', 0):+.2f}%
- 5min: {btc_context.get('change_5min_pct', 0):+.2f}%
- 15min: {btc_context.get('change_15min_pct', 0):+.2f}%
- 1h: {btc_context.get('change_1h_pct', 0):+.2f}%

TECHNICAL INDICATORS:
- RSI(14): {indicators.get('rsi', 50):.1f} {'(oversold)' if indicators.get('rsi', 50) < 30 else '(overbought)' if indicators.get('rsi', 50) > 70 else ''}
- EMA: {indicators.get('ema_cross', 'neutral')} (9={indicators.get('ema9', 0):.0f}, 21={indicators.get('ema21', 0):.0f})
- MACD: {indicators.get('macd_trend', 'neutral')} (line={indicators.get('macd', {}).get('macd', 0):.1f}, signal={indicators.get('macd', {}).get('signal', 0):.1f})
- Bollinger: price is {indicators.get('price_vs_bollinger', 'middle')} (L={indicators.get('bollinger', {}).get('lower', 0):.0f}, M={indicators.get('bollinger', {}).get('middle', 0):.0f}, U={indicators.get('bollinger', {}).get('upper', 0):.0f})

RECENT TRADES: {trade_summary}

DECISION GUIDELINES:
- You MUST trade. Your default is BUY. Only SKIP if price is near 50/50 with no clear signal.
- CRITICAL: Always buy the CHEAPER side (price < 45¢). Better risk/reward beats higher "conviction".
- DO NOT bet against momentum just because RSI is "overbought". RSI >70 often means strong trend, not reversal.
- Follow the trend: EMA bullish + MACD bullish + BTC rising = buy YES (or cheap NO if YES too expensive)
- Only go contrarian if bias is EXTREME (>85%) AND you're buying the cheap side (<20¢)
- Risk/reward matters more than win rate. A 40¢ entry with 60% chance beats 70¢ entry with 80% chance.
- ALWAYS explain your reasoning

Respond ONLY with valid JSON (no markdown):
{{"action": "BUY" or "SKIP", "side": "YES" or "NO", "confidence": 0.0-1.0, "reasoning": "brief explanation"}}
"""
    
    # Call AI
    ai_response = call_ai(prompt)
    
    if not ai_response:
        log("⚠️ AI call failed, SKIP")
        return None
    
    action = ai_response.get("action", "SKIP")
    side = ai_response.get("side", "YES")
    confidence = ai_response.get("confidence", 0.5)
    reasoning = ai_response.get("reasoning", "No reasoning provided")
    
    if action != "BUY":
        log(f"🤖 AI says SKIP: {reasoning}")
        return None
    
    # Validate side
    if side not in ["YES", "NO"]:
        log(f"⚠️ Invalid AI side: {side}, defaulting to {dominant_side}")
        side = dominant_side
    
    price = yes_price if side == "YES" else no_price
    
    # Price check
    if price > cfg["max_price"]:
        log(f"⚠️ AI picked {side} but price ${price:.2f} too high, SKIP")
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
        "reason": f"AI: {reasoning[:100]}",
        "size": trade_size,
        "payout_ratio": round(payout_ratio, 2),
        "price_bucket": price_bucket,
        "bias": round(bias, 3),
        "confidence": round(confidence, 2),
        "market_state": {
            "yes": round(yes_price, 3),
            "no": round(no_price, 3),
            "dominant": dominant_side,
        },
        "indicators": indicators,
        "btc_context": btc_context,
        "ai_prompt": prompt,
        "ai_response": ai_response,
    }


# ==================== TRADE MANAGEMENT ====================

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
        "confidence": decision.get("confidence", 0.5),
        "payout_ratio": decision.get("payout_ratio", 0),
        "price_bucket": decision.get("price_bucket", classify_price(price)),
        "bias": decision.get("bias", 0),
        "market_state": decision.get("market_state", {}),
        "indicators": decision.get("indicators"),
        "btc_context": decision.get("btc_context"),
        "ai_prompt": decision.get("ai_prompt", ""),
        "ai_response": decision.get("ai_response", {}),
        "status": "open",
        "result": None,
        "pnl": None,
        "close_reason": None,
        "strategy": tf_state.get("strategy", "ai"),
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
                strategy = tf_state.get("strategy", "ai")
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

                tf_state["balance"] = cfg["pool_size"]
                tf_state["trades"] = []
                tf_state["wins"] = 0
                tf_state["losses"] = 0
                tf_state["exits_profit"] = 0
                tf_state["exits_loss"] = 0
                tf_state["strategy"] = "ai"
                tf_state["generation"] = gen + 1
                state["total_resets"] = state.get("total_resets", 0) + 1

                resets.append(f"🔄 BOT C {tf} RESET: Gen {gen} ({strategy}, {wr:.0f}% WR) → Gen {gen+1} (ai)")

    if resets:
        save_state(state)
    return resets


def auto_iterate(state: dict) -> list:
    """Track AI performance."""
    changes = []
    for tf in ["15m", "1h"]:
        tf_state = state[tf]
        cfg = CONFIG[tf]
        total = tf_state["wins"] + tf_state["losses"]

        if total <= 0 or total % CONFIG["iterate_every"] != 0:
            continue
            
        wr = tf_state["wins"] / total
        pnl = tf_state["balance"] - cfg["pool_size"]
        
        changes.append(f"📊 BOT C (AI) {tf}: {tf_state['wins']}W-{tf_state['losses']}L ({wr:.0%}, ${pnl:+.2f})")

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
        log("😴 BOT C: Outside trading hours (6-14 ET), managing existing only")
        state = load_state()
        actions = manage_open_trades(state)
        for a in actions:
            log(f"  {a}")
        save_state(state)
        return
    
    state = load_state()
    log("🔄 BOT C (AI Decision Maker) CYCLE START")

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

    # Step 4: Get context data
    indicators = get_technical_indicators()
    btc_context = load_btc_context()
    
    if not btc_context:
        btc_context = {"current_price": indicators.get("current_price", 0) if indicators else 0}
    
    if indicators:
        log(f"  📊 Indicators: RSI={indicators['rsi']:.1f}, EMA={indicators['ema_cross']}, MACD={indicators['macd_trend']}")
    else:
        log(f"  ⚠️ Could not fetch indicators")

    # Step 5: AI-driven trades
    for tf in ["15m", "1h"]:
        cfg = CONFIG[tf]
        
        # Check if timeframe is disabled via override
        if not cfg.get("enabled", True):
            continue
        if (OVERRIDES.get("pause_1h_all") or OVERRIDES.get("bot_c_pause_1h")) and tf == "1h":
            log(f"  ⏸️ {tf} PAUSED (override)")
            continue
            
        if state[tf]["balance"] < cfg["trade_size"]:
            continue

        market = fetch_market(tf)
        if not market:
            continue

        if has_open_trade(state, tf, market["slug"]):
            continue

        if not indicators:
            log(f"  ⏭️ {tf}: No indicators, SKIP")
            continue

        decision = decide_trade_with_ai(market, tf, state, indicators, btc_context)
        if decision:
            trade = execute_trade(state, tf, market, decision)
            if trade:
                conf = decision.get('confidence', 0)
                log(f"  🤖 {tf}: {trade['side']} @ {trade['price']:.3f} (${trade['size']:.2f}) | Confidence={conf:.0%}")
                log(f"      Reasoning: {decision['reason']}")
        else:
            log(f"  ⏭️ {tf}: AI says SKIP or no edge")

    # Status
    total_pnl = (state["15m"]["balance"] - 25) + (state["1h"]["balance"] - 25)
    total_w = state["15m"]["wins"] + state["1h"]["wins"]
    total_l = state["15m"]["losses"] + state["1h"]["losses"]
    log(f"\n💰 BOT C Balance: 15m=${state['15m']['balance']:.2f} | 1h=${state['1h']['balance']:.2f}")
    log(f"📊 BOT C Record: {total_w}W-{total_l}L | P&L=${total_pnl:+.2f}")
    log("🔄 BOT C CYCLE COMPLETE")


def cmd_report(args):
    state = load_state()
    total_pnl = (state["15m"]["balance"] - 25) + (state["1h"]["balance"] - 25)
    total_w = state["15m"]["wins"] + state["1h"]["wins"]
    total_l = state["15m"]["losses"] + state["1h"]["losses"]
    total = total_w + total_l
    wr = (total_w / total * 100) if total > 0 else 0

    print(f"📊 BOT C (AI Decision Maker) REPORT")
    print(f"Record: {total_w}W-{total_l}L ({wr:.0f}% WR) | P&L: ${total_pnl:+.2f}")
    print(f"Resets: {state.get('total_resets', 0)}")
    print()
    for tf in ["15m", "1h"]:
        s = state[tf]
        t = s['wins'] + s['losses']
        tfwr = (s['wins'] / t * 100) if t > 0 else 0
        print(f"{tf} Gen{s.get('generation',1)} (ai): {s['wins']}W-{s['losses']}L ({tfwr:.0f}%) | ${s['balance']:.2f}")
        
        # Show last 3 trades with AI reasoning
        for tr in s["trades"][-3:]:
            pnl = tr.get("pnl")
            p = f"${pnl:+.2f}" if pnl is not None else "open"
            reason = tr.get("reason", "")[:50]
            conf = tr.get("confidence", 0)
            print(f"  {tr['side']} @ {tr['price']:.0%} → {p} | conf={conf:.0%} | {reason}")


def cmd_reset(args):
    state = new_state()
    save_state(state)
    print("✅ BOT C reset. Both pools at $25.")


def cmd_iterate(args):
    state = load_state()
    changes = auto_iterate(state)
    for c in changes:
        log(c)
    if not changes:
        log("BOT C: No changes needed.")


def main():
    parser = argparse.ArgumentParser(description="Bot C: AI Decision Maker")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("cycle", help="Full trading cycle").set_defaults(func=cmd_cycle)
    subparsers.add_parser("report", help="Generate report").set_defaults(func=cmd_report)
    subparsers.add_parser("reset", help="Reset pools").set_defaults(func=cmd_reset)
    subparsers.add_parser("iterate", help="Analyze and adjust").set_defaults(func=cmd_iterate)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
