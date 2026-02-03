"""
Urgency scoring system.
Extracts urgency calculation logic from scan.py.
"""
from datetime import datetime
from src.models import Event
from config.settings import URGENCY_MULTIPLIERS, URGENCY_KEYWORDS, SOURCES

def calculate_urgency_score(event: Event) -> float:
    """
    Calculate urgency score 1-10 based on multiple factors:
    - Category importance
    - Urgency keywords in title
    - Source priority
    - Time sensitivity
    
    Args:
        event: Event object to score
        
    Returns:
        Urgency score between 1.0 and 10.0
    """
    base_score = 5.0  # Default baseline
    
    # Category multiplier
    category = event.category
    category_mult = URGENCY_MULTIPLIERS.get(category, 1.0)
    base_score *= category_mult
    
    # Urgency keywords in headline
    headline = event.headline.lower()
    urgency_boost = 0
    for keyword, boost in URGENCY_KEYWORDS.items():
        if keyword in headline:
            urgency_boost = max(urgency_boost, boost)
    
    base_score += urgency_boost
    
    # Source priority (Fed feeds = high priority)
    source_url = event.feed or event.account or ""
    priority_sources = SOURCES.get('priority_sources', {})
    
    if source_url in priority_sources.get('high', []):
        base_score += 2.0
    elif source_url in priority_sources.get('medium', []):
        base_score += 1.0
    
    # Time decay - newer = more urgent
    try:
        alert_time = datetime.fromisoformat(event.timestamp)
        age_minutes = (datetime.now() - alert_time).total_seconds() / 60
        if age_minutes < 10:  # Very fresh
            base_score += 1.0
        elif age_minutes < 30:  # Still fresh
            base_score += 0.5
    except Exception:
        pass  # Skip time decay if timestamp parsing fails
    
    # Cap at 10, floor at 1
    return min(10.0, max(1.0, round(base_score, 1)))