"""
Event classification system.
Handles categorization and keyword matching for events.
"""
from typing import List, Tuple, Optional
from config.settings import KEYWORDS

def classify_text(text: str) -> Optional[Tuple[str, List[str]]]:
    """
    Classify text against keyword categories.
    
    Args:
        text: Text to classify (should be lowercase)
        
    Returns:
        Tuple of (category, matched_keywords) if found, None otherwise
    """
    text_lower = text.lower()
    
    for category, keywords in KEYWORDS.items():
        matched = [kw for kw in keywords if kw in text_lower]
        if matched:
            return category, matched
    
    return None

def extract_keywords_from_text(text: str) -> List[str]:
    """
    Extract all matching keywords from text across all categories.
    
    Args:
        text: Text to analyze
        
    Returns:
        List of all matched keywords
    """
    text_lower = text.lower()
    all_keywords = []
    
    for keywords in KEYWORDS.values():
        matched = [kw for kw in keywords if kw in text_lower]
        all_keywords.extend(matched)
    
    return list(set(all_keywords))  # Remove duplicates

def get_categories_for_keywords(keywords: List[str]) -> List[str]:
    """
    Get categories that contain the given keywords.
    
    Args:
        keywords: List of keywords to check
        
    Returns:
        List of categories that contain these keywords
    """
    categories = []
    keywords_lower = [kw.lower() for kw in keywords]
    
    for category, category_keywords in KEYWORDS.items():
        if any(kw in category_keywords for kw in keywords_lower):
            categories.append(category)
    
    return list(set(categories))