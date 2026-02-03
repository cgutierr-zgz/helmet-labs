#!/usr/bin/env python3
"""
Test script for the advanced scorer implementation.
Verifies all scoring modifiers work according to PRD.md spec.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.models import Event
from src.processors.scorer import calculate_score, calculate_score_with_breakdown, explain_score

def create_test_event(
    title: str = "Test event",
    content: str = "",
    category: str = "POLITICS_US",
    source: str = "rss",
    feed: str = "test.com",
    account: str = None,
    age_minutes: int = 10
) -> Event:
    """Create a test event with specified parameters."""
    timestamp = datetime.now() - timedelta(minutes=age_minutes)
    
    return Event(
        id="test_123",
        timestamp=timestamp,
        source=source,
        source_tier="tier3_general",
        category=category,
        title=title,
        content=content,
        url="https://test.com/news",
        author="Test Author",
        keywords_matched=["test"],
        urgency_score=5.0,
        is_duplicate=False,
        duplicate_of=None,
        raw_data={},
        headline=title,
        feed=feed,
        account=account
    )

def test_base_scoring():
    """Test base category scoring."""
    print("🔍 Testing Base Category Scoring...")
    
    # Test different categories
    categories = ["POLITICS_US", "FED_MONETARY", "GEOPOLITICS", "CRYPTO", "ENTERTAINMENT"]
    for category in categories:
        event = create_test_event(category=category)
        score = calculate_score(event)
        print(f"   {category}: Base score = {score}")
    
    print()

def test_source_reliability():
    """Test source reliability modifiers."""
    print("🔍 Testing Source Reliability Modifiers...")
    
    # Test Tier 1 source
    event = create_test_event(
        title="Fed announces rate cut",
        category="FED_MONETARY",
        source="rss",
        feed="https://feeds.reuters.com/reuters/topNews"
    )
    score, breakdown = calculate_score_with_breakdown(event)
    print(f"   Reuters (Tier 1): {score}/10 (modifier: +{breakdown.source_reliability_modifier})")
    
    # Test Tier 2 source
    event = create_test_event(
        title="Fed announces rate cut", 
        category="FED_MONETARY",
        source="rss",
        feed="https://thehill.com/feed"
    )
    score, breakdown = calculate_score_with_breakdown(event)
    print(f"   The Hill (Tier 2): {score}/10 (modifier: +{breakdown.source_reliability_modifier})")
    
    # Test Tier 3 source
    event = create_test_event(
        title="Fed announces rate cut",
        category="FED_MONETARY", 
        source="rss",
        feed="https://unknown-blog.com/feed"
    )
    score, breakdown = calculate_score_with_breakdown(event)
    print(f"   Unknown Blog (Tier 3): {score}/10 (modifier: +{breakdown.source_reliability_modifier})")
    
    print()

def test_recency_modifiers():
    """Test recency-based scoring modifiers."""
    print("🔍 Testing Recency Modifiers...")
    
    # Very fresh (< 5 min)
    event = create_test_event(title="Breaking: Fed cuts rates", age_minutes=2)
    score, breakdown = calculate_score_with_breakdown(event)
    print(f"   2 minutes old: {score}/10 (modifier: +{breakdown.recency_modifier})")
    
    # Fresh (< 15 min)
    event = create_test_event(title="Breaking: Fed cuts rates", age_minutes=10)
    score, breakdown = calculate_score_with_breakdown(event)
    print(f"   10 minutes old: {score}/10 (modifier: +{breakdown.recency_modifier})")
    
    # Normal (15-60 min)
    event = create_test_event(title="Breaking: Fed cuts rates", age_minutes=30)
    score, breakdown = calculate_score_with_breakdown(event)
    print(f"   30 minutes old: {score}/10 (modifier: {breakdown.recency_modifier})")
    
    # Old (> 60 min)
    event = create_test_event(title="Breaking: Fed cuts rates", age_minutes=90)
    score, breakdown = calculate_score_with_breakdown(event)
    print(f"   90 minutes old: {score}/10 (modifier: {breakdown.recency_modifier})")
    
    print()

def test_breaking_news_detection():
    """Test breaking news keyword detection."""
    print("🔍 Testing Breaking News Detection...")
    
    # Regular news
    event = create_test_event(title="Fed considers rate cut next month")
    score, breakdown = calculate_score_with_breakdown(event)
    print(f"   Regular news: {score}/10 (breaking: +{breakdown.breaking_bonus})")
    
    # Breaking news
    event = create_test_event(title="BREAKING: Fed announces emergency rate cut")
    score, breakdown = calculate_score_with_breakdown(event)
    print(f"   Breaking news: {score}/10 (breaking: +{breakdown.breaking_bonus})")
    
    # Urgent news
    event = create_test_event(title="URGENT: Fed chair Powell announces immediate action")
    score, breakdown = calculate_score_with_breakdown(event)
    print(f"   Urgent news: {score}/10 (breaking: +{breakdown.breaking_bonus})")
    
    print()

def test_numbers_detection():
    """Test numerical data detection."""
    print("🔍 Testing Numbers Detection...")
    
    # No numbers
    event = create_test_event(title="Fed discusses policy changes")
    score, breakdown = calculate_score_with_breakdown(event)
    print(f"   No numbers: {score}/10 (numbers: +{breakdown.numbers_bonus})")
    
    # With specific numbers
    event = create_test_event(title="Fed cuts rates by 0.5% or 50 basis points")
    score, breakdown = calculate_score_with_breakdown(event)
    print(f"   With numbers: {score}/10 (numbers: +{breakdown.numbers_bonus})")
    
    # With large numbers
    event = create_test_event(title="Bitcoin hits $100k milestone with $2.1 billion volume")
    score, breakdown = calculate_score_with_breakdown(event)
    print(f"   With large numbers: {score}/10 (numbers: +{breakdown.numbers_bonus})")
    
    print()

def test_score_explanation():
    """Test score explanation functionality."""
    print("🔍 Testing Score Explanation...")
    
    # Complex event with multiple modifiers
    event = create_test_event(
        title="BREAKING: Fed announces emergency 0.75% rate cut",
        category="FED_MONETARY",
        source="rss", 
        feed="https://feeds.reuters.com/reuters/topNews",
        age_minutes=3
    )
    
    explanation = explain_score(event)
    print(f"Complex Event Explanation:")
    print(explanation)
    print()

def test_edge_cases():
    """Test edge cases and score clamping."""
    print("🔍 Testing Edge Cases...")
    
    # Maximum possible score scenario
    event = create_test_event(
        title="BREAKING: Fed announces emergency 2% rate cut immediately",
        category="FED_MONETARY",  # base score 9
        source="rss",
        feed="https://feeds.reuters.com/reuters/topNews",  # +2 tier1
        age_minutes=1  # +2 recency, +2 breaking, +1 numbers
    )
    score = calculate_score(event)
    print(f"   Maximum scenario: {score}/10 (should be clamped to 10)")
    
    # Minimum score scenario
    event = create_test_event(
        title="old entertainment news",
        category="ENTERTAINMENT",  # base score 5
        source="rss", 
        feed="https://unknown.com",  # +0 tier3
        age_minutes=120  # -2 recency
    )
    score = calculate_score(event)
    print(f"   Minimum scenario: {score}/10 (should be clamped to 1)")
    
    print()

def main():
    """Run all tests."""
    print("🚀 Testing Advanced Scorer Implementation")
    print("=" * 50)
    
    test_base_scoring()
    test_source_reliability() 
    test_recency_modifiers()
    test_breaking_news_detection()
    test_numbers_detection()
    test_score_explanation()
    test_edge_cases()
    
    print("✅ All tests completed!")

if __name__ == "__main__":
    main()