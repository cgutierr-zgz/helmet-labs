"""
RSS feed fetcher.
Extracts RSS scanning functionality from scan.py.
"""
import feedparser
from datetime import datetime
from typing import List
from src.models import Event
from config.settings import SOURCES, KEYWORDS

def scan_rss_feeds() -> List[Event]:
    """
    Scan RSS feeds for relevant news.
    
    Returns:
        List of Event objects for detected alerts
    """
    events = []
    
    for category, feeds in SOURCES.get("rss_feeds", {}).items():
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
                                source_category=category
                            )
                            events.append(event)
                            break  # Only match first category
                            
            except Exception as e:
                print(f"RSS error ({feed_url}): {e}")
    
    return events