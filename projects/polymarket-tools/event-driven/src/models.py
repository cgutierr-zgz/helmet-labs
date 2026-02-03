"""
Data models for the event-driven system.
Enhanced with robust Event, Signal, and Alert models for Polymarket trading.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any, Literal
import json
import uuid
import hashlib


@dataclass
class Event:
    """Represents a detected event from any source with comprehensive metadata."""
    id: str
    timestamp: datetime
    source: str  # "rss" | "twitter"
    source_tier: str  # "tier1_breaking", "tier2_reliable", "tier3_general"
    category: str  # "fed", "crypto", "politics", "sports", etc.
    title: str
    content: str
    url: Optional[str]
    author: Optional[str]
    keywords_matched: List[str]
    urgency_score: float  # 1-10 scale
    is_duplicate: bool
    duplicate_of: Optional[str]
    raw_data: dict
    
    # Legacy fields for backward compatibility
    headline: Optional[str] = None
    matched_keywords: Optional[List[str]] = None
    feed: Optional[str] = None
    account: Optional[str] = None
    link: Optional[str] = None
    tweet_id: Optional[str] = None
    source_category: Optional[str] = None
    
    def __post_init__(self):
        """Post-initialization processing for backward compatibility."""
        # Sync legacy fields
        if self.headline and not self.title:
            self.title = self.headline
        elif self.title and not self.headline:
            self.headline = self.title
            
        if self.matched_keywords and not self.keywords_matched:
            self.keywords_matched = self.matched_keywords
        elif self.keywords_matched and not self.matched_keywords:
            self.matched_keywords = self.keywords_matched
            
        if self.link and not self.url:
            self.url = self.link
        elif self.url and not self.link:
            self.link = self.url
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            'source': self.source,
            'source_tier': self.source_tier,
            'category': self.category,
            'title': self.title,
            'content': self.content,
            'url': self.url,
            'author': self.author,
            'keywords_matched': self.keywords_matched,
            'urgency_score': self.urgency_score,
            'is_duplicate': self.is_duplicate,
            'duplicate_of': self.duplicate_of,
            'raw_data': self.raw_data,
            # Legacy fields
            'headline': self.headline,
            'matched_keywords': self.matched_keywords,
            'feed': self.feed,
            'account': self.account,
            'link': self.link,
            'tweet_id': self.tweet_id,
            'source_category': self.source_category
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """Create Event from dictionary with validation."""
        # Convert timestamp string back to datetime if needed
        timestamp = data.get('timestamp')
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except ValueError:
                timestamp = datetime.now()
        elif not isinstance(timestamp, datetime):
            timestamp = datetime.now()
        
        data = data.copy()
        data['timestamp'] = timestamp
        
        # Provide defaults for required fields
        data.setdefault('id', str(uuid.uuid4()))
        data.setdefault('source_tier', 'tier3_general')
        data.setdefault('urgency_score', 5.0)
        data.setdefault('is_duplicate', False)
        data.setdefault('keywords_matched', [])
        data.setdefault('raw_data', {})
        
        return cls(**data)
    
    @classmethod
    def create_from_legacy(cls, legacy_event: Dict[str, Any]) -> 'Event':
        """Create new Event from legacy event data."""
        # Generate ID from content hash for consistency
        content_hash = hashlib.md5(
            f"{legacy_event.get('headline', '')}{legacy_event.get('timestamp', '')}".encode()
        ).hexdigest()[:8]
        
        # Map legacy fields to new model
        return cls(
            id=f"evt_{content_hash}",
            timestamp=datetime.fromisoformat(legacy_event['timestamp']) if isinstance(legacy_event.get('timestamp'), str) else datetime.now(),
            source=legacy_event.get('source', 'unknown'),
            source_tier='tier3_general',  # Default, can be improved with source mapping
            category=legacy_event.get('category', 'general'),
            title=legacy_event.get('headline', ''),
            content=legacy_event.get('headline', ''),  # Use headline as content for now
            url=legacy_event.get('link'),
            author=legacy_event.get('account'),
            keywords_matched=legacy_event.get('matched_keywords', []),
            urgency_score=legacy_event.get('urgency_score', 5.0),
            is_duplicate=False,
            duplicate_of=None,
            raw_data=legacy_event,
            # Preserve legacy fields
            headline=legacy_event.get('headline'),
            matched_keywords=legacy_event.get('matched_keywords'),
            feed=legacy_event.get('feed'),
            account=legacy_event.get('account'),
            link=legacy_event.get('link'),
            tweet_id=legacy_event.get('tweet_id'),
            source_category=legacy_event.get('source_category')
        )
    
    def validate(self) -> List[str]:
        """Validate event data and return list of errors."""
        errors = []
        
        if not self.id:
            errors.append("Event ID is required")
        
        if not self.title:
            errors.append("Event title is required")
        
        if not self.source or self.source not in ['rss', 'twitter']:
            errors.append("Valid source (rss/twitter) is required")
        
        if not (1 <= self.urgency_score <= 10):
            errors.append("Urgency score must be between 1-10")
        
        if not isinstance(self.keywords_matched, list):
            errors.append("keywords_matched must be a list")
        
        return errors


@dataclass
class Signal:
    """Trading signal generated from event analysis."""
    market_id: str
    direction: Literal["BUY_YES", "BUY_NO", "HOLD"]
    confidence: float  # 0.0 - 1.0
    reasoning: str
    current_price: float
    expected_price: float
    event_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'market_id': self.market_id,
            'direction': self.direction,
            'confidence': self.confidence,
            'reasoning': self.reasoning,
            'current_price': self.current_price,
            'expected_price': self.expected_price,
            'event_id': self.event_id,
            'timestamp': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Signal':
        """Create Signal from dictionary with validation."""
        data = data.copy()
        
        # Convert timestamp string back to datetime if needed
        timestamp = data.get('timestamp')
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except ValueError:
                timestamp = datetime.now()
        elif not isinstance(timestamp, datetime):
            timestamp = datetime.now()
        
        data['timestamp'] = timestamp
        return cls(**data)
    
    def validate(self) -> List[str]:
        """Validate signal data and return list of errors."""
        errors = []
        
        if not self.market_id:
            errors.append("Market ID is required")
        
        if self.direction not in ["BUY_YES", "BUY_NO", "HOLD"]:
            errors.append("Direction must be BUY_YES, BUY_NO, or HOLD")
        
        if not (0.0 <= self.confidence <= 1.0):
            errors.append("Confidence must be between 0.0-1.0")
        
        if self.current_price < 0:
            errors.append("Current price must be non-negative")
        
        if not self.reasoning:
            errors.append("Reasoning is required")
        
        return errors
    
    @property 
    def expected_return(self) -> float:
        """Calculate expected return percentage."""
        if self.current_price == 0:
            return 0.0
        return (self.expected_price - self.current_price) / self.current_price


@dataclass
class Alert:
    """Alert containing event and associated trading signals."""
    id: str
    event: Event
    signals: List[Signal]
    priority: int  # 1-10 scale
    sent: bool
    sent_at: Optional[datetime]
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'event': self.event.to_dict(),
            'signals': [signal.to_dict() for signal in self.signals],
            'priority': self.priority,
            'sent': self.sent,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Alert':
        """Create Alert from dictionary with validation."""
        data = data.copy()
        
        # Convert event
        if isinstance(data['event'], dict):
            data['event'] = Event.from_dict(data['event'])
        
        # Convert signals
        if 'signals' in data:
            data['signals'] = [
                Signal.from_dict(signal) if isinstance(signal, dict) else signal
                for signal in data['signals']
            ]
        
        # Convert timestamps
        for field_name in ['sent_at', 'created_at']:
            timestamp = data.get(field_name)
            if isinstance(timestamp, str):
                try:
                    data[field_name] = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                except ValueError:
                    if field_name == 'created_at':
                        data[field_name] = datetime.now()
                    else:
                        data[field_name] = None
        
        return cls(**data)
    
    def validate(self) -> List[str]:
        """Validate alert data and return list of errors."""
        errors = []
        
        if not self.id:
            errors.append("Alert ID is required")
        
        if not (1 <= self.priority <= 10):
            errors.append("Priority must be between 1-10")
        
        # Validate nested objects
        errors.extend([f"Event: {err}" for err in self.event.validate()])
        
        for i, signal in enumerate(self.signals):
            errors.extend([f"Signal {i}: {err}" for err in signal.validate()])
        
        return errors
    
    def mark_sent(self):
        """Mark alert as sent with timestamp."""
        self.sent = True
        self.sent_at = datetime.now()
    
    @property
    def total_confidence(self) -> float:
        """Average confidence across all signals."""
        if not self.signals:
            return 0.0
        return sum(signal.confidence for signal in self.signals) / len(self.signals)
    
    @property
    def max_expected_return(self) -> float:
        """Maximum expected return across all signals."""
        if not self.signals:
            return 0.0
        return max(abs(signal.expected_return) for signal in self.signals)


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