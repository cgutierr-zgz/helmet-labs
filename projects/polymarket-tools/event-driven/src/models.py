"""
Data models for the event-driven system.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any
import json

@dataclass
class Event:
    """Represents a detected event from any source."""
    timestamp: str
    source: str  # "rss" or "twitter"
    category: str  # Alert category (e.g., "fed", "trump_deportations") 
    headline: str
    matched_keywords: List[str]
    urgency_score: float = 5.0
    
    # Source-specific fields
    feed: Optional[str] = None  # RSS feed URL
    account: Optional[str] = None  # Twitter account
    link: Optional[str] = None  # Article URL
    tweet_id: Optional[str] = None  # Twitter ID
    source_category: Optional[str] = None  # RSS category
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'timestamp': self.timestamp,
            'source': self.source,
            'category': self.category, 
            'headline': self.headline,
            'matched_keywords': self.matched_keywords,
            'urgency_score': self.urgency_score,
            'feed': self.feed,
            'account': self.account,
            'link': self.link,
            'tweet_id': self.tweet_id,
            'source_category': self.source_category
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """Create Event from dictionary."""
        return cls(**data)

@dataclass 
class ScanState:
    """Maintains state between scans."""
    last_scan: Optional[str]
    seen_ids: List[str]
    recent_alerts: List[Dict[str, Any]]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'last_scan': self.last_scan,
            'seen_ids': self.seen_ids,
            'recent_alerts': self.recent_alerts
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScanState':
        return cls(
            last_scan=data.get('last_scan'),
            seen_ids=data.get('seen_ids', []),
            recent_alerts=data.get('recent_alerts', [])
        )