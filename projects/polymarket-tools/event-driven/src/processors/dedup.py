"""
Intelligent event deduplication system.
Enhanced with multiple detection strategies, merging, and analytics.
"""
import hashlib
import re
from difflib import SequenceMatcher
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass

from src.models import Event
from src.processors.classifier import extract_entities
from config.settings import SIMILARITY_THRESHOLD, STATE_RETENTION_HOURS


@dataclass
class DuplicateAnalytics:
    """Analytics data for duplicate detection."""
    total_events: int = 0
    duplicates_found: int = 0
    url_duplicates: int = 0
    title_duplicates: int = 0
    content_duplicates: int = 0
    entity_duplicates: int = 0
    merged_events: int = 0
    
    @property
    def duplicate_rate(self) -> float:
        """Calculate duplicate detection rate."""
        if self.total_events == 0:
            return 0.0
        return self.duplicates_found / self.total_events


def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculate Levenshtein distance between two strings.
    Efficient implementation for deduplication.
    """
    if not s1:
        return len(s2)
    if not s2:
        return len(s1)
    
    # Create matrix
    rows = len(s1) + 1
    cols = len(s2) + 1
    
    # Initialize first row and column
    prev_row = list(range(cols))
    
    for i in range(1, rows):
        curr_row = [i]
        
        for j in range(1, cols):
            if s1[i-1] == s2[j-1]:
                cost = 0
            else:
                cost = 1
                
            curr_row.append(min(
                prev_row[j] + 1,      # deletion
                curr_row[j-1] + 1,    # insertion
                prev_row[j-1] + cost  # substitution
            ))
        
        prev_row = curr_row
    
    return prev_row[-1]


def levenshtein_ratio(s1: str, s2: str) -> float:
    """
    Calculate normalized Levenshtein similarity ratio (0.0 - 1.0).
    Higher values indicate more similarity.
    """
    distance = levenshtein_distance(s1, s2)
    max_len = max(len(s1), len(s2))
    
    if max_len == 0:
        return 1.0
    
    return 1.0 - (distance / max_len)


def sequence_matcher_similarity(s1: str, s2: str) -> float:
    """
    Calculate text similarity using SequenceMatcher.
    Fallback for levenshtein_ratio.
    """
    return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()


def calculate_similarity(s1: str, s2: str, method: str = "levenshtein") -> float:
    """
    Calculate text similarity using specified method.
    
    Args:
        s1: First string
        s2: Second string  
        method: "levenshtein" or "sequence_matcher"
        
    Returns:
        Similarity ratio (0.0 - 1.0)
    """
    if method == "levenshtein":
        return levenshtein_ratio(s1, s2)
    else:
        return sequence_matcher_similarity(s1, s2)


def normalize_content(text: str) -> str:
    """
    Normalize content for hash-based deduplication.
    Removes common variations that don't change meaning.
    """
    # Convert to lowercase
    text = text.lower()
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Remove common prefixes/suffixes that don't change content
    prefixes = ['breaking:', 'urgent:', 'alert:', 'just in:', 'update:', 'live:']
    for prefix in prefixes:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    
    # Remove trailing metadata
    # Remove stuff like " - CNN", " | Reuters", etc.
    text = re.sub(r'\s*[-|]\s*[A-Z]{2,}\s*$', '', text)
    text = re.sub(r'\s*[-|]\s*\w+\s*$', '', text)
    
    # Remove common time indicators that change frequently
    text = re.sub(r'\b\d{1,2}:\d{2}\s*(am|pm)?\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(today|yesterday|now|just|minutes ago|hours ago)\b', '', text, flags=re.IGNORECASE)
    
    # Remove quotes and extra punctuation
    text = re.sub(r'["""''„"]', '', text)
    text = re.sub(r'[^\w\s]', ' ', text)
    
    # Final cleanup
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def create_content_hash(text: str, include_stop_words: bool = False) -> str:
    """
    Create a hash for deduplication based on normalized content.
    
    Args:
        text: Original text
        include_stop_words: Whether to include stop words in hash
        
    Returns:
        MD5 hash of normalized content
    """
    normalized = normalize_content(text)
    
    if not include_stop_words:
        # Remove common stop words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have',
            'has', 'had', 'will', 'would', 'could', 'should', 'may', 'might',
            'this', 'that', 'these', 'those', 'it', 'its', 'he', 'she', 'his', 'her'
        }
        
        words = [w for w in normalized.split() if w not in stop_words and len(w) > 2]
        normalized = ' '.join(words)
    
    return hashlib.md5(normalized.encode()).hexdigest()


def extract_event_entities(event: Event) -> Set[str]:
    """
    Extract entities from an event for comparison.
    
    Args:
        event: Event to extract entities from
        
    Returns:
        Set of normalized entity strings
    """
    # Use full text: title + content
    full_text = f"{event.title} {event.content or ''}"
    
    # Extract entities using classifier
    entities_dict = extract_entities(full_text)
    
    # Flatten to set of normalized strings
    entities = set()
    for entity_type, entity_list in entities_dict.items():
        for entity in entity_list:
            # Normalize entity strings
            normalized = entity.lower().strip()
            if normalized and len(normalized) > 2:
                entities.add(normalized)
    
    return entities


def calculate_time_diff(event1: Event, event2: Event) -> float:
    """
    Calculate time difference between two events in seconds.
    
    Args:
        event1: First event
        event2: Second event
        
    Returns:
        Time difference in seconds (absolute value)
    """
    return abs((event1.timestamp - event2.timestamp).total_seconds())


def is_duplicate(new_event: Event, recent_events: List[Event], 
                threshold: float = SIMILARITY_THRESHOLD,
                analytics: Optional[DuplicateAnalytics] = None) -> Tuple[bool, Optional[str], str]:
    """
    Check if new event is duplicate using multiple strategies.
    
    Args:
        new_event: Event to check for duplication
        recent_events: List of recent events to compare against
        threshold: Similarity threshold for title matching (default: 0.8)
        analytics: Optional analytics object to track detection stats
        
    Returns:
        Tuple of (is_duplicate, duplicate_of_id, detection_method)
    """
    if analytics:
        analytics.total_events += 1
    
    for existing in recent_events:
        # Skip if comparing with itself
        if new_event.id == existing.id:
            continue
        
        # Strategy 1: Exact URL match
        if (new_event.url and existing.url and 
            new_event.url == existing.url):
            if analytics:
                analytics.duplicates_found += 1
                analytics.url_duplicates += 1
            return True, existing.id, "url_match"
        
        # Strategy 2: Title similarity
        title_similarity = calculate_similarity(new_event.title, existing.title)
        if title_similarity > threshold:
            if analytics:
                analytics.duplicates_found += 1
                analytics.title_duplicates += 1
            return True, existing.id, "title_similarity"
        
        # Strategy 3: Content hash match
        new_hash = create_content_hash(new_event.title)
        existing_hash = create_content_hash(existing.title)
        if new_hash == existing_hash:
            if analytics:
                analytics.duplicates_found += 1
                analytics.content_duplicates += 1
            return True, existing.id, "content_hash"
        
        # Strategy 4: Entity overlap + same category + within time window
        time_diff = calculate_time_diff(new_event, existing)
        if (new_event.category == existing.category and 
            time_diff < 3600):  # Within 1 hour
            
            new_entities = extract_event_entities(new_event)
            existing_entities = extract_event_entities(existing)
            
            # Check for significant entity overlap
            if new_entities and existing_entities:
                common_entities = new_entities & existing_entities
                overlap_ratio = len(common_entities) / max(len(new_entities), len(existing_entities))
                
                # If 50%+ entity overlap + same category + within 1 hour
                if overlap_ratio >= 0.5:
                    if analytics:
                        analytics.duplicates_found += 1
                        analytics.entity_duplicates += 1
                    return True, existing.id, "entity_overlap"
    
    return False, None, "none"


def find_duplicate_original(duplicate_event: Event, candidate_events: List[Event]) -> Optional[Event]:
    """
    Find the "original" event that this duplicate should reference.
    Uses timestamp priority and content completeness.
    
    Args:
        duplicate_event: Event marked as duplicate
        candidate_events: List of potential original events
        
    Returns:
        Original event or None if not found
    """
    candidates = []
    
    for event in candidate_events:
        # Skip self and other duplicates
        if event.id == duplicate_event.id or event.is_duplicate:
            continue
        
        # Check if they could be duplicates
        is_dup, _, method = _is_duplicate_new(duplicate_event, [event])
        
        if is_dup:
            # Score based on:
            # 1. Earlier timestamp (higher score)
            # 2. More complete content (longer title/content)
            # 3. Higher tier source
            
            time_score = 1.0 if event.timestamp <= duplicate_event.timestamp else 0.5
            content_score = len(event.content or event.title) / 500  # Normalize to content length
            
            tier_scores = {"tier1_breaking": 1.0, "tier2_reliable": 0.8, "tier3_general": 0.6}
            source_score = tier_scores.get(event.source_tier, 0.5)
            
            total_score = time_score + content_score + source_score
            candidates.append((event, total_score))
    
    if candidates:
        # Return event with highest score
        return max(candidates, key=lambda x: x[1])[0]
    
    return None


def merge_duplicate_info(original: Event, duplicate: Event) -> Event:
    """
    Merge information from duplicate into original event.
    Preserves additional information from duplicate if it's more complete.
    
    Args:
        original: Original event to update
        duplicate: Duplicate event with potential additional info
        
    Returns:
        Updated original event
    """
    # Merge content if duplicate has more information
    if duplicate.content and len(duplicate.content) > len(original.content or ''):
        original.content = duplicate.content
    
    # Merge keywords
    if duplicate.keywords_matched:
        original.keywords_matched = list(set(original.keywords_matched + duplicate.keywords_matched))
    
    # Use higher urgency score
    if duplicate.urgency_score > original.urgency_score:
        original.urgency_score = duplicate.urgency_score
    
    # Merge URLs if original doesn't have one
    if not original.url and duplicate.url:
        original.url = duplicate.url
    
    # Merge author if original doesn't have one
    if not original.author and duplicate.author:
        original.author = duplicate.author
    
    # Merge raw_data
    if duplicate.raw_data:
        original.raw_data.update(duplicate.raw_data)
    
    return original


def mark_as_duplicate(event: Event, original_id: str, detection_method: str):
    """
    Mark an event as duplicate and set metadata.
    
    Args:
        event: Event to mark as duplicate
        original_id: ID of the original event
        detection_method: Method used to detect duplication
    """
    event.is_duplicate = True
    event.duplicate_of = original_id
    
    # Add detection metadata to raw_data
    event.raw_data['duplicate_detection'] = {
        'method': detection_method,
        'detected_at': datetime.now().isoformat(),
        'original_id': original_id
    }


def cleanup_old_events(events: List[Event], max_age_hours: float = STATE_RETENTION_HOURS) -> List[Event]:
    """
    Remove old events from tracking list to prevent memory bloat.
    
    Args:
        events: List of events to clean
        max_age_hours: Maximum age in hours to keep
        
    Returns:
        Filtered list of recent events
    """
    cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
    
    return [
        event for event in events 
        if event.timestamp >= cutoff_time
    ]


def deduplicate_event_batch(new_events: List[Event], existing_events: List[Event],
                          threshold: float = SIMILARITY_THRESHOLD,
                          merge_duplicates: bool = True) -> Tuple[List[Event], DuplicateAnalytics]:
    """
    Process a batch of new events for deduplication.
    
    Args:
        new_events: List of new events to process
        existing_events: List of existing events for comparison
        threshold: Similarity threshold for duplicate detection
        merge_duplicates: Whether to merge duplicate information
        
    Returns:
        Tuple of (processed_events, analytics)
    """
    analytics = DuplicateAnalytics()
    processed_events = []
    
    # Clean up old events first
    recent_events = cleanup_old_events(existing_events)
    
    for new_event in new_events:
        # Check if it's a duplicate
        is_dup, original_id, method = _is_duplicate_new(new_event, recent_events, threshold, analytics)
        
        if is_dup and original_id:
            # Mark as duplicate
            mark_as_duplicate(new_event, original_id, method)
            
            # Optionally merge information back to original
            if merge_duplicates:
                original = next((e for e in recent_events if e.id == original_id), None)
                if original:
                    merge_duplicate_info(original, new_event)
                    analytics.merged_events += 1
        
        processed_events.append(new_event)
        
        # Add to recent events for future comparisons
        recent_events.append(new_event)
    
    return processed_events, analytics


# Legacy compatibility functions
def similarity(a: str, b: str) -> float:
    """Legacy function for backward compatibility."""
    return calculate_similarity(a, b)


def is_duplicate_legacy(new_event: Event, existing_alerts: List[Dict[str, Any]], 
                       similarity_threshold: float = SIMILARITY_THRESHOLD) -> bool:
    """
    Legacy wrapper for is_duplicate function.
    Maintains compatibility with existing code that uses alert dictionaries.
    
    Args:
        new_event: New Event to check
        existing_alerts: List of existing alert dictionaries (legacy format)
        similarity_threshold: Similarity threshold for duplicate detection
        
    Returns:
        True if the event is considered a duplicate
    """
    # Convert alert dictionaries to Event objects
    existing_events = []
    
    for alert_data in existing_alerts:
        try:
            # Create Event from dictionary 
            event = Event.from_dict(alert_data)
            existing_events.append(event)
        except Exception as e:
            # Skip invalid alert data
            print(f"Warning: Skipping invalid alert data: {e}")
            continue
    
    # Use new is_duplicate function (stored reference before override)
    is_dup, _, _ = _is_duplicate_new(new_event, existing_events, similarity_threshold)
    return is_dup


def generate_alert_id(event: Event) -> str:
    """Generate a unique ID for the event for traditional ID-based deduplication."""
    source_identifier = event.url or event.title[:50]
    return f"{event.source}:{source_identifier}"


# Store reference to new function before overriding
_is_duplicate_new = is_duplicate

# Override the is_duplicate function for backward compatibility
# This allows existing code to work without changes
is_duplicate = is_duplicate_legacy