#!/usr/bin/env python3
"""
News Sentiment Bot - Contrarian crypto sentiment signals
Fetches crypto news from RSS feeds and analyzes sentiment.
Extreme sentiment = potential contrarian opportunity.
"""

import feedparser
import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter

STATE_FILE = Path(__file__).parent / "news_sentiment_state.json"
LOG_FILE = Path(__file__).parent / "news_sentiment_signals.log"

# RSS Feeds
FEEDS = {
    "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "cointelegraph": "https://cointelegraph.com/rss",
}

# Simple sentiment keywords
POSITIVE_KEYWORDS = [
    "bullish", "surge", "rally", "soar", "moon", "breakthrough", "adoption",
    "growth", "profit", "gain", "up", "rise", "positive", "optimistic",
    "boom", "recovery", "milestone", "success", "winning"
]

NEGATIVE_KEYWORDS = [
    "bearish", "crash", "plunge", "tank", "dump", "collapse", "fear",
    "loss", "down", "fall", "negative", "pessimistic", "crisis", "panic",
    "scam", "hack", "exploit", "vulnerability", "regulation", "ban"
]

CRYPTO_KEYWORDS = ["bitcoin", "btc", "ethereum", "eth", "crypto", "cryptocurrency"]


def load_state():
    """Load bot state from file"""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        "last_run": None,
        "seen_articles": [],
        "signals_today": 0
    }


def save_state(state):
    """Save bot state to file"""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def log_signal(signal_type, sentiment_score, summary, articles):
    """Log a trading signal"""
    timestamp = datetime.now().isoformat()
    log_entry = {
        "timestamp": timestamp,
        "signal": signal_type,
        "sentiment_score": sentiment_score,
        "summary": summary,
        "article_count": len(articles),
        "sample_headlines": articles[:3]
    }
    
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(log_entry) + "\n")
    
    print(f"[{timestamp}] SIGNAL: {signal_type} | Score: {sentiment_score:.2f}")
    print(f"  {summary}")
    return log_entry


def analyze_text(text):
    """Simple keyword-based sentiment analysis"""
    text_lower = text.lower()
    
    pos_count = sum(1 for word in POSITIVE_KEYWORDS if word in text_lower)
    neg_count = sum(1 for word in NEGATIVE_KEYWORDS if word in text_lower)
    
    # Normalize by text length (rough approximation)
    total = pos_count + neg_count
    if total == 0:
        return 0
    
    # Score from -1 (very negative) to +1 (very positive)
    return (pos_count - neg_count) / total if total > 0 else 0


def fetch_news():
    """Fetch news from all RSS feeds"""
    articles = []
    
    for source, url in FEEDS.items():
        try:
            print(f"Fetching {source}...")
            feed = feedparser.parse(url)
            
            for entry in feed.entries[:20]:  # Last 20 articles per feed
                # Check if crypto-related
                title = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))
                full_text = f"{title} {summary}"
                
                is_crypto = any(kw in full_text.lower() for kw in CRYPTO_KEYWORDS)
                
                if is_crypto:
                    articles.append({
                        "source": source,
                        "title": title,
                        "summary": summary,
                        "link": entry.get("link", ""),
                        "published": entry.get("published", ""),
                        "sentiment": analyze_text(full_text)
                    })
        
        except Exception as e:
            print(f"Error fetching {source}: {e}")
    
    return articles


def analyze_sentiment(articles, state):
    """Analyze overall sentiment and generate signals"""
    if not articles:
        print("No crypto articles found")
        return None
    
    # Filter out already seen articles (by title)
    seen = set(state.get("seen_articles", []))
    new_articles = [a for a in articles if a["title"] not in seen]
    
    if not new_articles:
        print(f"No new articles (found {len(articles)} total)")
        return None
    
    print(f"Analyzing {len(new_articles)} new articles...")
    
    # Calculate aggregate sentiment
    sentiments = [a["sentiment"] for a in new_articles]
    avg_sentiment = sum(sentiments) / len(sentiments)
    
    # Count extreme sentiments
    very_positive = sum(1 for s in sentiments if s > 0.5)
    very_negative = sum(1 for s in sentiments if s < -0.5)
    
    # Update seen articles (keep last 200)
    state["seen_articles"] = list(seen.union({a["title"] for a in new_articles}))[-200:]
    
    # Generate contrarian signals
    signal = None
    
    # Extreme positive sentiment = contrarian SHORT opportunity
    if avg_sentiment > 0.4 and very_positive > len(new_articles) * 0.6:
        signal = log_signal(
            "CONTRARIAN_SHORT",
            avg_sentiment,
            f"Extreme bullish sentiment detected ({very_positive}/{len(new_articles)} very positive). Potential top?",
            [a["title"] for a in sorted(new_articles, key=lambda x: x["sentiment"], reverse=True)]
        )
    
    # Extreme negative sentiment = contrarian LONG opportunity
    elif avg_sentiment < -0.4 and very_negative > len(new_articles) * 0.6:
        signal = log_signal(
            "CONTRARIAN_LONG",
            avg_sentiment,
            f"Extreme bearish sentiment detected ({very_negative}/{len(new_articles)} very negative). Potential bottom?",
            [a["title"] for a in sorted(new_articles, key=lambda x: x["sentiment"])]
        )
    
    # Moderate sentiment = no clear signal
    else:
        print(f"Sentiment neutral (avg: {avg_sentiment:.2f}, +{very_positive}/-{very_negative})")
    
    return signal


def cycle():
    """Main bot cycle - fetch news and analyze sentiment"""
    print(f"\n{'='*60}")
    print(f"News Sentiment Bot - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    state = load_state()
    
    # Fetch news
    articles = fetch_news()
    print(f"\nFound {len(articles)} crypto-related articles")
    
    # Analyze sentiment
    signal = analyze_sentiment(articles, state)
    
    # Update state
    state["last_run"] = datetime.now().isoformat()
    if signal:
        state["signals_today"] = state.get("signals_today", 0) + 1
    
    save_state(state)
    
    print(f"\nState saved. Signals today: {state.get('signals_today', 0)}")
    return signal


if __name__ == "__main__":
    cycle()
