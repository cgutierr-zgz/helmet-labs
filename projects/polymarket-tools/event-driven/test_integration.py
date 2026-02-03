#!/usr/bin/env python3
"""
Integration test between classifier and advanced scorer.
Verifies TASK-005 classifier works with TASK-006 scorer improvements.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path  
sys.path.append(str(Path(__file__).parent / "src"))

from src.models import Event
from src.processors.classifier import classify_event, update_event_with_classification
from src.processors.scorer import calculate_score, explain_score

def create_test_event(title: str, content: str = "", age_minutes: int = 5) -> Event:
    """Create a test event for integration testing."""
    timestamp = datetime.now() - timedelta(minutes=age_minutes)
    
    return Event(
        id=f"test_{hash(title) % 10000}",
        timestamp=timestamp,
        source="rss",
        source_tier="tier1_breaking",
        category="UNKNOWN",  # Will be set by classifier
        title=title,
        content=content,
        url="https://test.com/news",
        author="Test Author",
        keywords_matched=[],
        urgency_score=5.0,
        is_duplicate=False,
        duplicate_of=None,
        raw_data={}
    )

def test_fed_event():
    """Test Fed-related event classification and scoring."""
    print("🔍 Testing Fed Event Integration...")
    
    event = create_test_event(
        title="BREAKING: Federal Reserve announces emergency 0.75% rate cut",
        content="The Federal Reserve announced an emergency 75 basis points rate cut to combat economic uncertainty.",
        age_minutes=2
    )
    
    # Step 1: Classify the event
    classification = classify_event(event)
    event = update_event_with_classification(event, classification)
    
    print(f"   Classified as: {event.category}")
    print(f"   Matched keywords: {event.keywords_matched}")
    
    # Step 2: Score the event  
    score = calculate_score(event)
    print(f"   Final score: {score}/10")
    
    # Step 3: Get explanation
    explanation = explain_score(event)
    print(f"   Explanation:\n{explanation}")
    
    print()

def test_crypto_event():
    """Test crypto-related event classification and scoring."""
    print("🔍 Testing Crypto Event Integration...")
    
    event = create_test_event(
        title="Bitcoin surges past $100,000 as SEC approves new ETF",
        content="Bitcoin price jumped 15% to reach $102,500 following SEC approval of a new spot bitcoin ETF.",
        age_minutes=8
    )
    
    # Classify and score
    classification = classify_event(event)
    event = update_event_with_classification(event, classification)
    score = calculate_score(event)
    
    print(f"   Classified as: {event.category}")
    print(f"   Final score: {score}/10")
    
    explanation = explain_score(event)
    print(f"   Explanation:\n{explanation}")
    
    print()

def test_geopolitics_event():
    """Test geopolitics event classification and scoring."""
    print("🔍 Testing Geopolitics Event Integration...")
    
    event = create_test_event(
        title="Ukraine and Russia announce ceasefire agreement",
        content="Ukrainian President Zelensky and Russian officials have reached a preliminary ceasefire agreement after months of negotiations.",
        age_minutes=30
    )
    
    # Classify and score
    classification = classify_event(event)
    event = update_event_with_classification(event, classification)
    score = calculate_score(event)
    
    print(f"   Classified as: {event.category}")
    print(f"   Final score: {score}/10")
    
    explanation = explain_score(event)
    print(f"   Explanation:\n{explanation}")
    
    print()

def test_low_priority_event():
    """Test low priority event classification and scoring."""
    print("🔍 Testing Low Priority Event Integration...")
    
    event = create_test_event(
        title="Gaming industry reports quarterly earnings",
        content="Various gaming companies released their Q4 earnings reports showing mixed results.",
        age_minutes=120  # Old news
    )
    
    # Classify and score
    classification = classify_event(event) 
    event = update_event_with_classification(event, classification)
    score = calculate_score(event)
    
    print(f"   Classified as: {event.category}")
    print(f"   Final score: {score}/10")
    
    explanation = explain_score(event)
    print(f"   Explanation:\n{explanation}")
    
    print()

def test_multiple_categories():
    """Test event that could match multiple categories."""
    print("🔍 Testing Multi-Category Event Integration...")
    
    event = create_test_event(
        title="Trump announces Bitcoin will be part of US strategic reserves",
        content="Former President Trump announced that Bitcoin will be included in US strategic reserves, impacting both crypto and political markets.",
        age_minutes=1
    )
    
    # Classify and score
    classification = classify_event(event)
    event = update_event_with_classification(event, classification)
    score = calculate_score(event)
    
    print(f"   Classified as: {event.category}")
    print(f"   All categories: {classification.categories}")
    print(f"   Final score: {score}/10")
    
    explanation = explain_score(event)
    print(f"   Explanation:\n{explanation}")
    
    print()

def test_pipeline_consistency():
    """Test that classification and scoring work consistently."""
    print("🔍 Testing Pipeline Consistency...")
    
    events = [
        "Breaking: Fed raises rates by 2%",
        "Bitcoin crashes 30% after regulatory news",
        "Russia announces military exercises near Taiwan",
        "New GTA 6 trailer released by Rockstar Games",
        "Minor weather update for tomorrow"
    ]
    
    results = []
    for title in events:
        event = create_test_event(title)
        
        # Full pipeline
        classification = classify_event(event)
        event = update_event_with_classification(event, classification)
        score = calculate_score(event)
        
        results.append((title[:40], event.category, score))
    
    # Sort by score (highest first)
    results.sort(key=lambda x: x[2], reverse=True)
    
    print("   Event Rankings (by score):")
    for i, (title, category, score) in enumerate(results, 1):
        print(f"   {i}. [{score}/10] {category}: {title}")
    
    print()

def main():
    """Run integration tests."""
    print("🚀 Testing Classifier + Scorer Integration (TASK-005 + TASK-006)")
    print("=" * 70)
    
    test_fed_event()
    test_crypto_event()
    test_geopolitics_event()
    test_low_priority_event()
    test_multiple_categories()
    test_pipeline_consistency()
    
    print("✅ Integration tests completed!")

if __name__ == "__main__":
    main()