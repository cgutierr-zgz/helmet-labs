# Bot B & Bot C - Implementation Summary

## Overview
Two new trading bots built to trade the same Polymarket BTC markets as auto_trader_v2, but with different decision-making approaches.

## Bot B: Technical Indicators Bot 
**File:** `bot_b_technical.py`  
**State:** `state_bot_b.json`

### Features
- Fetches BTC candle data from Binance REST API (1-min and 5-min intervals)
- Calculates technical indicators (pure Python, no dependencies):
  - **RSI(14)** - Relative Strength Index on 1-min candles
  - **EMA(9) and EMA(21)** - Exponential Moving Averages
  - **MACD(12,26,9)** - Moving Average Convergence Divergence
  - **Bollinger Bands(20,2)** - Price volatility bands
  
### Trading Logic
Uses indicators to CONFIRM or VETO trades:
- **Momentum YES + RSI <30** → SKIP (oversold, reversal likely)
- **Momentum YES + EMA bullish + MACD bullish** → STRONG BUY
- **Momentum NO + RSI >70** → STRONG BUY (overbought, down likely)
- **Price below lower Bollinger** → contrarian UP signal

### First Cycle Results (Feb 5, 2026 19:37 GMT+1)
```
✅ Successfully executed
📊 Indicators: RSI=54.1, EMA=bearish, MACD=bearish, BB=middle
🎯 Trades placed:
   - 15m: NO @ $0.695 ($2.00) - Momentum NO (bearish indicators)
   - 1h: NO @ $0.680 ($3.00) - Momentum NO (bearish indicators)
💰 Balance: 15m=$23.00 | 1h=$22.00
📊 Record: 0W-0L | P&L=$-5.00 (in open trades)
```

**Status:** ✅ Working perfectly  
**Indicator logging:** ✅ All indicator values logged with each trade

---

## Bot C: AI Decision Maker
**File:** `bot_c_ai.py`  
**State:** `state_bot_c.json`

### Features
- Gathers comprehensive market context:
  - Polymarket prices + bias
  - BTC price changes (1min, 5min, 15min, 1h) from btc_feed.json
  - Technical indicators (RSI, EMA, MACD, Bollinger) - reused from Bot B
  - Recent trade history (last 5 trades, outcomes)
  
- Builds a detailed prompt for LLM decision-making
- Calls OpenAI API (gpt-4o-mini) with timeout and retry logic
- Parses JSON response: `{"action": "BUY"/"SKIP", "side": "YES"/"NO", "confidence": 0-1, "reasoning": "..."}`
- Falls back to SKIP if API call fails

### AI Prompt Structure
```
MARKET: [question] + prices + bias
BTC PRICE: current + 1min/5min/15min/1h changes
TECHNICAL INDICATORS: RSI, EMA, MACD, Bollinger analysis
RECENT TRADES: W-L record + last result
DECISION GUIDELINES: alignment rules, contrarian opportunities
```

### First Cycle Results (Feb 5, 2026 19:37 GMT+1)
```
✅ Successfully executed
📊 Indicators: RSI=53.1, EMA=bearish, MACD=bearish
🤖 AI Decision (15m): SKIP
   Reasoning: "Market bias is strongly against an UP move (70%), 
              BTC momentum is neutral, and technical indicators show bearish signals."
🤖 AI Decision (1h): SKIP  
   Reasoning: "Market bias is strongly NO at 78%, and technical indicators 
              (bearish EMA and MACD) do not support a bullish move."
💰 Balance: 15m=$25.00 | 1h=$25.00
📊 Record: 0W-0L | P&L=$0.00
```

**Status:** ✅ Working perfectly  
**AI reasoning logging:** ✅ Full prompt, response, and reasoning logged

---

## Comparison: Bot B vs Bot C

| Aspect | Bot B (Technical) | Bot C (AI) |
|--------|------------------|------------|
| **Approach** | Rule-based indicators | LLM decision-making |
| **First 15m trade** | ✅ Entered NO @ $0.695 | ❌ Skipped (too cautious) |
| **First 1h trade** | ✅ Entered NO @ $0.680 | ❌ Skipped (too cautious) |
| **Reasoning** | Bearish EMA/MACD confirmed momentum | AI analyzed all data, deemed edges insufficient |
| **Risk tolerance** | Medium (follows indicators) | Conservative (needs strong alignment) |

**Key Insight:** Bot C (AI) is more conservative than Bot B. Same market data, but AI required stronger confluence of signals to enter. Bot B followed its programmatic rules and entered bearish positions based on indicator alignment.

---

## Technical Details

### Dependencies
- Python 3 standard library only
- No external packages (numpy/pandas/ta-lib)
- Uses `urllib` for all API calls (Binance, Polymarket, OpenAI)

### Pool Configuration
- Both bots: $25 per timeframe ($50 total)
- 15m: $2.00 trade size
- 1h: $3.00 trade size
- Same TP/SL as auto_trader_v2:
  - 15m: 50% TP, 25% SL
  - 1h: 40% TP, 25% SL

### CLI Commands (identical for both)
```bash
python3 bot_b_technical.py cycle    # Run full cycle
python3 bot_b_technical.py report   # Show performance
python3 bot_b_technical.py iterate  # Analyze & adjust
python3 bot_b_technical.py reset    # Reset pools

python3 bot_c_ai.py cycle           # Run full cycle
python3 bot_c_ai.py report          # Show performance
python3 bot_c_ai.py iterate         # Track AI performance
python3 bot_c_ai.py reset           # Reset pools
```

### State Files
- `state_bot_b.json` - Bot B trades + indicators
- `state_bot_c.json` - Bot C trades + AI prompts/responses
- `analysis_bot_b.json` - Bot B generation history
- `analysis_bot_c.json` - Bot C generation history

---

## Next Steps

1. **Run all three bots in parallel** to compare performance:
   - `auto_trader_v2.py` (original momentum + contrarian + volatility)
   - `bot_b_technical.py` (technical indicators)
   - `bot_c_ai.py` (AI decision-making)

2. **Collect data over 50+ trades** per bot to analyze:
   - Which indicator combinations work best (Bot B)
   - What types of AI reasoning lead to wins (Bot C)
   - Whether AI's conservatism improves win rate vs auto_trader_v2

3. **Monitor API costs** (Bot C):
   - gpt-4o-mini: ~$0.00015 per decision
   - ~$0.30 per 100 trades (very cheap)

4. **Potential improvements**:
   - Bot B: Add more indicators (volume, ATR, Stochastic)
   - Bot C: Fine-tune prompt based on winning patterns
   - Both: Dynamic position sizing based on confidence

---

## Files Created
✅ `/Users/helmet/.openclaw/workspace/trading/bots/bot_b_technical.py` (29KB)  
✅ `/Users/helmet/.openclaw/workspace/trading/bots/bot_c_ai.py` (30KB)  
✅ `/Users/helmet/.openclaw/workspace/trading/bots/state_bot_b.json` (Bot B state with 2 open trades)  
✅ Both bots tested and working

---

**Delivered by:** Subagent `build-bot-bc`  
**Completion time:** ~5 minutes  
**Status:** ✅ Both bots operational and ready for trading
