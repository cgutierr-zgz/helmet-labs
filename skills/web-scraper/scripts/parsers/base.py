"""
Base parser interface for all content parsers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional
import hashlib


@dataclass
class ParsedItem:
    """
    Standardized structure for a parsed item.
    
    All parsers return lists of ParsedItem regardless of source type.
    """
    title: str
    link: str
    content: str  # description/summary/body
    published_at: Optional[str]  # ISO timestamp or None
    guid: str  # Unique identifier for deduplication
    
    # Optional metadata
    category: Optional[str] = None
    author: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)
    
    @staticmethod
    def generate_guid(link: str, title: str = "") -> str:
        """
        Generate a guid from link + title if no native guid exists.
        
        Uses MD5 hash for consistent, short identifiers.
        """
        content = f"{link}:{title}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()[:16]


class BaseParser(ABC):
    """
    Base parser interface.
    
    All parsers must implement the parse() method to extract
    structured items from raw content.
    """
    
    @abstractmethod
    def parse(self, content: str, source_config: dict) -> list[ParsedItem]:
        """
        Parse raw content into list of structured items.
        
        Args:
            content: Raw content string (XML, HTML, etc.)
            source_config: Source configuration from sources.json
            
        Returns:
            List of ParsedItem objects extracted from content
        """
        raise NotImplementedError
    
    def clean_text(self, text: Optional[str]) -> str:
        """Clean and normalize text content."""
        if not text:
            return ""
        # Remove excessive whitespace
        import re
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def parse_date(self, date_str: Optional[str]) -> Optional[str]:
        """
        Parse various date formats to ISO timestamp.
        
        Returns None if parsing fails.
        """
        if not date_str:
            return None
        
        date_str = date_str.strip()
        
        # Common date formats
        formats = [
            '%Y-%m-%dT%H:%M:%S.%fZ',    # ISO with microseconds
            '%Y-%m-%dT%H:%M:%SZ',        # ISO without microseconds
            '%Y-%m-%dT%H:%M:%S%z',       # ISO with timezone
            '%a, %d %b %Y %H:%M:%S %z',  # RFC 822 (RSS)
            '%a, %d %b %Y %H:%M:%S %Z',  # RFC 822 variant
            '%Y-%m-%d %H:%M:%S',         # Simple datetime
            '%Y-%m-%d',                   # Date only
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.isoformat()
            except ValueError:
                continue
        
        # Try dateutil as fallback (if available)
        try:
            from dateutil import parser as date_parser
            dt = date_parser.parse(date_str)
            return dt.isoformat()
        except (ImportError, ValueError):
            pass
        
        return None
