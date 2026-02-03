"""
Twitter fetcher using bird CLI.
Extracts Twitter scanning functionality from scan.py.
"""
import subprocess
import json
from datetime import datetime
from typing import List
from src.models import Event
from config.settings import SOURCES, KEYWORDS, TWITTER_CATEGORIES_TO_SCAN, TWITTER_TWEETS_PER_ACCOUNT

def scan_twitter_accounts() -> List[Event]:
    """
    Use bird CLI to check Twitter accounts for relevant content.
    
    Returns:
        List of Event objects for detected alerts
    """
    events = []
    
    for category in TWITTER_CATEGORIES_TO_SCAN:
        accounts = SOURCES.get("twitter_accounts", {}).get(category, [])
        if not accounts:
            continue
            
        # Limit accounts to avoid rate limits
        for account in accounts[:5]:
            try:
                result = subprocess.run(
                    ["bird", "user", account, "-n", str(TWITTER_TWEETS_PER_ACCOUNT), "--json"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0:
                    tweets = json.loads(result.stdout)
                    for tweet in tweets:
                        text = tweet.get("text", "").lower()
                        
                        # Check against keywords
                        for alert_cat, keywords in KEYWORDS.items():
                            if any(kw in text for kw in keywords):
                                event = Event(
                                    timestamp=datetime.now().isoformat(),
                                    source="twitter",
                                    account=account,
                                    category=alert_cat,
                                    headline=tweet.get("text", "")[:200],  # Truncate long tweets
                                    matched_keywords=[kw for kw in keywords if kw in text],
                                    tweet_id=tweet.get("id", "")
                                )
                                events.append(event)
                                break  # Only match first category
                                
            except Exception as e:
                print(f"Twitter error (@{account}): {e}")
    
    return events