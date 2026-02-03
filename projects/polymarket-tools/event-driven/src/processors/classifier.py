"""
Intelligent event classification system.
Handles multi-category classification, entity extraction, and confidence scoring.
"""
import re
from typing import List, Tuple, Optional, Dict, Set
from dataclasses import dataclass
from datetime import datetime

from config.categories import (
    CATEGORIES, ENTITY_PATTERNS, URGENCY_KEYWORDS, 
    SOURCE_MODIFIERS, get_category_names
)
from src.models import Event


@dataclass
class ClassificationResult:
    """Result of event classification."""
    categories: List[str]  # Multiple categories possible
    matched_keywords: Dict[str, List[str]]  # Keywords by category
    confidence_scores: Dict[str, float]  # Confidence by category
    entities: Dict[str, List[str]]  # Extracted entities by type
    urgency_score: float  # Final urgency score (1-10)
    primary_category: str  # Main category with highest confidence


def extract_entities(text: str) -> Dict[str, List[str]]:
    """
    Extract entities from text using regex patterns.
    
    Args:
        text: Text to analyze
        
    Returns:
        Dictionary mapping entity type to list of found entities
    """
    entities = {}
    
    for entity_type, pattern in ENTITY_PATTERNS.items():
        matches = pattern.findall(text)
        if matches:
            # Remove duplicates while preserving order
            entities[entity_type] = list(dict.fromkeys(matches))
    
    return entities


def calculate_keyword_score(text: str, keywords: List[str]) -> Tuple[List[str], float]:
    """
    Calculate keyword matching score for a category.
    
    Args:
        text: Text to analyze (lowercase)
        keywords: List of keywords to match
        
    Returns:
        Tuple of (matched_keywords, score)
    """
    text_lower = text.lower()
    matched = []
    score = 0.0
    
    for keyword in keywords:
        if keyword.lower() in text_lower:
            matched.append(keyword)
            # Score based on keyword specificity (longer = more specific)
            keyword_score = 1.0 + (len(keyword.split()) - 1) * 0.5
            score += keyword_score
    
    # Normalize by total possible keywords
    if keywords:
        score = min(score / len(keywords), 1.0)
    
    return matched, score


def calculate_pattern_score(text: str, patterns: List[re.Pattern]) -> float:
    """
    Calculate pattern matching score using regex patterns.
    
    Args:
        text: Text to analyze
        patterns: List of compiled regex patterns
        
    Returns:
        Pattern matching score (0.0-1.0)
    """
    if not patterns:
        return 0.0
    
    matches = 0
    for pattern in patterns:
        if pattern.search(text):
            matches += 1
    
    return matches / len(patterns)


def calculate_urgency_modifiers(text: str, source_tier: str) -> float:
    """
    Calculate urgency modifiers based on text content and source.
    
    Args:
        text: Text to analyze
        source_tier: Source tier (tier1_breaking, etc.)
        
    Returns:
        Urgency modifier score
    """
    text_lower = text.lower()
    modifier = 0.0
    
    # Source tier modifier
    modifier += SOURCE_MODIFIERS.get(source_tier, 0.0)
    
    # Urgency keyword modifiers
    for keyword, multiplier in URGENCY_KEYWORDS.items():
        if keyword in text_lower:
            modifier += multiplier
            break  # Only count the highest urgency keyword
    
    return modifier


def classify_event(event: Event) -> ClassificationResult:
    """
    Classify an event across multiple categories with confidence scores.
    
    Args:
        event: Event object to classify
        
    Returns:
        Classification result with categories, keywords, and scores
    """
    # Combine title and content for analysis
    full_text = f"{event.title} {event.content or ''}"
    
    # Extract entities
    entities = extract_entities(full_text)
    
    # Classify against all categories
    category_scores = {}
    category_keywords = {}
    
    for category_name, category_config in CATEGORIES.items():
        # Calculate keyword score
        keywords = category_config.get("keywords", [])
        patterns = category_config.get("patterns", [])
        
        matched_keywords, keyword_score = calculate_keyword_score(full_text, keywords)
        pattern_score = calculate_pattern_score(full_text, patterns)
        
        # Combine scores (weighted)
        combined_score = (keyword_score * 0.7) + (pattern_score * 0.3)
        
        # Entity boost: if we found specific entities, boost confidence
        entity_boost = 0.0
        if entities:
            # More entities = higher confidence
            entity_count = sum(len(ent_list) for ent_list in entities.values())
            entity_boost = min(entity_count * 0.1, 0.3)  # Cap at 0.3
        
        # Final confidence score
        final_score = min(combined_score + entity_boost, 1.0)
        
        if matched_keywords or final_score > 0.1:  # Only include if we have matches
            category_scores[category_name] = final_score
            category_keywords[category_name] = matched_keywords
    
    # Determine primary category (highest confidence)
    if category_scores:
        primary_category = max(category_scores.items(), key=lambda x: x[1])[0]
        
        # Filter categories with significant confidence (>= 0.3 or top 3)
        significant_categories = []
        sorted_categories = sorted(category_scores.items(), key=lambda x: x[1], reverse=True)
        
        for cat, score in sorted_categories[:3]:  # Top 3
            if score >= 0.3:  # Minimum threshold
                significant_categories.append(cat)
    else:
        # No matches - assign to general category
        primary_category = "GENERAL"
        significant_categories = ["GENERAL"]
        category_scores = {"GENERAL": 0.1}
        category_keywords = {"GENERAL": []}
    
    # Calculate urgency score
    base_score = CATEGORIES.get(primary_category, {}).get("base_score", 5)
    urgency_modifier = calculate_urgency_modifiers(full_text, event.source_tier)
    
    # Time decay factor (recent events more urgent)
    time_diff_minutes = (datetime.now() - event.timestamp).total_seconds() / 60
    time_factor = 1.0
    if time_diff_minutes < 5:
        time_factor = 1.3
    elif time_diff_minutes < 15:
        time_factor = 1.1
    elif time_diff_minutes > 60:
        time_factor = 0.8
    
    urgency_score = base_score + urgency_modifier
    urgency_score *= time_factor
    urgency_score = max(1.0, min(urgency_score, 10.0))  # Clamp to 1-10
    
    return ClassificationResult(
        categories=significant_categories,
        matched_keywords=category_keywords,
        confidence_scores=category_scores,
        entities=entities,
        urgency_score=urgency_score,
        primary_category=primary_category
    )


def update_event_with_classification(event: Event, classification: ClassificationResult) -> Event:
    """
    Update an Event object with classification results.
    
    Args:
        event: Event to update
        classification: Classification result
        
    Returns:
        Updated event
    """
    # Update primary fields
    event.category = classification.primary_category
    event.urgency_score = classification.urgency_score
    
    # Combine all matched keywords
    all_keywords = []
    for keywords in classification.matched_keywords.values():
        all_keywords.extend(keywords)
    event.keywords_matched = list(set(all_keywords))  # Remove duplicates
    
    # Store classification details in raw_data
    if not hasattr(event, 'raw_data') or event.raw_data is None:
        event.raw_data = {}
    
    event.raw_data['classification'] = {
        'all_categories': classification.categories,
        'confidence_scores': classification.confidence_scores,
        'entities': classification.entities,
        'matched_keywords_by_category': classification.matched_keywords
    }
    
    return event


# Legacy compatibility functions
def classify_text(text: str) -> Optional[Tuple[str, List[str]]]:
    """
    Legacy function for backward compatibility.
    
    Args:
        text: Text to classify
        
    Returns:
        Tuple of (category, matched_keywords) if found, None otherwise
    """
    # Create a minimal event for classification
    from datetime import datetime
    temp_event = Event(
        id="temp",
        timestamp=datetime.now(),
        source="unknown",
        source_tier="tier3_general",
        category="unknown",
        title=text,
        content="",
        url=None,
        author=None,
        keywords_matched=[],
        urgency_score=5.0,
        is_duplicate=False,
        duplicate_of=None,
        raw_data={}
    )
    
    result = classify_event(temp_event)
    
    if result.categories:
        all_keywords = []
        for keywords in result.matched_keywords.values():
            all_keywords.extend(keywords)
        return result.primary_category, all_keywords
    
    return None


def extract_keywords_from_text(text: str) -> List[str]:
    """
    Legacy function: Extract all matching keywords from text across all categories.
    
    Args:
        text: Text to analyze
        
    Returns:
        List of all matched keywords
    """
    classification = classify_text(text)
    if classification:
        return classification[1]
    return []


def get_categories_for_keywords(keywords: List[str]) -> List[str]:
    """
    Legacy function: Get categories that contain the given keywords.
    
    Args:
        keywords: List of keywords to check
        
    Returns:
        List of categories that contain these keywords
    """
    categories = []
    keywords_lower = [kw.lower() for kw in keywords]
    
    for category, config in CATEGORIES.items():
        category_keywords = [kw.lower() for kw in config.get("keywords", [])]
        if any(kw in category_keywords for kw in keywords_lower):
            categories.append(category)
    
    return list(set(categories))