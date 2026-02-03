"""
RSS feed fetcher with tier system.
Extracts RSS scanning functionality from scan.py and adds tiered fetching.
"""
import feedparser
from datetime import datetime, timedelta
from typing import List, Dict
import json
from pathlib import Path
from src.models import Event
from config.settings import SOURCES, KEYWORDS, STATE_FILE

# Tier intervals in minutes
TIER_INTERVALS = {
    "tier1_breaking": 1,    # Every 1 minute - highest priority
    "tier2_politics": 5,    # Every 5 minutes  
    "tier3_finance": 5,     # Every 5 minutes
}

def load_rss_state() -> Dict:
    """Load RSS fetch state from file."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {"rss_last_fetched": {}}

def save_rss_state(state: Dict) -> None:
    """Save RSS fetch state to file."""
    try:
        # Load existing state
        existing_state = {}
        if STATE_FILE.exists():
            with open(STATE_FILE, 'r') as f:
                existing_state = json.load(f)
        
        # Update RSS portion
        existing_state.update(state)
        
        with open(STATE_FILE, 'w') as f:
            json.dump(existing_state, f, indent=2)
    except Exception as e:
        print(f"Error saving RSS state: {e}")

def should_fetch_tier(tier_name: str, state: Dict) -> bool:
    """Check if enough time has passed to fetch this tier."""
    if tier_name not in TIER_INTERVALS:
        return True  # Unknown tiers always fetch
    
    last_fetched = state.get("rss_last_fetched", {}).get(tier_name)
    if not last_fetched:
        return True  # Never fetched before
    
    try:
        last_time = datetime.fromisoformat(last_fetched)
        interval_minutes = TIER_INTERVALS[tier_name]
        time_diff = datetime.now() - last_time
        return time_diff >= timedelta(minutes=interval_minutes)
    except Exception:
        return True  # Error parsing time, safe to fetch

def scan_rss_feeds() -> List[Event]:
    """
    Scan RSS feeds for relevant news using tier system.
    
    Returns:
        List of Event objects for detected alerts
    """
    events = []
    state = load_rss_state()
    
    # Get RSS feeds with tier structure
    rss_config = SOURCES.get("rss_tiers", SOURCES.get("rss_feeds", {}))
    
    for tier_name, feeds in rss_config.items():
        # Check if it's time to fetch this tier
        if not should_fetch_tier(tier_name, state):
            print(f"Skipping {tier_name} - interval not reached")
            continue
        
        print(f"Fetching {tier_name} ({len(feeds)} feeds)")
        
        for feed_url in feeds:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:10]:  # Limit to recent entries
                    title = entry.get("title", "").lower()
                    summary = entry.get("summary", "").lower()
                    text = f"{title} {summary}"
                    
                    # Check against keywords
                    for alert_cat, keywords in KEYWORDS.items():
                        if any(kw in text for kw in keywords):
                            event = Event(
                                timestamp=datetime.now().isoformat(),
                                source="rss",
                                feed=feed_url,
                                category=alert_cat,
                                headline=entry.get("title", ""),
                                link=entry.get("link", ""),
                                matched_keywords=[kw for kw in keywords if kw in text],
                                source_category=tier_name
                            )
                            events.append(event)
                            break  # Only match first category
                            
            except Exception as e:
                print(f"RSS error ({feed_url}): {e}")
        
        # Update last fetched time for this tier
        if "rss_last_fetched" not in state:
            state["rss_last_fetched"] = {}
        state["rss_last_fetched"][tier_name] = datetime.now().isoformat()
    
    # Save updated state
    save_rss_state(state)
    
    return events

def get_tier_status() -> Dict:
    """Get status of all tiers and when they were last fetched."""
    state = load_rss_state()
    status = {}
    
    for tier_name, interval_minutes in TIER_INTERVALS.items():
        last_fetched = state.get("rss_last_fetched", {}).get(tier_name)
        next_fetch = "Now"
        
        if last_fetched:
            try:
                last_time = datetime.fromisoformat(last_fetched)
                next_time = last_time + timedelta(minutes=interval_minutes)
                if next_time > datetime.now():
                    time_diff = next_time - datetime.now()
                    minutes_left = int(time_diff.total_seconds() / 60)
                    next_fetch = f"{minutes_left}m"
                else:
                    next_fetch = "Now"
            except Exception:
                next_fetch = "Now"
        
        status[tier_name] = {
            "interval_minutes": interval_minutes,
            "last_fetched": last_fetched,
            "next_fetch": next_fetch,
            "should_fetch": should_fetch_tier(tier_name, state)
        }
    
    return status