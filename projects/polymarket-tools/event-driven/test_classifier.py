#!/usr/bin/env python3
"""
Test script for the new intelligent classifier.
"""
from datetime import datetime
from src.models import Event
from src.processors.classifier import classify_event, update_event_with_classification

def test_classifier():
    """Test the new classifier with sample events."""
    
    # Test events
    test_events = [
        {
            "title": "BREAKING: Fed cuts rates by 50 basis points in emergency move",
            "content": "The Federal Reserve announced an emergency 50 basis point rate cut following FOMC meeting. Powell says inflation concerns driving policy.",
            "expected_category": "FED_MONETARY"
        },
        {
            "title": "Trump announces new executive order on immigration enforcement",
            "content": "President Trump signed executive order expanding deportation programs. White House says mass deportations to begin next week.",
            "expected_category": "POLITICS_US"
        },
        {
            "title": "Bitcoin hits $100K as SEC approves spot ETF applications",
            "content": "Bitcoin surges to new all-time high of $100,000 after SEC approves multiple spot Bitcoin ETF applications. Crypto markets rally.",
            "expected_category": "CRYPTO"
        },
        {
            "title": "Russia launches major offensive in Ukraine, NATO responds",
            "content": "Russia launched largest military offensive since invasion began. Ukraine reports massive missile attacks. NATO calls emergency meeting.",
            "expected_category": "GEOPOLITICS"
        },
        {
            "title": "Rockstar Games announces GTA 6 release date for 2025",
            "content": "After years of speculation, Rockstar finally confirms Grand Theft Auto 6 will release in Q2 2025. Gaming industry stocks surge.",
            "expected_category": "ENTERTAINMENT"
        }
    ]
    
    print("🧪 Testing Intelligent Event Classifier")
    print("=" * 50)
    
    for i, test_data in enumerate(test_events, 1):
        # Create test event
        event = Event(
            id=f"test_{i}",
            timestamp=datetime.now(),
            source="test",
            source_tier="tier1_breaking",
            category="unknown",
            title=test_data["title"],
            content=test_data["content"],
            url=None,
            author=None,
            keywords_matched=[],
            urgency_score=5.0,
            is_duplicate=False,
            duplicate_of=None,
            raw_data={}
        )
        
        # Classify event
        print(f"\n📝 Test Event {i}:")
        print(f"Title: {event.title}")
        print(f"Expected: {test_data['expected_category']}")
        
        result = classify_event(event)
        
        print(f"Primary Category: {result.primary_category}")
        print(f"All Categories: {result.categories}")
        print(f"Confidence Scores: {result.confidence_scores}")
        print(f"Keywords Matched: {result.matched_keywords}")
        print(f"Entities Found: {result.entities}")
        print(f"Urgency Score: {result.urgency_score:.1f}/10")
        
        # Check if classification is correct
        if result.primary_category == test_data["expected_category"]:
            print("✅ Classification CORRECT")
        else:
            print("❌ Classification INCORRECT")
        
        # Update event with classification
        updated_event = update_event_with_classification(event, result)
        print(f"Updated Event Category: {updated_event.category}")
        print(f"Updated Keywords: {updated_event.keywords_matched}")
    
    print("\n🎉 Classifier test complete!")

if __name__ == "__main__":
    test_classifier()