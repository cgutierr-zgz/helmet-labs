"""
Signal generation for Polymarket trading.
Generates trading signals based on event analysis and current market conditions.
"""
import sys
import os
import asyncio
from typing import List, Optional, Tuple, Dict
from datetime import datetime
import re
import math

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.models import Event, Signal
from src.intelligence.mapper import MarketMapper, MarketMatch
from src.fetchers.polymarket import fetch_market_prices, MarketPrice
from src.processors.classifier import classify_event, update_event_with_classification
from src.processors.scorer import calculate_score


# Signal generation constants
MIN_CONFIDENCE_THRESHOLD = 0.3  # Don't generate signals below this confidence
MAX_EXPECTED_PRICE_MOVE = 0.15   # Maximum 15% price move expectation
MIN_LIQUIDITY_THRESHOLD = 1000   # Minimum market liquidity to trade
DIRECTION_CONFIDENCE_THRESHOLD = 0.6  # Threshold for BUY vs HOLD decisions

# Sentiment keywords for price movement calculation
BULLISH_KEYWORDS = {
    'strong': 0.8, 'surge': 0.9, 'boom': 0.8, 'rally': 0.7, 'positive': 0.6,
    'growth': 0.7, 'increase': 0.6, 'rise': 0.6, 'up': 0.5, 'gains': 0.7,
    'optimistic': 0.6, 'bullish': 0.8, 'breakthrough': 0.8, 'success': 0.7,
    'approval': 0.7, 'passed': 0.7, 'signed': 0.6, 'confirmed': 0.6,
    'victory': 0.8, 'wins': 0.7, 'beating': 0.6, 'exceeds': 0.7
}

BEARISH_KEYWORDS = {
    'crash': 0.9, 'collapse': 0.9, 'plummet': 0.8, 'decline': 0.7, 'fall': 0.6,
    'negative': 0.6, 'drop': 0.6, 'down': 0.5, 'losses': 0.7, 'pessimistic': 0.6,
    'bearish': 0.8, 'failure': 0.8, 'crisis': 0.9, 'concern': 0.5, 'worry': 0.5,
    'rejection': 0.7, 'denied': 0.7, 'cancelled': 0.8, 'delayed': 0.6,
    'defeat': 0.8, 'loses': 0.7, 'missing': 0.6, 'below': 0.5
}

# Source reliability weights
SOURCE_RELIABILITY = {
    'tier1_breaking': 1.0,  # Reuters, AP, Bloomberg
    'tier2_reliable': 0.8,  # WSJ, NYT, major outlets
    'tier3_general': 0.6    # General sources
}


def analyze_event_sentiment(event: Event, market_match: MarketMatch) -> float:
    """
    Analyze sentiment of event text relative to market.
    
    Args:
        event: The event to analyze
        market_match: Market match info with direction hint
        
    Returns:
        Sentiment score from 0.0 (very bearish) to 1.0 (very bullish)
    """
    text = f"{event.title} {event.content}".lower()
    
    # Start with neutral sentiment
    sentiment = 0.5
    
    # Calculate keyword-based sentiment
    bullish_score = 0.0
    bearish_score = 0.0
    
    for keyword, strength in BULLISH_KEYWORDS.items():
        if keyword in text:
            bullish_score += strength * (text.count(keyword) * 0.5 + 0.5)  # Boost for repetition
    
    for keyword, strength in BEARISH_KEYWORDS.items():
        if keyword in text:
            bearish_score += strength * (text.count(keyword) * 0.5 + 0.5)
    
    # Normalize and combine scores
    max_score = max(bullish_score, bearish_score, 1.0)  # Prevent division by zero
    bullish_normalized = bullish_score / max_score
    bearish_normalized = bearish_score / max_score
    
    # Calculate final sentiment
    if bullish_score > bearish_score:
        sentiment = 0.5 + (bullish_normalized * 0.4)  # 0.5 to 0.9
    elif bearish_score > bullish_score:
        sentiment = 0.5 - (bearish_normalized * 0.4)  # 0.1 to 0.5
    # If equal or both zero, stay at 0.5 (neutral)
    
    # Apply market direction hint if available
    if market_match.direction_hint == "bullish":
        sentiment = min(0.9, sentiment + 0.1)
    elif market_match.direction_hint == "bearish":
        sentiment = max(0.1, sentiment - 0.1)
    
    # Boost sentiment based on event urgency
    urgency_boost = (event.urgency_score - 5) / 50  # -0.1 to +0.1
    sentiment = max(0.0, min(1.0, sentiment + urgency_boost))
    
    return sentiment


def calculate_expected_price_move(sentiment: float, event: Event, market_price: MarketPrice) -> float:
    """
    Calculate expected price movement based on sentiment and event impact.
    
    Args:
        sentiment: Sentiment score 0.0 - 1.0
        event: Event triggering the move
        market_price: Current market state
        
    Returns:
        Expected price move as percentage (positive = increase, negative = decrease)
    """
    # Base move calculation
    if sentiment > 0.5:
        # Bullish: move proportional to sentiment strength above neutral
        base_move = (sentiment - 0.5) * 2 * MAX_EXPECTED_PRICE_MOVE  # 0 to MAX_EXPECTED_PRICE_MOVE
    else:
        # Bearish: negative move proportional to sentiment strength below neutral
        base_move = (sentiment - 0.5) * 2 * MAX_EXPECTED_PRICE_MOVE  # -MAX_EXPECTED_PRICE_MOVE to 0
    
    # Adjust based on event urgency (higher urgency = bigger potential moves)
    urgency_multiplier = min(2.0, event.urgency_score / 5.0)  # 0.2x to 2.0x
    adjusted_move = base_move * urgency_multiplier
    
    # Reduce move if market is already at extreme prices (mean reversion)
    current_price = market_price.yes_price
    if current_price > 0.8 and adjusted_move > 0:  # Already high, reduce upside
        adjusted_move *= (1.0 - current_price) * 2  # Scale down by distance from 100%
    elif current_price < 0.2 and adjusted_move < 0:  # Already low, reduce downside
        adjusted_move *= current_price * 2  # Scale down by distance from 0%
    
    # Apply market liquidity factor (low liquidity = bigger moves)
    if market_price.liquidity > 0:
        liquidity_factor = max(0.5, min(2.0, 10000 / (market_price.liquidity + 1000)))
        adjusted_move *= liquidity_factor
    
    # Cap the maximum move
    return max(-MAX_EXPECTED_PRICE_MOVE, min(MAX_EXPECTED_PRICE_MOVE, adjusted_move))


def calculate_confidence(event: Event, market_match: MarketMatch, market_price: MarketPrice) -> float:
    """
    Calculate confidence score for the signal based on multiple factors.
    
    Args:
        event: Event data
        market_match: Market mapping data  
        market_price: Current market state
        
    Returns:
        Confidence score from 0.0 to 1.0
    """
    confidence_factors = []
    
    # 1. Source reliability (20% weight)
    source_reliability = SOURCE_RELIABILITY.get(event.source_tier, 0.5)
    confidence_factors.append(('source', source_reliability, 0.20))
    
    # 2. Market relevance (25% weight)
    relevance = market_match.relevance_score
    confidence_factors.append(('relevance', relevance, 0.25))
    
    # 3. Event urgency (20% weight)
    urgency_confidence = min(1.0, event.urgency_score / 10.0)
    confidence_factors.append(('urgency', urgency_confidence, 0.20))
    
    # 4. Market liquidity (15% weight)
    # Higher liquidity = more confidence (easier to execute)
    if market_price.liquidity > MIN_LIQUIDITY_THRESHOLD:
        liquidity_confidence = min(1.0, market_price.liquidity / 50000)  # Full confidence at $50k+
    else:
        liquidity_confidence = 0.3  # Low confidence for illiquid markets
    confidence_factors.append(('liquidity', liquidity_confidence, 0.15))
    
    # 5. Market activity (10% weight)
    # Higher volume = more market interest = higher confidence
    volume_confidence = min(1.0, market_price.volume / 100000) if market_price.volume > 0 else 0.3
    confidence_factors.append(('volume', volume_confidence, 0.10))
    
    # 6. Match quality (10% weight)
    match_confidence = market_match.confidence if hasattr(market_match, 'confidence') else 1.0
    confidence_factors.append(('match', match_confidence, 0.10))
    
    # Calculate weighted average
    total_confidence = sum(score * weight for _, score, weight in confidence_factors)
    
    # Apply penalties
    penalties = []
    
    # Penalty for very recent or very old events
    if hasattr(event, 'timestamp'):
        time_diff = (datetime.now() - event.timestamp).total_seconds() / 3600  # hours
        if time_diff > 24:  # Event is old
            penalties.append(0.8)  # 20% penalty
        elif time_diff < 0.5:  # Event is very recent (might be incomplete)
            penalties.append(0.9)  # 10% penalty
    
    # Penalty for inactive markets
    if not market_price.is_active:
        penalties.append(0.5)  # 50% penalty for inactive markets
    
    # Penalty for extreme current prices (less room to move)
    if market_price.yes_price > 0.85 or market_price.yes_price < 0.15:
        penalties.append(0.8)  # 20% penalty for extreme prices
    
    # Apply all penalties
    for penalty in penalties:
        total_confidence *= penalty
    
    return max(0.0, min(1.0, total_confidence))


def generate_signal(event: Event, market_match: MarketMatch, market_price: MarketPrice) -> Optional[Signal]:
    """
    Generate trading signal based on event and current market state.
    
    Args:
        event: Analyzed event
        market_match: Market match with relevance info
        market_price: Current market pricing data
        
    Returns:
        Signal object or None if confidence is too low
    """
    # Calculate sentiment and expected move
    sentiment = analyze_event_sentiment(event, market_match)
    expected_move = calculate_expected_price_move(sentiment, event, market_price)
    confidence = calculate_confidence(event, market_match, market_price)
    
    # Filter out low-confidence signals
    if confidence < MIN_CONFIDENCE_THRESHOLD:
        return None
    
    # Determine direction based on sentiment and confidence
    if sentiment > DIRECTION_CONFIDENCE_THRESHOLD and confidence > 0.5:
        direction = "BUY_YES"
    elif sentiment < (1.0 - DIRECTION_CONFIDENCE_THRESHOLD) and confidence > 0.5:
        direction = "BUY_NO"
    else:
        direction = "HOLD"
    
    # Calculate expected price
    current_price = market_price.yes_price
    expected_price = current_price + expected_move
    expected_price = max(0.01, min(0.99, expected_price))  # Keep in valid range
    
    # Build reasoning
    reasoning_parts = [
        f"Event sentiment: {sentiment:.2f} ({'bullish' if sentiment > 0.5 else 'bearish' if sentiment < 0.5 else 'neutral'})",
        f"Market relevance: {market_match.relevance_score:.2f}",
        f"Expected move: {expected_move:+.1%}",
        f"Urgency: {event.urgency_score}/10",
        f"Source: {event.source_tier}"
    ]
    
    if market_match.direction_hint != "neutral":
        reasoning_parts.append(f"Direction hint: {market_match.direction_hint}")
    
    reasoning = "; ".join(reasoning_parts)
    
    return Signal(
        market_id=market_price.market_id,
        direction=direction,
        confidence=confidence,
        reasoning=reasoning,
        current_price=current_price,
        expected_price=expected_price,
        event_id=event.id,
        timestamp=datetime.now()
    )


async def process_event_to_signals(event: Event) -> List[Signal]:
    """
    Complete pipeline: Event → Classification → Scoring → Mapping → Price Fetch → Signals
    
    Args:
        event: Raw event to process
        
    Returns:
        List of generated signals
    """
    signals = []
    
    try:
        # Step 1: Classify event if not already classified
        if not hasattr(event, 'category') or not event.category:
            classification_result = classify_event(event)
            if classification_result:
                event = update_event_with_classification(event, classification_result)
        
        # Step 2: Score event if not already scored  
        if not hasattr(event, 'urgency_score') or event.urgency_score == 0:
            urgency_score = calculate_score(event)
            event.urgency_score = float(urgency_score)
        
        # Step 3: Map event to affected markets
        mapper = MarketMapper()
        market_matches = mapper.get_affected_markets(event)
        
        if not market_matches:
            return signals
        
        # Step 4: Fetch current prices for matched markets
        market_slugs = [match.market_slug for match in market_matches]
        market_prices = await fetch_market_prices(market_slugs)
        
        # Create slug → price mapping
        price_lookup = {price.market_slug: price for price in market_prices}
        
        # Step 5: Generate signals for each market match
        for market_match in market_matches:
            if market_match.market_slug in price_lookup:
                market_price = price_lookup[market_match.market_slug]
                
                signal = generate_signal(event, market_match, market_price)
                if signal:
                    signals.append(signal)
        
        return signals
        
    except Exception as e:
        print(f"Error processing event {event.id} to signals: {e}")
        return []


def filter_signals(signals: List[Signal], min_confidence: float = MIN_CONFIDENCE_THRESHOLD) -> List[Signal]:
    """
    Filter signals based on confidence and other quality criteria.
    
    Args:
        signals: List of signals to filter
        min_confidence: Minimum confidence threshold
        
    Returns:
        Filtered list of high-quality signals
    """
    filtered = []
    
    for signal in signals:
        # Skip low confidence signals
        if signal.confidence < min_confidence:
            continue
        
        # Skip HOLD signals with low confidence (they're not actionable)
        if signal.direction == "HOLD" and signal.confidence < 0.6:
            continue
        
        # Skip signals with minimal expected moves
        expected_return = abs(signal.expected_return)
        if expected_return < 0.02:  # Less than 2% expected move
            continue
        
        filtered.append(signal)
    
    # Sort by confidence descending
    filtered.sort(key=lambda s: s.confidence, reverse=True)
    
    return filtered


def get_signal_summary(signals: List[Signal]) -> Dict:
    """
    Get summary statistics for a list of signals.
    
    Args:
        signals: List of signals
        
    Returns:
        Dictionary with summary stats
    """
    if not signals:
        return {
            'total_signals': 0,
            'buy_yes': 0,
            'buy_no': 0,
            'hold': 0,
            'avg_confidence': 0.0,
            'max_expected_return': 0.0
        }
    
    direction_counts = {'BUY_YES': 0, 'BUY_NO': 0, 'HOLD': 0}
    confidences = []
    expected_returns = []
    
    for signal in signals:
        direction_counts[signal.direction] += 1
        confidences.append(signal.confidence)
        expected_returns.append(abs(signal.expected_return))
    
    return {
        'total_signals': len(signals),
        'buy_yes': direction_counts['BUY_YES'],
        'buy_no': direction_counts['BUY_NO'],
        'hold': direction_counts['HOLD'],
        'avg_confidence': sum(confidences) / len(confidences),
        'max_expected_return': max(expected_returns) if expected_returns else 0.0
    }


# Example usage and testing
if __name__ == "__main__":
    async def test_signal_generation():
        """Test signal generation with a sample event."""
        # Create test event with simpler content
        test_event = Event(
            id="test-signal-1",
            timestamp=datetime.now(),
            source="reuters",
            source_tier="tier1_breaking",
            category="fed",
            title="Trump announces major policy change",
            content="Former President Trump announced significant policy changes that could affect multiple markets.",
            url="https://reuters.com/test",
            author="Reuters",
            keywords_matched=["trump", "policy"],
            urgency_score=8.0,
            is_duplicate=False,
            duplicate_of=None,
            raw_data={}
        )
        
        # Create a mock market match for testing
        from src.intelligence.mapper import MarketMatch
        test_market_match = MarketMatch(
            market_slug="test-market",
            relevance_score=0.8,
            direction_hint="bullish",
            reasoning="Test match for signal generation",
            matched_keywords=["trump"],
            match_type="keyword"
        )
        
        # Create a mock market price
        from src.fetchers.polymarket import MarketPrice
        test_market_price = MarketPrice(
            market_id="test-market-id",
            market_slug="test-market",
            question="Test market question?",
            yes_price=0.6,
            no_price=0.4,
            volume=50000.0,
            liquidity=25000.0,
            last_updated=datetime.now(),
            is_active=True
        )
        
        print("Testing individual signal generation...")
        signal = generate_signal(test_event, test_market_match, test_market_price)
        
        if signal:
            print(f"\nGenerated signal:")
            print(f"- Market: {signal.market_id}")
            print(f"  Direction: {signal.direction}")
            print(f"  Confidence: {signal.confidence:.3f}")
            print(f"  Current: {signal.current_price:.3f} → Expected: {signal.expected_price:.3f}")
            print(f"  Expected Return: {signal.expected_return:+.1%}")
            print(f"  Reasoning: {signal.reasoning}")
            print()
        else:
            print("No signal generated (confidence too low)")
        
        print("\nTesting sentiment analysis...")
        sentiment = analyze_event_sentiment(test_event, test_market_match)
        print(f"Event sentiment: {sentiment:.3f}")
        
        confidence = calculate_confidence(test_event, test_market_match, test_market_price)
        print(f"Signal confidence: {confidence:.3f}")
        
        expected_move = calculate_expected_price_move(sentiment, test_event, test_market_price)
        print(f"Expected price move: {expected_move:+.1%}")
        print(f"Current price: {test_market_price.yes_price:.3f}")
        print(f"Expected price: {test_market_price.yes_price + expected_move:.3f}")
        
        # Commented out full pipeline test to avoid API calls
        # print("Testing signal generation pipeline...")
        # signals = await process_event_to_signals(test_event)
        # 
        # if signals:
        #     print(f"\nGenerated {len(signals)} signals:")
        #     for signal in signals:
        #         print(f"- Market: {signal.market_id}")
        #         print(f"  Direction: {signal.direction}")
        #         print(f"  Confidence: {signal.confidence:.2f}")
        #         print(f"  Current: {signal.current_price:.3f} → Expected: {signal.expected_price:.3f}")
        #         print(f"  Expected Return: {signal.expected_return:+.1%}")
        #         print(f"  Reasoning: {signal.reasoning}")
        #         print()
        #     
        #     summary = get_signal_summary(signals)
        #     print("Summary:")
        #     for key, value in summary.items():
        #         print(f"  {key}: {value}")
        # else:
        #     print("No signals generated")
    
    # Run the test
    asyncio.run(test_signal_generation())