"""
Event deduplication system.
Extracts deduplication logic from scan.py.
"""
import hashlib
import re
from difflib import SequenceMatcher
from typing import List, Dict, Any
from src.models import Event
from config.settings import SIMILARITY_THRESHOLD

def similarity(a: str, b: str) -> float:
    """Calculate text similarity using SequenceMatcher."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def create_content_hash(text: str) -> str:
    """Create a hash for deduplication based on key content words."""
    # Extract key words (remove common words)
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were'}
    words = [w.lower() for w in re.findall(r'\w+', text) if len(w) > 3 and w.lower() not in stop_words]
    key_content = ' '.join(sorted(words[:10]))  # Sort to normalize order
    return hashlib.md5(key_content.encode()).hexdigest()

def is_duplicate(new_event: Event, existing_alerts: List[Dict[str, Any]], similarity_threshold: float = SIMILARITY_THRESHOLD) -> bool:
    """
    Check if new event is duplicate of existing ones.
    Uses both content similarity and hash matching.
    
    Args:
        new_event: New Event to check
        existing_alerts: List of existing alert dictionaries
        similarity_threshold: Similarity threshold for duplicate detection
        
    Returns:
        True if the event is considered a duplicate
    """
    new_headline = new_event.headline
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

def generate_alert_id(event: Event) -> str:
    """Generate a unique ID for the event for traditional ID-based deduplication."""
    source_identifier = event.link or event.headline[:50]
    return f"{event.source}:{source_identifier}"