#!/usr/bin/env python3
"""
Event Scanner - Busca eventos relevantes para Polymarket
Diseñado para correr periódicamente y detectar movimientos.
"""

import json
import subprocess
import feedparser
import re
from datetime import datetime, timedelta
from pathlib import Path

WORKSPACE = Path(__file__).parent
SOURCES = json.loads((WORKSPACE / "sources.json").read_text())
STATE_FILE = WORKSPACE / "scan_state.json"
ALERTS_FILE = WORKSPACE / "alerts.jsonl"

# Keywords que disparan alertas por categoría (más específicos para evitar falsos positivos)
KEYWORDS = {
    "trump_deportations": ["deportation", "deported", "ice raid", "mass deportation", "immigration enforcement"],
    "tariffs": ["tariff", "trade war", "import tax", "trump tariff"],
    "fed": ["fomc", "rate cut", "rate hike", "powell", "federal reserve", "basis points", "fed decision"],
    "russia_ukraine": ["ceasefire", "peace talk", "zelensky", "putin negotiate", "ukraine offensive", "russia attack"],
    "china_taiwan": ["taiwan strait", "china taiwan", "pla exercise", "taiwan invasion", "blockade taiwan"],
    "btc": ["bitcoin price", "btc price", "whale alert", "bitcoin etf", "btc 100k", "btc million"],
    "gta": ["gta 6", "gta vi", "rockstar games", "grand theft auto 6"]
}

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"last_scan": None, "seen_ids": []}

def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))

def log_alert(alert):
    with open(ALERTS_FILE, "a") as f:
        f.write(json.dumps(alert) + "\n")
    print(f"🚨 ALERT: [{alert['category']}] {alert['headline'][:60]}")

def scan_rss():
    """Scan RSS feeds for relevant news."""
    alerts = []
    
    for category, feeds in SOURCES.get("rss_feeds", {}).items():
        for feed_url in feeds:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:10]:
                    title = entry.get("title", "").lower()
                    summary = entry.get("summary", "").lower()
                    text = f"{title} {summary}"
                    
                    # Check against keywords
                    for alert_cat, keywords in KEYWORDS.items():
                        if any(kw in text for kw in keywords):
                            alerts.append({
                                "timestamp": datetime.now().isoformat(),
                                "source": "rss",
                                "feed": feed_url,
                                "category": alert_cat,
                                "headline": entry.get("title", ""),
                                "link": entry.get("link", ""),
                                "matched_keywords": [kw for kw in keywords if kw in text]
                            })
                            break
            except Exception as e:
                print(f"RSS error ({feed_url}): {e}")
    
    return alerts

def scan_twitter_via_bird(accounts, limit=5):
    """Use bird CLI to check Twitter accounts."""
    alerts = []
    
    for account in accounts[:5]:  # Limit to avoid rate limits
        try:
            result = subprocess.run(
                ["bird", "user", account, "-n", str(limit), "--json"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                tweets = json.loads(result.stdout)
                for tweet in tweets:
                    text = tweet.get("text", "").lower()
                    
                    for alert_cat, keywords in KEYWORDS.items():
                        if any(kw in text for kw in keywords):
                            alerts.append({
                                "timestamp": datetime.now().isoformat(),
                                "source": "twitter",
                                "account": account,
                                "category": alert_cat,
                                "headline": tweet.get("text", "")[:200],
                                "matched_keywords": [kw for kw in keywords if kw in text]
                            })
                            break
        except Exception as e:
            print(f"Twitter error (@{account}): {e}")
    
    return alerts

def main():
    print(f"🔍 Event scan started at {datetime.now().isoformat()}")
    
    state = load_state()
    all_alerts = []
    
    # Scan RSS
    print("📰 Scanning RSS feeds...")
    rss_alerts = scan_rss()
    all_alerts.extend(rss_alerts)
    print(f"   Found {len(rss_alerts)} potential alerts from RSS")
    
    # Scan Twitter (breaking news accounts)
    print("🐦 Scanning Twitter...")
    twitter_accounts = SOURCES.get("twitter_accounts", {}).get("breaking", [])
    twitter_alerts = scan_twitter_via_bird(twitter_accounts)
    all_alerts.extend(twitter_alerts)
    print(f"   Found {len(twitter_alerts)} potential alerts from Twitter")
    
    # Dedupe and log new alerts
    seen = set(state.get("seen_ids", []))
    new_alerts = []
    
    for alert in all_alerts:
        alert_id = f"{alert['source']}:{alert.get('link', alert.get('headline', ''))[:50]}"
        if alert_id not in seen:
            seen.add(alert_id)
            new_alerts.append(alert)
            log_alert(alert)
    
    # Update state
    state["last_scan"] = datetime.now().isoformat()
    state["seen_ids"] = list(seen)[-500:] if len(seen) > 500 else list(seen)  # Keep last 500
    save_state(state)
    
    print(f"\n✅ Scan complete. {len(new_alerts)} new alerts logged.")
    return new_alerts

if __name__ == "__main__":
    main()
