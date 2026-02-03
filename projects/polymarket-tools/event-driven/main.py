#!/usr/bin/env python3
"""
Event Scanner - Main orchestrator for the modular system.
Refactored from monolithic scan.py.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

from src.fetchers.rss import scan_rss_feeds
from src.fetchers.twitter import scan_twitter_accounts
from src.processors.scorer import calculate_urgency_score
from src.processors.dedup import is_duplicate, generate_alert_id
from src.models import Event, ScanState
from config.settings import (
    STATE_FILE, ALERTS_FILE, MIN_URGENCY_THRESHOLD,
    STATE_RETENTION_HOURS, MAX_SEEN_IDS, MAX_RECENT_ALERTS
)

def load_state() -> ScanState:
    """Load scan state from file."""
    if STATE_FILE.exists():
        data = json.loads(STATE_FILE.read_text())
        return ScanState.from_dict(data)
    return ScanState(last_scan=None, seen_ids=[], recent_alerts=[])

def save_state(state: ScanState) -> None:
    """Save scan state to file."""
    STATE_FILE.write_text(json.dumps(state.to_dict(), indent=2))

def log_alert(event: Event) -> None:
    """Log alert to JSONL file and console."""
    with open(ALERTS_FILE, "a") as f:
        f.write(json.dumps(event.to_dict()) + "\n")
    
    urgency = event.urgency_score
    urgency_icon = "🔥" if urgency >= 8 else "🚨" if urgency >= 6 else "⚡" if urgency >= 4 else "📢"
    print(f"{urgency_icon} ALERT [{event.category}] Score:{urgency}/10 - {event.headline[:60]}")

def clean_state(state: ScanState) -> ScanState:
    """Clean up state by removing old data."""
    # Clean up recent alerts (keep only recent ones)
    cutoff_time = datetime.now() - timedelta(hours=STATE_RETENTION_HOURS)
    recent_alerts = []
    
    for alert_data in state.recent_alerts[-MAX_RECENT_ALERTS:]:
        try:
            alert_time = datetime.fromisoformat(alert_data.get('timestamp', ''))
            if alert_time > cutoff_time:
                recent_alerts.append(alert_data)
        except Exception:
            continue  # Skip invalid timestamps
    
    # Limit seen IDs
    seen_ids = state.seen_ids[-MAX_SEEN_IDS:] if len(state.seen_ids) > MAX_SEEN_IDS else state.seen_ids
    
    return ScanState(
        last_scan=state.last_scan,
        seen_ids=seen_ids,
        recent_alerts=recent_alerts
    )

def main():
    """Main event scanning orchestrator."""
    print(f"🔍 Event scan started at {datetime.now().isoformat()}")
    
    # Load state
    state = load_state()
    all_events = []
    
    # Fetch from all sources
    print("📰 Scanning RSS feeds...")
    rss_events = scan_rss_feeds()
    all_events.extend(rss_events)
    print(f"   Found {len(rss_events)} potential events from RSS")
    
    print("🐦 Scanning Twitter...")
    twitter_events = scan_twitter_accounts()
    all_events.extend(twitter_events)
    print(f"   Found {len(twitter_events)} potential events from Twitter")
    
    # Process events
    seen = set(state.seen_ids)
    new_events = []
    
    # Sort by urgency score (highest first) after calculating scores
    for event in all_events:
        event.urgency_score = calculate_urgency_score(event)
    
    all_events.sort(key=lambda x: x.urgency_score, reverse=True)
    
    for event in all_events:
        # Traditional ID-based deduplication
        event_id = generate_alert_id(event)
        if event_id in seen:
            continue
        
        # Content-based deduplication
        if is_duplicate(event, state.recent_alerts):
            print(f"   Skipping duplicate: {event.headline[:40]}...")
            continue
        
        # Only process events with urgency >= threshold
        if event.urgency_score >= MIN_URGENCY_THRESHOLD:
            seen.add(event_id)
            new_events.append(event)
            state.recent_alerts.append(event.to_dict())
            log_alert(event)
    
    # Clean up and update state
    state.seen_ids = list(seen)
    state.last_scan = datetime.now().isoformat()
    state = clean_state(state)
    save_state(state)
    
    print(f"\n✅ Scan complete. {len(new_events)} new alerts logged (urgency ≥{MIN_URGENCY_THRESHOLD}).")
    if new_events:
        avg_urgency = sum(e.urgency_score for e in new_events) / len(new_events)
        print(f"   Average urgency score: {avg_urgency:.1f}/10")
    
    return new_events

if __name__ == "__main__":
    main()