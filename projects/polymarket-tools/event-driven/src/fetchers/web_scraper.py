#!/usr/bin/env python3
"""
Web Scraper Fetcher - Reads events from the OpenClaw web-scraper skill.

The web scraper skill monitors various government/regulatory websites and
generates events in a JSON file. This fetcher reads those events,
converts them to the trading bot's Event format, and tracks which ones
have already been processed to avoid duplicates.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import logging

from src.models import Event

logger = logging.getLogger(__name__)

# Path to the web scraper skill's output
SCRAPER_EVENTS_PATH = Path.home() / ".openclaw/workspace/skills/web-scraper/data/scraped_events.json"

# Path to track processed event IDs (relative to event-driven project)
PROCESSED_IDS_PATH = Path(__file__).parent.parent.parent / "data/processed_scraper_ids.json"

# Category mapping from web scraper to trading bot categories
CATEGORY_MAP = {
    "monetary": "fed",
    "corporate": "finance",
    "regulatory": "finance",
    "government": "politics",
    "sanctions": "geopolitics",
}

# Source tier mapping based on web scraper source
SOURCE_TIER_MAP = {
    "fed_all_releases": "tier1_breaking",
    "fed_monetary_policy": "tier1_breaking",
    "sec_8k_filings": "tier2_politics",
    "fda_press_announcements": "tier2_politics",
    "whitehouse_briefings": "tier2_politics",
    "treasury_press_releases": "tier2_politics",
    "ofac_recent_actions": "tier1_breaking",  # Sanctions are market-moving
}


class WebScraperFetcher:
    """
    Fetcher that reads events from the web scraper skill.
    
    The web scraper monitors government/regulatory websites like:
    - Federal Reserve (monetary policy, FOMC statements)
    - SEC (8-K filings, corporate events)
    - FDA (drug approvals, regulatory actions)
    - Treasury/OFAC (sanctions, policy changes)
    - White House (briefings, executive actions)
    
    Events are pre-categorized by the scraper and arrive with priority
    indicators which we preserve and enhance.
    """
    
    def __init__(self, events_path: Optional[Path] = None, processed_ids_path: Optional[Path] = None):
        """
        Initialize the fetcher.
        
        Args:
            events_path: Override path to scraped events file
            processed_ids_path: Override path to processed IDs tracking file
        """
        self.events_path = events_path or SCRAPER_EVENTS_PATH
        self.processed_ids_path = processed_ids_path or PROCESSED_IDS_PATH
        self.processed_ids = self._load_processed_ids()
    
    def _load_processed_ids(self) -> set:
        """Load set of already-processed event IDs."""
        try:
            if self.processed_ids_path.exists():
                with open(self.processed_ids_path, 'r') as f:
                    data = json.load(f)
                    return set(data) if isinstance(data, list) else set()
        except Exception as e:
            logger.warning(f"Could not load processed IDs: {e}")
        return set()
    
    def _save_processed_ids(self):
        """Save processed event IDs to file."""
        try:
            self.processed_ids_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.processed_ids_path, 'w') as f:
                # Keep only last 1000 IDs to prevent unbounded growth
                ids_list = list(self.processed_ids)[-1000:]
                json.dump(ids_list, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save processed IDs: {e}")
    
    def _read_scraped_events(self) -> List[dict]:
        """Read raw events from the scraper output file."""
        try:
            if not self.events_path.exists():
                logger.debug(f"Scraper events file not found: {self.events_path}")
                return []
            
            with open(self.events_path, 'r') as f:
                events = json.load(f)
                if not isinstance(events, list):
                    logger.warning("Scraped events file is not a list")
                    return []
                return events
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in scraped events file: {e}")
            return []
        except Exception as e:
            logger.error(f"Error reading scraped events: {e}")
            return []
    
    def _convert_to_event(self, scraped: dict) -> Event:
        """
        Convert a web scraper event to the trading bot Event format.
        
        Web scraper format:
        {
            "id": "uuid",
            "source": "web_scraper",
            "source_id": "sec_8k_filings",
            "source_url": "https://...",
            "title": "...",
            "content": "...",
            "detected_at": "ISO timestamp",
            "category": "corporate",
            "priority": 1,
            "change_type": "new_content" | "modified"
        }
        
        Trading bot Event format:
        Event(id, timestamp, source, source_tier, category, title, content,
              url, author, keywords_matched, urgency_score, is_duplicate,
              duplicate_of, raw_data)
        """
        event_id = scraped.get('id', str(uuid.uuid4()))
        source_id = scraped.get('source_id', 'unknown')
        
        # Parse timestamp
        timestamp_str = scraped.get('detected_at', '')
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            timestamp = datetime.now()
        
        # Map category
        scraper_category = scraped.get('category', 'general')
        mapped_category = CATEGORY_MAP.get(scraper_category, scraper_category)
        
        # Determine source tier based on the original source
        source_tier = SOURCE_TIER_MAP.get(source_id, 'tier2_politics')
        
        # Calculate urgency based on priority and content
        priority = scraped.get('priority', 2)
        base_urgency = 8.0 if priority == 1 else 5.0 if priority == 2 else 3.0
        
        # Boost urgency for certain keywords
        title = scraped.get('title', '').lower()
        content = scraped.get('content', '').lower()
        text = f"{title} {content}"
        
        urgency_keywords = {
            'fomc': 2.0,
            'rate cut': 2.0,
            'rate hike': 2.0,
            'emergency': 1.5,
            'sanctions': 1.5,
            'immediate': 1.0,
            'approval': 0.5,
            'breaking': 1.5,
        }
        
        urgency_boost = 0.0
        matched_keywords = []
        for keyword, boost in urgency_keywords.items():
            if keyword in text:
                urgency_boost = max(urgency_boost, boost)
                matched_keywords.append(keyword)
        
        urgency_score = min(10.0, base_urgency + urgency_boost)
        
        # Create Event object
        return Event(
            id=f"ws_{event_id[:8]}",  # Prefix to identify web scraper events
            timestamp=timestamp,
            source="web_scraper",
            source_tier=source_tier,
            category=mapped_category,
            title=scraped.get('title', ''),
            content=scraped.get('content', scraped.get('title', '')),
            url=scraped.get('source_url'),
            author=None,
            keywords_matched=matched_keywords,
            urgency_score=urgency_score,
            is_duplicate=False,
            duplicate_of=None,
            raw_data={
                'scraper_event': scraped,
                'source_id': source_id,
                'priority': priority,
                'change_type': scraped.get('change_type', 'unknown')
            },
            # Legacy fields
            headline=scraped.get('title', ''),
            matched_keywords=matched_keywords,
            link=scraped.get('source_url'),
            source_category=source_id
        )
    
    def fetch(self) -> List[Event]:
        """
        Fetch new events from the web scraper.
        
        Reads the scraped events file, filters out already-processed events,
        converts them to Event objects, and marks them as processed.
        
        Returns:
            List of new Event objects ready for the pipeline
        """
        logger.info("🔍 Reading web scraper events...")
        
        # Read all scraped events
        scraped_events = self._read_scraped_events()
        if not scraped_events:
            logger.info("   No scraped events found")
            return []
        
        logger.info(f"   Found {len(scraped_events)} total scraped events")
        
        # Filter out already-processed events
        new_events = []
        for scraped in scraped_events:
            event_id = scraped.get('id', '')
            if not event_id:
                continue
                
            if event_id in self.processed_ids:
                continue
            
            # Convert and add to results
            try:
                event = self._convert_to_event(scraped)
                new_events.append(event)
                self.processed_ids.add(event_id)
            except Exception as e:
                logger.warning(f"Could not convert scraped event {event_id}: {e}")
        
        # Save updated processed IDs
        if new_events:
            self._save_processed_ids()
        
        logger.info(f"   {len(new_events)} new events from web scraper")
        
        return new_events
    
    def get_status(self) -> dict:
        """Get status information about the fetcher."""
        events_file_exists = self.events_path.exists()
        event_count = 0
        
        if events_file_exists:
            try:
                with open(self.events_path, 'r') as f:
                    data = json.load(f)
                    event_count = len(data) if isinstance(data, list) else 0
            except Exception:
                pass
        
        return {
            'events_file_exists': events_file_exists,
            'events_file_path': str(self.events_path),
            'total_scraped_events': event_count,
            'processed_ids_count': len(self.processed_ids),
        }


def scan_web_scraper() -> List[Event]:
    """
    Convenience function to scan web scraper events.
    
    This mirrors the interface of scan_rss_feeds() and scan_twitter_accounts()
    for easy integration into the pipeline.
    
    Returns:
        List of Event objects from the web scraper
    """
    fetcher = WebScraperFetcher()
    return fetcher.fetch()


# For testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    fetcher = WebScraperFetcher()
    
    print("\n📊 Web Scraper Fetcher Status:")
    status = fetcher.get_status()
    for key, value in status.items():
        print(f"   {key}: {value}")
    
    print("\n🔍 Fetching new events...")
    events = fetcher.fetch()
    
    print(f"\n📥 Found {len(events)} new events:")
    for event in events:
        urgency_icon = "🔥" if event.urgency_score >= 8 else "🚨" if event.urgency_score >= 6 else "⚡"
        print(f"   {urgency_icon} [{event.category}] {event.title[:60]}... (urgency: {event.urgency_score})")
