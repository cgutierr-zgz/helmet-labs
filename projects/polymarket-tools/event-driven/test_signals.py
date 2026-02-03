#!/usr/bin/env python3
"""
Test script for signal generation functionality.
Tests various scenarios and edge cases for the signal generator.
"""
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from src.models import Event, Signal
from src.intelligence.signals import (
    analyze_event_sentiment, 
    calculate_confidence,
    calculate_expected_price_move,
    generate_signal,
    filter_signals,
    get_signal_summary
)
from src.intelligence.mapper import MarketMatch
from src.fetchers.polymarket import MarketPrice


def create_test_event(title: str, content: str, urgency: float = 7.0, source_tier: str = "tier1_breaking") -> Event:
    """Create a test event with given parameters."""
    return Event(
        id=f"test-{hash(title) % 10000}",
        timestamp=datetime.now(),
        source="test_source",
        source_tier=source_tier,
        category="test",
        title=title,
        content=content,
        url="https://test.com",
        author="Test Author",
        keywords_matched=[],
        urgency_score=urgency,
        is_duplicate=False,
        duplicate_of=None,
        raw_data={}
    )


def create_test_market_match(relevance: float = 0.8, direction: str = "neutral") -> MarketMatch:
    """Create a test market match with given parameters."""
    return MarketMatch(
        market_slug="test-market",
        relevance_score=relevance,
        direction_hint=direction,
        reasoning="Test market match",
        matched_keywords=["test"],
        match_type="keyword"
    )


def create_test_market_price(yes_price: float = 0.5, volume: float = 50000, liquidity: float = 25000, active: bool = True) -> MarketPrice:
    """Create a test market price with given parameters."""
    return MarketPrice(
        market_id="test-market-id",
        market_slug="test-market",
        question="Test market question?",
        yes_price=yes_price,
        no_price=1.0 - yes_price,
        volume=volume,
        liquidity=liquidity,
        last_updated=datetime.now(),
        is_active=active
    )


def test_bullish_sentiment():
    """Test bullish sentiment analysis."""
    print("=== Testing Bullish Sentiment ===")
    
    event = create_test_event(
        "Bitcoin Surges to New All-Time High", 
        "Bitcoin rallied to a new record high today, showing strong positive momentum with massive gains"
    )
    market_match = create_test_market_match(direction="bullish")
    
    sentiment = analyze_event_sentiment(event, market_match)
    print(f"Bullish event sentiment: {sentiment:.3f}")
    assert sentiment > 0.6, f"Expected bullish sentiment > 0.6, got {sentiment:.3f}"
    

def test_bearish_sentiment():
    """Test bearish sentiment analysis."""
    print("=== Testing Bearish Sentiment ===")
    
    event = create_test_event(
        "Market Crashes as Economic Data Disappoints",
        "Markets fell sharply today following negative economic data and concerns about recession"
    )
    market_match = create_test_market_match(direction="bearish")
    
    sentiment = analyze_event_sentiment(event, market_match)
    print(f"Bearish event sentiment: {sentiment:.3f}")
    assert sentiment < 0.4, f"Expected bearish sentiment < 0.4, got {sentiment:.3f}"


def test_confidence_factors():
    """Test confidence calculation with various factors."""
    print("=== Testing Confidence Factors ===")
    
    # High confidence scenario
    high_conf_event = create_test_event("Breaking: Major Announcement", "content", urgency=9.0, source_tier="tier1_breaking")
    high_conf_match = create_test_market_match(relevance=0.9)
    high_conf_price = create_test_market_price(volume=100000, liquidity=50000)
    
    high_confidence = calculate_confidence(high_conf_event, high_conf_match, high_conf_price)
    print(f"High confidence scenario: {high_confidence:.3f}")
    
    # Low confidence scenario
    low_conf_event = create_test_event("Minor Update", "content", urgency=3.0, source_tier="tier3_general")
    low_conf_match = create_test_market_match(relevance=0.3)
    low_conf_price = create_test_market_price(volume=1000, liquidity=500)
    
    low_confidence = calculate_confidence(low_conf_event, low_conf_match, low_conf_price)
    print(f"Low confidence scenario: {low_confidence:.3f}")
    
    assert high_confidence > low_confidence, "High confidence scenario should have higher score"


def test_price_movement_calculation():
    """Test expected price movement calculation."""
    print("=== Testing Price Movement ===")
    
    # Bullish event
    bullish_event = create_test_event("Positive News", "Very positive development with strong growth", urgency=8.0)
    market_price = create_test_market_price(yes_price=0.5)
    
    move = calculate_expected_price_move(0.8, bullish_event, market_price)  # 0.8 = bullish sentiment
    print(f"Bullish expected move: {move:+.1%}")
    assert move > 0, f"Expected positive move for bullish sentiment, got {move:+.1%}"
    
    # Bearish event  
    bearish_event = create_test_event("Negative News", "Very concerning development with major decline", urgency=8.0)
    
    move = calculate_expected_price_move(0.2, bearish_event, market_price)  # 0.2 = bearish sentiment
    print(f"Bearish expected move: {move:+.1%}")
    assert move < 0, f"Expected negative move for bearish sentiment, got {move:+.1%}"


def test_signal_generation():
    """Test complete signal generation."""
    print("=== Testing Signal Generation ===")
    
    # Create test data
    event = create_test_event(
        "Fed Announces Rate Cut",
        "Federal Reserve announces unexpected rate cut to boost economy", 
        urgency=8.5
    )
    market_match = create_test_market_match(relevance=0.85, direction="bullish")
    market_price = create_test_market_price(yes_price=0.6, volume=75000, liquidity=30000)
    
    signal = generate_signal(event, market_match, market_price)
    
    if signal:
        print(f"Generated signal:")
        print(f"  Direction: {signal.direction}")
        print(f"  Confidence: {signal.confidence:.3f}")
        print(f"  Current → Expected: {signal.current_price:.3f} → {signal.expected_price:.3f}")
        print(f"  Expected Return: {signal.expected_return:+.1%}")
        print(f"  Reasoning: {signal.reasoning}")
        
        # Validate signal properties
        assert signal.direction in ["BUY_YES", "BUY_NO", "HOLD"], f"Invalid direction: {signal.direction}"
        assert 0.0 <= signal.confidence <= 1.0, f"Invalid confidence: {signal.confidence}"
        assert 0.01 <= signal.expected_price <= 0.99, f"Invalid expected price: {signal.expected_price}"
        assert signal.market_id == market_price.market_id, "Market ID mismatch"
        assert signal.event_id == event.id, "Event ID mismatch"
        
        print("✅ Signal validation passed")
    else:
        print("❌ No signal generated")


def test_signal_filtering():
    """Test signal filtering functionality."""
    print("=== Testing Signal Filtering ===")
    
    # Create various signals with different confidence levels
    signals = []
    
    # High confidence signal
    high_signal = Signal(
        market_id="market1",
        direction="BUY_YES", 
        confidence=0.8,
        reasoning="High confidence test",
        current_price=0.5,
        expected_price=0.6,
        event_id="event1"
    )
    signals.append(high_signal)
    
    # Low confidence signal
    low_signal = Signal(
        market_id="market2", 
        direction="BUY_NO",
        confidence=0.2,
        reasoning="Low confidence test",
        current_price=0.7,
        expected_price=0.65,
        event_id="event2"
    )
    signals.append(low_signal)
    
    # HOLD signal with medium confidence
    hold_signal = Signal(
        market_id="market3",
        direction="HOLD",
        confidence=0.5,
        reasoning="Medium confidence HOLD",
        current_price=0.5,
        expected_price=0.5,
        event_id="event3"
    )
    signals.append(hold_signal)
    
    print(f"Original signals: {len(signals)}")
    
    filtered = filter_signals(signals, min_confidence=0.3)
    print(f"Filtered signals: {len(filtered)}")
    
    # Should only keep high confidence signal
    assert len(filtered) == 1, f"Expected 1 filtered signal, got {len(filtered)}"
    assert filtered[0].confidence == 0.8, "Should keep the high confidence signal"
    
    summary = get_signal_summary(filtered)
    print(f"Summary: {summary}")


def test_edge_cases():
    """Test edge cases and error handling."""
    print("=== Testing Edge Cases ===")
    
    # Extreme prices
    extreme_event = create_test_event("Test", "content")
    market_match = create_test_market_match()
    
    # Very high current price
    high_price_market = create_test_market_price(yes_price=0.95)
    sentiment = analyze_event_sentiment(extreme_event, market_match)
    move = calculate_expected_price_move(sentiment, extreme_event, high_price_market)
    print(f"Move for 95% price: {move:+.1%}")
    
    # Very low current price
    low_price_market = create_test_market_price(yes_price=0.05)
    move = calculate_expected_price_move(sentiment, extreme_event, low_price_market)
    print(f"Move for 5% price: {move:+.1%}")
    
    # Inactive market
    inactive_market = create_test_market_price(active=False)
    signal = generate_signal(extreme_event, market_match, inactive_market)
    if signal:
        print(f"Inactive market confidence: {signal.confidence:.3f}")
        assert signal.confidence < 0.5, "Inactive markets should have low confidence"
    else:
        print("No signal for inactive market (expected)")


def run_all_tests():
    """Run all test functions."""
    print("🧪 Running Signal Generator Tests\n")
    
    try:
        test_bullish_sentiment()
        print("✅ Bullish sentiment test passed\n")
        
        test_bearish_sentiment() 
        print("✅ Bearish sentiment test passed\n")
        
        test_confidence_factors()
        print("✅ Confidence factors test passed\n")
        
        test_price_movement_calculation()
        print("✅ Price movement test passed\n")
        
        test_signal_generation()
        print("✅ Signal generation test passed\n")
        
        test_signal_filtering()
        print("✅ Signal filtering test passed\n")
        
        test_edge_cases()
        print("✅ Edge cases test passed\n")
        
        print("🎉 All tests passed! Signal generator is working correctly.")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)