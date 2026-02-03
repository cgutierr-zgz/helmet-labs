#!/usr/bin/env python3
"""
Event Scanner - Busca eventos relevantes para Polymarket
Diseñado para correr periódicamente y detectar movimientos.
v2.0 - Fase 2: Data Quality (scoring + deduplicación)
"""

import json
import subprocess
import feedparser
import re
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from difflib import SequenceMatcher

WORKSPACE = Path(__file__).parent
SOURCES = json.loads((WORKSPACE / "sources.json").read_text())
STATE_FILE = WORKSPACE / "scan_state.json"
ALERTS_FILE = WORKSPACE / "alerts.jsonl"

# Keywords que disparan alertas por categoría (más específicos para evitar falsos positivos)
KEYWORDS = {
    "trump_deportations": ["deportation", "deported", "ice raid", "mass deportation", "immigration enforcement"],
    "tariffs": ["tariff", "trade war", "import tax", "trump tariff"],
    "fed": ["fomc", "rate cut", "rate hike", "powell", "federal reserve", "basis points", "fed decision", "interest rate"],
    "russia_ukraine": ["ceasefire", "peace talk", "zelensky", "putin negotiate", "ukraine offensive", "russia attack"],
    "china_taiwan": ["taiwan strait", "china taiwan", "pla exercise", "taiwan invasion", "blockade taiwan"],
    "btc": ["bitcoin price", "btc price", "whale alert", "bitcoin etf", "btc 100k", "btc million"],
    "gta": ["gta 6", "gta vi", "rockstar games", "grand theft auto 6"]
}

# Urgency scoring factors
URGENCY_MULTIPLIERS = {
    "fed": 2.5,  # Fed news are highest priority for markets
    "btc": 2.0,  # Crypto moves fast
    "trump_deportations": 1.8,
    "tariffs": 1.7,
    "russia_ukraine": 1.5,
    "china_taiwan": 1.4,
    "gta": 0.8   # Lower priority
}

URGENCY_KEYWORDS = {
    "breaking": 3.0,
    "urgent": 3.0,
    "alert": 2.5,
    "just in": 2.5,
    "emergency": 3.0,
    "immediate": 2.5,
    "now": 1.5,
    "announced": 2.0,
    "confirms": 1.8,
    "official": 1.5
}

def calculate_urgency_score(alert):
    """
    Calculate urgency score 1-10 based on multiple factors:
    - Category importance
    - Urgency keywords in title
    - Source priority
    - Time sensitivity
    """
    base_score = 5.0  # Default baseline
    
    # Category multiplier
    category = alert.get('category', '')
    category_mult = URGENCY_MULTIPLIERS.get(category, 1.0)
    base_score *= category_mult
    
    # Urgency keywords in headline
    headline = alert.get('headline', '').lower()
    urgency_boost = 0
    for keyword, boost in URGENCY_KEYWORDS.items():
        if keyword in headline:
            urgency_boost = max(urgency_boost, boost)
    
    base_score += urgency_boost
    
    # Source priority (Fed feeds = high priority)
    source_url = alert.get('feed', alert.get('account', ''))
    priority_sources = SOURCES.get('priority_sources', {})
    
    if source_url in priority_sources.get('high', []):
        base_score += 2.0
    elif source_url in priority_sources.get('medium', []):
        base_score += 1.0
    
    # Time decay - newer = more urgent
    if 'timestamp' in alert:
        try:
            alert_time = datetime.fromisoformat(alert['timestamp'])
            age_minutes = (datetime.now() - alert_time).total_seconds() / 60
            if age_minutes < 10:  # Very fresh
                base_score += 1.0
            elif age_minutes < 30:  # Still fresh
                base_score += 0.5
        except:
            pass
    
    # Cap at 10
    return min(10.0, max(1.0, round(base_score, 1)))

def similarity(a, b):
    """Calculate text similarity using SequenceMatcher."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def create_content_hash(text):
    """Create a hash for deduplication based on key content words."""
    # Extract key words (remove common words)
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were'}
    words = [w.lower() for w in re.findall(r'\w+', text) if len(w) > 3 and w.lower() not in stop_words]
    key_content = ' '.join(sorted(words[:10]))  # Sort to normalize order
    return hashlib.md5(key_content.encode()).hexdigest()

def is_duplicate(new_alert, existing_alerts, similarity_threshold=0.75):
    """
    Check if new alert is duplicate of existing ones.
    Uses both content similarity and hash matching.
    """
    new_headline = new_alert.get('headline', '')
    new_hash = create_content_hash(new_headline)
    
    for existing in existing_alerts:
        existing_headline = existing.get('headline', '')
        existing_hash = create_content_hash(existing_headline)
        
        # Hash match = likely duplicate
        if new_hash == existing_hash:
            return True
        
        # High similarity = likely duplicate  
        if similarity(new_headline, existing_headline) > similarity_threshold:
            return True
    
    return False

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"last_scan": None, "seen_ids": []}

def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))

def log_alert(alert):
    with open(ALERTS_FILE, "a") as f:
        f.write(json.dumps(alert) + "\n")
    
    urgency = alert.get('urgency_score', 5)
    urgency_icon = "🔥" if urgency >= 8 else "🚨" if urgency >= 6 else "⚡" if urgency >= 4 else "📢"
    print(f"{urgency_icon} ALERT [{alert['category']}] Score:{urgency}/10 - {alert['headline'][:60]}")

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
                            alert = {
                                "timestamp": datetime.now().isoformat(),
                                "source": "rss",
                                "feed": feed_url,
                                "category": alert_cat,
                                "headline": entry.get("title", ""),
                                "link": entry.get("link", ""),
                                "matched_keywords": [kw for kw in keywords if kw in text],
                                "source_category": category
                            }
                            
                            # Add urgency score
                            alert["urgency_score"] = calculate_urgency_score(alert)
                            alerts.append(alert)
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
                            alert = {
                                "timestamp": datetime.now().isoformat(),
                                "source": "twitter",
                                "account": account,
                                "category": alert_cat,
                                "headline": tweet.get("text", "")[:200],
                                "matched_keywords": [kw for kw in keywords if kw in text],
                                "tweet_id": tweet.get("id", "")
                            }
                            
                            # Add urgency score
                            alert["urgency_score"] = calculate_urgency_score(alert)
                            alerts.append(alert)
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
    
    # Scan Twitter (breaking news accounts + fed specific + bloomberg terminal)
    print("🐦 Scanning Twitter...")
    twitter_categories = ["breaking", "fed_specific", "bloomberg_terminal"]
    for category in twitter_categories:
        accounts = SOURCES.get("twitter_accounts", {}).get(category, [])
        if accounts:
            twitter_alerts = scan_twitter_via_bird(accounts, limit=3)  # Reduce per account
            all_alerts.extend(twitter_alerts)
    
    print(f"   Found {sum(1 for a in all_alerts if a['source'] == 'twitter')} potential alerts from Twitter")
    
    # Enhanced deduplication and filtering
    seen = set(state.get("seen_ids", []))
    recent_alerts = state.get("recent_alerts", [])  # For similarity checking
    new_alerts = []
    
    # Sort by urgency score (highest first)
    all_alerts.sort(key=lambda x: x.get('urgency_score', 5), reverse=True)
    
    for alert in all_alerts:
        # Traditional ID-based deduplication
        alert_id = f"{alert['source']}:{alert.get('link', alert.get('headline', ''))[:50]}"
        if alert_id in seen:
            continue
        
        # Content-based deduplication (check against recent alerts)
        if is_duplicate(alert, recent_alerts):
            print(f"   Skipping duplicate: {alert['headline'][:40]}...")
            continue
        
        # Only log alerts with urgency >= 4
        if alert.get('urgency_score', 5) >= 4.0:
            seen.add(alert_id)
            new_alerts.append(alert)
            recent_alerts.append(alert)
            log_alert(alert)
    
    # Clean up state (keep only recent alerts for dedup checking)
    cutoff_time = datetime.now() - timedelta(hours=6)
    recent_alerts = [
        a for a in recent_alerts[-50:]  # Keep last 50 max
        if datetime.fromisoformat(a.get('timestamp', '')) > cutoff_time
    ]
    
    # Update state
    state["last_scan"] = datetime.now().isoformat()
    state["seen_ids"] = list(seen)[-500:] if len(seen) > 500 else list(seen)  # Keep last 500
    state["recent_alerts"] = recent_alerts
    save_state(state)
    
    print(f"\n✅ Scan complete. {len(new_alerts)} new alerts logged (urgency ≥4).")
    if new_alerts:
        avg_urgency = sum(a.get('urgency_score', 5) for a in new_alerts) / len(new_alerts)
        print(f"   Average urgency score: {avg_urgency:.1f}/10")
    
    return new_alerts

if __name__ == "__main__":
    main()
