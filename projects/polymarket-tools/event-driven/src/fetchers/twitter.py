"""
Twitter fetcher with tier system and rate limiting.
Extracts Twitter scanning functionality from scan.py and adds tiered fetching.
"""
import subprocess
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict
from pathlib import Path
from src.models import Event
from config.settings import SOURCES, KEYWORDS, STATE_FILE

# Tier intervals in minutes (per PRD.md requirements)
TWITTER_TIER_INTERVALS = {
    "critical": 1,      # Every 1 minute - highest priority (BNONews, disclosetv, etc.)
    "politics": 5,      # Every 5 minutes (Trump, WhiteHouse, etc.)
    "crypto": 5,        # Every 5 minutes (whale_alert, DocumentingBTC, etc.)
    "geopolitics": 10,  # Every 10 minutes (TheStudyofWar, sentdefender, etc.)
}

# Rate limiting: Maximum requests per minute to avoid Twitter limits
MAX_REQUESTS_PER_MINUTE = 20
REQUESTS_WINDOW = 60  # seconds

# Request tracking for rate limiting
_request_times = []

def load_twitter_state() -> Dict:
    """Load Twitter fetch state from file."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {"twitter_last_fetched": {}}

def save_twitter_state(state: Dict) -> None:
    """Save Twitter fetch state to file."""
    try:
        # Load existing state
        existing_state = {}
        if STATE_FILE.exists():
            with open(STATE_FILE, 'r') as f:
                existing_state = json.load(f)
        
        # Update Twitter portion
        existing_state.update(state)
        
        with open(STATE_FILE, 'w') as f:
            json.dump(existing_state, f, indent=2)
    except Exception as e:
        print(f"Error saving Twitter state: {e}")

def should_fetch_tier(tier_name: str, state: Dict) -> bool:
    """Check if enough time has passed to fetch this tier."""
    if tier_name not in TWITTER_TIER_INTERVALS:
        return True  # Unknown tiers always fetch
    
    last_fetched = state.get("twitter_last_fetched", {}).get(tier_name)
    if not last_fetched:
        return True  # Never fetched before
    
    try:
        last_time = datetime.fromisoformat(last_fetched)
        interval_minutes = TWITTER_TIER_INTERVALS[tier_name]
        time_diff = datetime.now() - last_time
        return time_diff >= timedelta(minutes=interval_minutes)
    except Exception:
        return True  # Error parsing time, safe to fetch

def can_make_request() -> bool:
    """Check if we can make a request without exceeding rate limits."""
    global _request_times
    now = time.time()
    
    # Remove requests older than the window
    _request_times = [t for t in _request_times if now - t <= REQUESTS_WINDOW]
    
    # Check if we can make another request
    if len(_request_times) >= MAX_REQUESTS_PER_MINUTE:
        return False
    
    return True

def record_request() -> None:
    """Record that we made a request for rate limiting purposes."""
    global _request_times
    _request_times.append(time.time())

def fetch_user_tweets(username: str, count: int = 5, tier: str = "default") -> List[Dict]:
    """
    Fetch tweets from a user using bird CLI with error handling and rate limiting.
    
    Args:
        username: Twitter username (without @)
        count: Number of tweets to fetch
        tier: Tier name for logging
        
    Returns:
        List of tweet dictionaries, empty list on error
    """
    if not can_make_request():
        print(f"Rate limit reached, skipping @{username} (tier: {tier})")
        return []
    
    try:
        record_request()
        
        result = subprocess.run(
            ["bird", "user-tweets", username, "-n", str(count), "--json"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            tweets = json.loads(result.stdout)
            print(f"✓ Fetched {len(tweets)} tweets from @{username} ({tier})")
            return tweets if isinstance(tweets, list) else []
        else:
            print(f"✗ bird CLI error for @{username}: {result.stderr}")
            return []
            
    except subprocess.TimeoutExpired:
        print(f"✗ Timeout fetching @{username} ({tier})")
        return []
    except json.JSONDecodeError:
        print(f"✗ Invalid JSON from @{username} ({tier})")
        return []
    except FileNotFoundError:
        print("✗ bird CLI not found. Install with: pip install bird-api")
        return []
    except Exception as e:
        print(f"✗ Unexpected error fetching @{username} ({tier}): {e}")
        return []

def scan_twitter_accounts() -> List[Event]:
    """
    Scan Twitter accounts for relevant content using tier system.
    
    Returns:
        List of Event objects for detected alerts
    """
    events = []
    state = load_twitter_state()
    
    # Get Twitter config with tier structure
    twitter_config = SOURCES.get("twitter_tiers", SOURCES.get("twitter_accounts", {}))
    
    for tier_name, accounts in twitter_config.items():
        # Check if it's time to fetch this tier
        if not should_fetch_tier(tier_name, state):
            print(f"Skipping {tier_name} - interval not reached")
            continue
        
        print(f"Fetching {tier_name} ({len(accounts)} accounts)")
        
        # Determine tweets per account based on tier priority
        tweets_per_account = 10 if tier_name == "critical" else 5
        
        for username in accounts:
            tweets = fetch_user_tweets(username, tweets_per_account, tier_name)
            
            for tweet in tweets:
                try:
                    text = tweet.get("text", "").lower()
                    
                    # Check against keywords
                    for alert_cat, keywords in KEYWORDS.items():
                        if any(kw in text for kw in keywords):
                            event = Event(
                                timestamp=datetime.now().isoformat(),
                                source="twitter",
                                account=username,
                                category=alert_cat,
                                headline=tweet.get("text", "")[:200],  # Truncate long tweets
                                matched_keywords=[kw for kw in keywords if kw in text],
                                tweet_id=tweet.get("id", ""),
                                source_category=tier_name
                            )
                            events.append(event)
                            break  # Only match first category
                            
                except Exception as e:
                    print(f"Error processing tweet from @{username}: {e}")
        
        # Update last fetched time for this tier
        if "twitter_last_fetched" not in state:
            state["twitter_last_fetched"] = {}
        state["twitter_last_fetched"][tier_name] = datetime.now().isoformat()
    
    # Save updated state
    save_twitter_state(state)
    
    return events

def get_tier_status() -> Dict:
    """Get status of all Twitter tiers and when they were last fetched."""
    state = load_twitter_state()
    status = {}
    
    for tier_name, interval_minutes in TWITTER_TIER_INTERVALS.items():
        last_fetched = state.get("twitter_last_fetched", {}).get(tier_name)
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

def get_rate_limit_status() -> Dict:
    """Get current rate limiting status."""
    global _request_times
    now = time.time()
    
    # Clean old requests
    _request_times = [t for t in _request_times if now - t <= REQUESTS_WINDOW]
    
    return {
        "requests_in_window": len(_request_times),
        "max_requests": MAX_REQUESTS_PER_MINUTE,
        "window_seconds": REQUESTS_WINDOW,
        "can_make_request": can_make_request(),
        "next_window_reset": max(0, int(REQUESTS_WINDOW - (now - min(_request_times)) if _request_times else 0))
    }