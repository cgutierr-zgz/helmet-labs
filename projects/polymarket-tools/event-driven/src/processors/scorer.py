"""
Advanced scoring system with modifiers as per PRD.md section 3.2.
Implements sophisticated scoring with source reliability, recency, confirmation, and market impact.
"""
import re
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass

from src.models import Event
from config.categories import CATEGORIES, URGENCY_KEYWORDS
from config.settings import SOURCES


# Source reliability tiers according to PRD.md
TIER1_SOURCES = {
    # High reliability sources
    "feeds.reuters.com", "feeds.bbci.co.uk", "rss.cnn.com", 
    "feeds.bloomberg.com", "feeds.ft.com", "feeds.wsj.com",
    "rss.ap.org", "feeds.npr.org",
    # Twitter high-tier accounts
    "BNONews", "disclosetv", "DeItaone", "unusual_whales",
    "federalreserve", "federalreserve.gov", "ecb.europa.eu"
}

TIER2_SOURCES = {
    # Reliable but not primary sources  
    "thehill.com", "politico.com", "feeds.marketwatch.com",
    "rss.cbc.ca", "feeds.skynews.com", "guardian.co.uk",
    # Twitter medium-tier accounts
    "whale_alert", "DocumentingBTC", "tier10k", "WhiteHouse",
    "RALee85", "sentdefender", "TheStudyofWar"
}

# Breaking news detection keywords
BREAKING_NEWS_KEYWORDS = {
    "breaking", "urgent", "alert", "just in", "emergency", 
    "immediate", "live", "developing", "exclusive", "confirmed",
    "official", "announced", "reports", "sources say", "unconfirmed"
}

# Numbers detection pattern for market impact
NUMBERS_PATTERN = re.compile(r'\b\d+(?:\.\d+)?(?:%|bp|bps|million|billion|trillion|k|m|b|t)?\b', re.IGNORECASE)


@dataclass 
class ScoreBreakdown:
    """Detailed breakdown of how a score was calculated."""
    base_score: int
    category: str
    source_reliability_modifier: int
    recency_modifier: int
    confirmation_modifier: int
    market_impact_modifier: int
    breaking_bonus: int
    numbers_bonus: int
    final_score: int
    
    def explain(self) -> str:
        """Human-readable explanation of the score."""
        explanation = f"Score Breakdown for {self.category}:\n"
        explanation += f"  Base Score: {self.base_score}\n"
        
        if self.source_reliability_modifier != 0:
            tier = "Tier1" if self.source_reliability_modifier == 2 else "Tier2"
            explanation += f"  Source Reliability ({tier}): +{self.source_reliability_modifier}\n"
        
        if self.recency_modifier != 0:
            if self.recency_modifier == 2:
                explanation += f"  Recency (<5 min): +{self.recency_modifier}\n"
            elif self.recency_modifier == 1:
                explanation += f"  Recency (<15 min): +{self.recency_modifier}\n"
            else:
                explanation += f"  Recency (>60 min): {self.recency_modifier}\n"
        
        if self.confirmation_modifier != 0:
            explanation += f"  Multiple Sources Confirmed: +{self.confirmation_modifier}\n"
            
        if self.breaking_bonus != 0:
            explanation += f"  Breaking News: +{self.breaking_bonus}\n"
            
        if self.numbers_bonus != 0:
            explanation += f"  Contains Specific Data: +{self.numbers_bonus}\n"
        
        explanation += f"  Final Score: {self.final_score}/10"
        return explanation


# Cache for similar event tracking (simple in-memory cache)
_similar_events_cache: Dict[str, List[Tuple[str, datetime]]] = {}
_cache_max_age_hours = 24


def _clean_cache():
    """Remove old entries from the similar events cache."""
    cutoff = datetime.now().timestamp() - (_cache_max_age_hours * 3600)
    for key in list(_similar_events_cache.keys()):
        _similar_events_cache[key] = [
            (event_id, timestamp) for event_id, timestamp in _similar_events_cache[key]
            if timestamp.timestamp() > cutoff
        ]
        if not _similar_events_cache[key]:
            del _similar_events_cache[key]


def _extract_key_terms(event: Event) -> Set[str]:
    """Extract key terms from event for similarity matching."""
    text = f"{event.title} {event.content or ''}".lower()
    
    # Remove common words and extract meaningful terms
    stop_words = {"the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "a", "an"}
    words = re.findall(r'\b\w{3,}\b', text)  # Words 3+ chars
    
    # Add matched keywords if available
    if hasattr(event, 'keywords_matched') and event.keywords_matched:
        words.extend([kw.lower() for kw in event.keywords_matched])
    
    # Filter stop words and return unique terms
    return {word for word in words if word not in stop_words}


def _is_similar_to_cached_event(event: Event, threshold: float = 0.4) -> bool:
    """Check if event is similar to any recently processed events."""
    _clean_cache()
    
    event_terms = _extract_key_terms(event)
    if not event_terms:
        return False
    
    cache_key = event.category
    if cache_key not in _similar_events_cache:
        return False
    
    # Require at least 2 events in cache to consider confirmation
    if len(_similar_events_cache[cache_key]) < 2:
        return False
    
    # Check similarity with recent events in same category
    similar_count = 0
    for cached_event_id, cached_timestamp in _similar_events_cache[cache_key]:
        # Don't compare with the exact same event
        if cached_event_id == event.id:
            continue
            
        # Check time window (within 2 hours for confirmation)
        time_diff = abs((event.timestamp - cached_timestamp).total_seconds()) / 60
        if time_diff < 120:  # Within 2 hours
            similar_count += 1
            
        # Need at least 2 similar events for confirmation
        if similar_count >= 2:
            return True
    
    return False


def _add_to_cache(event: Event):
    """Add event to the similar events cache."""
    cache_key = event.category
    if cache_key not in _similar_events_cache:
        _similar_events_cache[cache_key] = []
    
    _similar_events_cache[cache_key].append((event.id, event.timestamp))
    
    # Limit cache size per category
    if len(_similar_events_cache[cache_key]) > 50:
        _similar_events_cache[cache_key] = _similar_events_cache[cache_key][-25:]


def _get_source_identifier(event: Event) -> str:
    """Extract source identifier from event for tier classification."""
    # Try multiple source fields
    source = event.source or event.feed or event.account or ""
    
    # Clean up the source string to match our tier definitions
    if "twitter" in event.source.lower() and event.account:
        return event.account.replace("@", "").lower()
    elif "rss" in event.source.lower() and event.feed:
        # Extract domain from feed URL
        import urllib.parse
        try:
            parsed = urllib.parse.urlparse(event.feed)
            return parsed.netloc.lower()
        except:
            return event.feed.lower()
    
    return source.lower()


def _calculate_source_reliability_modifier(event: Event) -> int:
    """Calculate source reliability modifier (+2 for tier1, +1 for tier2, 0 for tier3)."""
    source_id = _get_source_identifier(event)
    
    # Check exact matches and partial matches
    for tier1_source in TIER1_SOURCES:
        if tier1_source.lower() in source_id or source_id in tier1_source.lower():
            return 2
    
    for tier2_source in TIER2_SOURCES:
        if tier2_source.lower() in source_id or source_id in tier2_source.lower():
            return 1
    
    return 0  # Tier 3 (unknown/low reliability)


def _calculate_recency_modifier(event: Event) -> int:
    """Calculate recency modifier based on event age."""
    try:
        if isinstance(event.timestamp, str):
            event_time = datetime.fromisoformat(event.timestamp.replace('Z', '+00:00'))
        else:
            event_time = event.timestamp
            
        age_minutes = (datetime.now() - event_time).total_seconds() / 60
        
        if age_minutes < 5:
            return 2
        elif age_minutes < 15:
            return 1
        elif age_minutes > 60:
            return -2
        else:
            return 0
    except Exception:
        return 0  # If timestamp parsing fails, no modifier


def _calculate_confirmation_modifier(event: Event) -> int:
    """Calculate confirmation modifier based on multiple source detection."""
    # Check if this event is similar to recent events (suggesting multiple sources)
    if _is_similar_to_cached_event(event):
        return 2
    return 0


def _is_breaking_news(event: Event) -> bool:
    """Detect if event contains breaking news keywords."""
    text = f"{event.title} {event.content or ''}".lower()
    return any(keyword in text for keyword in BREAKING_NEWS_KEYWORDS)


def _contains_numbers(event: Event) -> bool:
    """Detect if event contains specific numerical data."""
    text = f"{event.title} {event.content or ''}"
    return bool(NUMBERS_PATTERN.search(text))


def calculate_score(event: Event) -> int:
    """
    Calculate advanced score as per PRD.md section 3.2.
    
    Args:
        event: Event object to score
        
    Returns:
        Score between 1-10
    """
    # Get base score from category
    base_score = CATEGORIES.get(event.category, {}).get("base_score", 5)
    
    # Calculate all modifiers
    source_modifier = _calculate_source_reliability_modifier(event)
    recency_modifier = _calculate_recency_modifier(event)
    confirmation_modifier = _calculate_confirmation_modifier(event)
    
    # Market impact modifiers
    breaking_bonus = 2 if _is_breaking_news(event) else 0
    numbers_bonus = 1 if _contains_numbers(event) else 0
    market_impact_modifier = breaking_bonus + numbers_bonus
    
    # Calculate final score
    final_score = (
        base_score + 
        source_modifier + 
        recency_modifier + 
        confirmation_modifier + 
        market_impact_modifier
    )
    
    # Clamp to 1-10 range
    final_score = min(max(final_score, 1), 10)
    
    # Add to cache for future confirmation detection
    _add_to_cache(event)
    
    return final_score


def calculate_score_with_breakdown(event: Event) -> Tuple[int, ScoreBreakdown]:
    """
    Calculate score and return detailed breakdown.
    
    Args:
        event: Event object to score
        
    Returns:
        Tuple of (final_score, breakdown_object)
    """
    # Get base score from category
    base_score = CATEGORIES.get(event.category, {}).get("base_score", 5)
    
    # Calculate all modifiers
    source_modifier = _calculate_source_reliability_modifier(event)
    recency_modifier = _calculate_recency_modifier(event)
    confirmation_modifier = _calculate_confirmation_modifier(event)
    
    # Market impact modifiers
    breaking_bonus = 2 if _is_breaking_news(event) else 0
    numbers_bonus = 1 if _contains_numbers(event) else 0
    market_impact_modifier = breaking_bonus + numbers_bonus
    
    # Calculate final score
    final_score = (
        base_score + 
        source_modifier + 
        recency_modifier + 
        confirmation_modifier + 
        market_impact_modifier
    )
    
    # Clamp to 1-10 range
    final_score = min(max(final_score, 1), 10)
    
    # Create breakdown object
    breakdown = ScoreBreakdown(
        base_score=base_score,
        category=event.category,
        source_reliability_modifier=source_modifier,
        recency_modifier=recency_modifier,
        confirmation_modifier=confirmation_modifier,
        market_impact_modifier=market_impact_modifier,
        breaking_bonus=breaking_bonus,
        numbers_bonus=numbers_bonus,
        final_score=final_score
    )
    
    # Add to cache for future confirmation detection
    _add_to_cache(event)
    
    return final_score, breakdown


def explain_score(event: Event) -> str:
    """
    Generate human-readable explanation of event score.
    
    Args:
        event: Event object to explain
        
    Returns:
        String explanation of the scoring
    """
    score, breakdown = calculate_score_with_breakdown(event)
    return breakdown.explain()


# Legacy compatibility function
def calculate_urgency_score(event: Event) -> float:
    """
    Legacy function for backward compatibility.
    Maps to new calculate_score function.
    
    Args:
        event: Event object to score
        
    Returns:
        Urgency score between 1.0 and 10.0
    """
    return float(calculate_score(event))