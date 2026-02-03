"""
Market mapper for Polymarket - maps events to potentially affected markets.
Implements keyword matching, fuzzy matching, and relevance scoring.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple
from datetime import datetime
import re
from difflib import SequenceMatcher
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.models import Event
from config.markets import (
    MARKET_MAPPING, 
    CATEGORY_MAPPING, 
    MARKET_DIRECTION_HINTS,
    FUZZY_MATCH_THRESHOLD,
    MIN_RELEVANCE_SCORE,
    MARKET_ALIASES
)


@dataclass
class MarketMatch:
    """Represents a match between an event and a Polymarket market."""
    market_slug: str
    relevance_score: float  # 0.0 - 1.0
    direction_hint: str  # "bullish" | "bearish" | "neutral"
    reasoning: str
    matched_keywords: List[str] = field(default_factory=list)
    match_type: str = "keyword"  # "keyword" | "category" | "fuzzy" | "entity"
    confidence: float = 1.0  # Additional confidence modifier


class MarketMapper:
    """Maps events to potentially affected Polymarket markets."""
    
    def __init__(self):
        """Initialize the market mapper with configuration."""
        self.market_mapping = MARKET_MAPPING
        self.category_mapping = CATEGORY_MAPPING
        self.direction_hints = MARKET_DIRECTION_HINTS
        self.fuzzy_threshold = FUZZY_MATCH_THRESHOLD
        self.min_relevance = MIN_RELEVANCE_SCORE
        self.market_aliases = MARKET_ALIASES
        
        # Build reverse lookup for faster searching
        self._build_reverse_lookup()
    
    def _build_reverse_lookup(self):
        """Build reverse lookup maps for efficient searching."""
        self.keyword_to_markets = {}
        self.market_to_keywords = {}
        
        # Build keyword → markets mapping
        for keyword, markets in self.market_mapping.items():
            keyword_lower = keyword.lower()
            self.keyword_to_markets[keyword_lower] = markets
            
            # Also store markets → keywords for reverse lookup
            for market in markets:
                if market not in self.market_to_keywords:
                    self.market_to_keywords[market] = []
                self.market_to_keywords[market].append(keyword_lower)
    
    def get_affected_markets(self, event: Event) -> List[MarketMatch]:
        """
        Return list of markets potentially affected by this event.
        
        Args:
            event: The event to analyze
            
        Returns:
            List of MarketMatch objects sorted by relevance score (desc)
        """
        matches = []
        
        # 1. Keyword-based matching
        keyword_matches = self._match_by_keywords(event)
        matches.extend(keyword_matches)
        
        # 2. Category-based matching
        category_matches = self._match_by_category(event)
        matches.extend(category_matches)
        
        # 3. Entity-based matching (if entities are available)
        if hasattr(event, 'entities') and event.entities:
            entity_matches = self._match_by_entities(event)
            matches.extend(entity_matches)
        
        # 4. Fuzzy matching on market names
        fuzzy_matches = self._match_by_fuzzy_search(event)
        matches.extend(fuzzy_matches)
        
        # 5. Deduplicate and merge scores
        final_matches = self._deduplicate_and_merge(matches)
        
        # 6. Filter by minimum relevance and sort
        filtered_matches = [m for m in final_matches if m.relevance_score >= self.min_relevance]
        filtered_matches.sort(key=lambda x: x.relevance_score, reverse=True)
        
        return filtered_matches
    
    def _match_by_keywords(self, event: Event) -> List[MarketMatch]:
        """Match event by keywords in title and content."""
        matches = []
        text = f"{event.title} {event.content}".lower()
        
        for keyword, markets in self.keyword_to_markets.items():
            # Check if keyword appears in text
            if self._keyword_matches(keyword, text):
                for market_slug in markets:
                    # Calculate relevance based on keyword prominence
                    relevance = self._calculate_keyword_relevance(keyword, text, event)
                    direction = self._determine_direction(market_slug, text, event)
                    
                    match = MarketMatch(
                        market_slug=market_slug,
                        relevance_score=relevance,
                        direction_hint=direction,
                        reasoning=f"Keyword '{keyword}' found in event text",
                        matched_keywords=[keyword],
                        match_type="keyword"
                    )
                    matches.append(match)
        
        return matches
    
    def _match_by_category(self, event: Event) -> List[MarketMatch]:
        """Match event by its category."""
        matches = []
        
        if event.category in self.category_mapping:
            markets = self.category_mapping[event.category]
            
            for market_slug in markets:
                # Category matches get lower base relevance than keyword matches
                relevance = self._calculate_category_relevance(event)
                direction = self._determine_direction(market_slug, f"{event.title} {event.content}".lower(), event)
                
                match = MarketMatch(
                    market_slug=market_slug,
                    relevance_score=relevance,
                    direction_hint=direction,
                    reasoning=f"Category match: {event.category}",
                    match_type="category"
                )
                matches.append(match)
        
        return matches
    
    def _match_by_entities(self, event: Event) -> List[MarketMatch]:
        """Match event by detected entities."""
        matches = []
        
        if not hasattr(event, 'entities') or not event.entities:
            return matches
        
        # Convert entities to lowercase for matching
        entity_text = " ".join(str(entity).lower() for entity in event.entities)
        
        for keyword, markets in self.keyword_to_markets.items():
            if keyword in entity_text:
                for market_slug in markets:
                    relevance = self._calculate_entity_relevance(keyword, event)
                    direction = self._determine_direction(market_slug, entity_text, event)
                    
                    match = MarketMatch(
                        market_slug=market_slug,
                        relevance_score=relevance,
                        direction_hint=direction,
                        reasoning=f"Entity match: {keyword}",
                        matched_keywords=[keyword],
                        match_type="entity"
                    )
                    matches.append(match)
        
        return matches
    
    def _match_by_fuzzy_search(self, event: Event) -> List[MarketMatch]:
        """Match using fuzzy string matching on market names."""
        matches = []
        text = f"{event.title} {event.content}".lower()
        
        # Extract potential market-related phrases
        words = re.findall(r'\b\w+\b', text)
        phrases = []
        
        # Create 1-3 word phrases for fuzzy matching
        for i in range(len(words)):
            phrases.append(words[i])
            if i < len(words) - 1:
                phrases.append(f"{words[i]} {words[i+1]}")
            if i < len(words) - 2:
                phrases.append(f"{words[i]} {words[i+1]} {words[i+2]}")
        
        # Check against market aliases and slugs
        all_markets = set()
        for markets in self.market_mapping.values():
            all_markets.update(markets)
        
        for phrase in phrases:
            for market_slug in all_markets:
                # Check against market slug
                similarity = SequenceMatcher(None, phrase, market_slug).ratio()
                
                if similarity >= self.fuzzy_threshold:
                    relevance = similarity * 0.6  # Fuzzy matches get lower base score
                    direction = self._determine_direction(market_slug, text, event)
                    
                    match = MarketMatch(
                        market_slug=market_slug,
                        relevance_score=relevance,
                        direction_hint=direction,
                        reasoning=f"Fuzzy match: '{phrase}' ~ '{market_slug}' (similarity: {similarity:.2f})",
                        match_type="fuzzy",
                        confidence=similarity
                    )
                    matches.append(match)
                
                # Check against aliases
                for alias, canonical_slug in self.market_aliases.items():
                    if canonical_slug == market_slug:
                        alias_similarity = SequenceMatcher(None, phrase, alias).ratio()
                        if alias_similarity >= self.fuzzy_threshold:
                            relevance = alias_similarity * 0.7
                            direction = self._determine_direction(market_slug, text, event)
                            
                            match = MarketMatch(
                                market_slug=market_slug,
                                relevance_score=relevance,
                                direction_hint=direction,
                                reasoning=f"Alias match: '{phrase}' ~ '{alias}' (similarity: {alias_similarity:.2f})",
                                match_type="fuzzy",
                                confidence=alias_similarity
                            )
                            matches.append(match)
        
        return matches
    
    def _keyword_matches(self, keyword: str, text: str) -> bool:
        """Check if keyword matches in text (with word boundaries for single words)."""
        if " " in keyword:
            # Multi-word keyword - simple substring match
            return keyword in text
        else:
            # Single word - use word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(keyword) + r'\b'
            return bool(re.search(pattern, text, re.IGNORECASE))
    
    def _calculate_keyword_relevance(self, keyword: str, text: str, event: Event) -> float:
        """Calculate relevance score for keyword matches."""
        base_score = 0.8
        
        # Boost if keyword is in title vs content
        if keyword in event.title.lower():
            base_score += 0.15
        
        # Boost for exact matches
        if f" {keyword} " in f" {text} ":
            base_score += 0.05
        
        # Boost for multiple occurrences
        occurrences = text.count(keyword)
        if occurrences > 1:
            base_score += min(0.1, occurrences * 0.02)
        
        # Adjust based on event urgency
        if hasattr(event, 'urgency_score'):
            urgency_modifier = (event.urgency_score - 5) / 50  # -0.1 to +0.1
            base_score += urgency_modifier
        
        return min(1.0, base_score)
    
    def _calculate_category_relevance(self, event: Event) -> float:
        """Calculate relevance score for category matches."""
        base_score = 0.5  # Lower than keyword matches
        
        # Boost based on urgency
        if hasattr(event, 'urgency_score') and event.urgency_score >= 7:
            base_score += 0.2
        
        # Boost for tier 1 sources
        if hasattr(event, 'source_tier') and event.source_tier == "tier1_breaking":
            base_score += 0.15
        
        return min(1.0, base_score)
    
    def _calculate_entity_relevance(self, keyword: str, event: Event) -> float:
        """Calculate relevance score for entity matches."""
        base_score = 0.7  # Between keyword and category
        
        # Entity matches are generally high confidence
        if hasattr(event, 'urgency_score'):
            urgency_modifier = (event.urgency_score - 5) / 40
            base_score += urgency_modifier
        
        return min(1.0, base_score)
    
    def _determine_direction(self, market_slug: str, text: str, event: Event) -> str:
        """Determine market direction hint based on event sentiment and content."""
        direction = "neutral"  # Default
        
        # Check market-specific direction hints
        if market_slug in self.direction_hints:
            hints = self.direction_hints[market_slug]
            
            for signal, market_direction in hints.items():
                if signal.lower() in text:
                    direction = market_direction
                    break
        
        # General sentiment analysis
        bullish_terms = ["positive", "growth", "increase", "surge", "rally", "bullish", "optimistic", "success"]
        bearish_terms = ["negative", "decline", "decrease", "crash", "fall", "bearish", "pessimistic", "failure"]
        
        bullish_count = sum(1 for term in bullish_terms if term in text)
        bearish_count = sum(1 for term in bearish_terms if term in text)
        
        if bullish_count > bearish_count and bullish_count >= 2:
            direction = "bullish"
        elif bearish_count > bullish_count and bearish_count >= 2:
            direction = "bearish"
        
        return direction
    
    def _deduplicate_and_merge(self, matches: List[MarketMatch]) -> List[MarketMatch]:
        """Deduplicate matches and merge scores for the same market."""
        market_matches = {}
        
        for match in matches:
            slug = match.market_slug
            
            if slug in market_matches:
                # Merge with existing match
                existing = market_matches[slug]
                
                # Take the highest relevance score
                if match.relevance_score > existing.relevance_score:
                    existing.relevance_score = match.relevance_score
                    existing.direction_hint = match.direction_hint
                    existing.reasoning = f"{existing.reasoning}; {match.reasoning}"
                
                # Merge keywords
                existing.matched_keywords.extend(match.matched_keywords)
                existing.matched_keywords = list(set(existing.matched_keywords))
                
                # Update match type if we have a better one
                type_priority = {"keyword": 3, "entity": 2, "category": 1, "fuzzy": 0}
                if type_priority.get(match.match_type, 0) > type_priority.get(existing.match_type, 0):
                    existing.match_type = match.match_type
            else:
                market_matches[slug] = match
        
        return list(market_matches.values())


def get_affected_markets(event: Event) -> List[MarketMatch]:
    """
    Convenience function to get affected markets for an event.
    
    Args:
        event: The event to analyze
        
    Returns:
        List of MarketMatch objects sorted by relevance
    """
    mapper = MarketMapper()
    return mapper.get_affected_markets(event)


# Example usage for testing
if __name__ == "__main__":
    from datetime import datetime
    
    # Create a test event
    test_event = Event(
        id="test-1",
        timestamp=datetime.now(),
        source="reuters",
        source_tier="tier1_breaking",
        category="fed",
        title="Fed Chair Powell Signals Potential Rate Cut in March",
        content="Federal Reserve Chairman Jerome Powell indicated today that the central bank may consider cutting interest rates in March if inflation continues to moderate. The comments came during his speech at the Economic Club.",
        url="https://reuters.com/test",
        author="Reuters",
        keywords_matched=["fed", "jerome powell", "rate cut"],
        urgency_score=8.5,
        is_duplicate=False,
        duplicate_of=None,
        raw_data={}
    )
    
    # Test the mapper
    mapper = MarketMapper()
    matches = mapper.get_affected_markets(test_event)
    
    print(f"Found {len(matches)} market matches:")
    for match in matches:
        print(f"- {match.market_slug}: {match.relevance_score:.2f} ({match.direction_hint}) - {match.reasoning}")