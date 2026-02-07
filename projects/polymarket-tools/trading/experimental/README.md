# Experimental Trading Bots

Two experimental bots for finding contrarian trading opportunities.

## 1. News Sentiment Bot 📰

**File:** `news_sentiment_bot.py`

### What it does
- Fetches crypto news from RSS feeds (CoinDesk, CoinTelegraph)
- Simple keyword-based sentiment analysis
- **Contrarian signals**: Extreme sentiment = potential reversal opportunity
  - Very bullish news → potential SHORT signal (top?)
  - Very bearish news → potential LONG signal (bottom?)

### Usage
```bash
python3 news_sentiment_bot.py
```

### Files
- `news_sentiment_state.json` - Bot state (seen articles, last run)
- `news_sentiment_signals.log` - Trading signals log (JSON lines)

### How it works
1. Fetches last 20 articles from each RSS feed
2. Filters for crypto-related content
3. Analyzes sentiment with keyword matching
4. Generates contrarian signals when sentiment is extreme (>60% very positive/negative)

### Customization
- Add more RSS feeds to `FEEDS` dict
- Tune `POSITIVE_KEYWORDS` / `NEGATIVE_KEYWORDS`
- Adjust thresholds in `analyze_sentiment()`

---

## 2. Sports ELO Bot 🏀

**File:** `sports_elo_bot.py`

### What it does
- Calculates ELO ratings for NBA teams from recent game results
- Finds upcoming games where ELO prediction differs from market odds
- **Edge detection**: Compare ELO win probability to Polymarket odds

### Setup
1. Get free API key from https://www.balldontlie.io/
2. Set environment variable:
   ```bash
   export BALLDONTLIE_API_KEY="your_key_here"
   ```
   Or edit `API_KEY` in the script

### Usage
```bash
python3 sports_elo_bot.py
```

**Mock mode** (no API key): Uses sample data for testing

### Files
- `sports_elo_state.json` - ELO ratings and processed games
- `sports_elo_signals.log` - Trading signals log (JSON lines)

### How it works
1. Fetches recent NBA games (last 14 days)
2. Calculates ELO ratings for each team
3. Fetches upcoming games (next 3 days)
4. Calculates ELO-based win probabilities
5. Logs games with strong favorites (>65% or <35% win prob)

### Finding real edges
To find actual trading edges:
1. Get ELO probability from bot
2. Check Polymarket odds for the same game
3. **Edge = |ELO_prob - Market_price| > threshold**
   - Example: ELO says 70% home win, Polymarket at 55% → 15% edge!

### Customization
- Adjust `INITIAL_ELO` (default: 1500)
- Tune `K_FACTOR` (default: 20, higher = more volatile)
- Change edge thresholds in `find_edges()`
- Add home court advantage (+50-100 ELO)

---

## Next Steps

### News Bot
- [ ] Add more news sources (Reddit, Twitter via RSS)
- [ ] Better sentiment analysis (VADER, transformers)
- [ ] Track sentiment over time (trends)
- [ ] Correlate with price action

### Sports Bot
- [ ] Integrate Polymarket API for real-time odds
- [ ] Add home court advantage
- [ ] Consider injuries, rest days
- [ ] Expand to other sports (NFL, soccer)
- [ ] Backtest ELO accuracy vs market

### Integration
- [ ] Run bots on schedule (cron)
- [ ] Alert system (Discord, Telegram)
- [ ] Position sizing based on edge magnitude
- [ ] Track P&L

---

## Notes

Both bots focus on **data fetching first** - getting the pipeline working before optimizing signals.

**Contrarian approach**: Markets overreact to news and sentiment. Extreme readings often mark reversals.

**ELO edge**: Simple rating systems can sometimes spot value before the market adjusts.

Remember: These are **experimental**. Test with paper trading first!
