#!/usr/bin/env python3
"""
Demo script showcasing the complete signal generation pipeline.
Shows how events flow through classification → scoring → mapping → signal generation.
"""
import sys
import os
import asyncio
from datetime import datetime
from typing import List

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from src.models import Event
from src.intelligence.signals import process_event_to_signals, filter_signals, get_signal_summary


def create_demo_events() -> List[Event]:
    """Create a variety of demo events to showcase different scenarios."""
    events = []
    
    # 1. High-impact Fed event
    events.append(Event(
        id="demo-fed-001",
        timestamp=datetime.now(),
        source="reuters",
        source_tier="tier1_breaking",
        category="fed",
        title="Fed Chair Powell Signals Emergency Rate Cut Following Market Turmoil",
        content="Federal Reserve Chairman Jerome Powell announced an emergency 0.75% rate cut in response to market volatility, stating the Fed is prepared to take further action if needed.",
        url="https://reuters.com/fed-emergency-cut",
        author="Reuters Economic Team",
        keywords_matched=["fed", "powell", "rate cut", "emergency"],
        urgency_score=9.5,
        is_duplicate=False,
        duplicate_of=None,
        raw_data={}
    ))
    
    # 2. Trump policy announcement
    events.append(Event(
        id="demo-trump-001",
        timestamp=datetime.now(),
        source="wsj",
        source_tier="tier2_reliable",
        category="politics",
        title="Trump Announces Comprehensive Immigration Enforcement Plan for Day One",
        content="Former President Trump detailed his immigration enforcement strategy, including immediate deportation operations and border security measures to begin on his first day in office.",
        url="https://wsj.com/trump-immigration",
        author="WSJ Politics",
        keywords_matched=["trump", "immigration", "deportation"],
        urgency_score=8.0,
        is_duplicate=False,
        duplicate_of=None,
        raw_data={}
    ))
    
    # 3. Crypto market development
    events.append(Event(
        id="demo-crypto-001",
        timestamp=datetime.now(),
        source="coindesk",
        source_tier="tier2_reliable",
        category="crypto",
        title="Bitcoin Breaks Above $110,000 as Institutional Adoption Surges",
        content="Bitcoin reached a new all-time high above $110,000 following major institutional announcements and positive regulatory developments.",
        url="https://coindesk.com/btc-110k",
        author="CoinDesk Markets",
        keywords_matched=["bitcoin", "btc", "110000", "institutional"],
        urgency_score=7.5,
        is_duplicate=False,
        duplicate_of=None,
        raw_data={}
    ))
    
    # 4. Russia-Ukraine development
    events.append(Event(
        id="demo-ukraine-001",
        timestamp=datetime.now(),
        source="bbc",
        source_tier="tier1_breaking",
        category="geopolitics",
        title="Russia and Ukraine Agree to Preliminary Ceasefire Framework",
        content="Both sides have agreed to a preliminary framework for a ceasefire, with negotiations set to begin next week under international mediation.",
        url="https://bbc.com/ukraine-ceasefire",
        author="BBC World Service",
        keywords_matched=["russia", "ukraine", "ceasefire"],
        urgency_score=9.0,
        is_duplicate=False,
        duplicate_of=None,
        raw_data={}
    ))
    
    # 5. Tech earnings (lower impact)
    events.append(Event(
        id="demo-tech-001",
        timestamp=datetime.now(),
        source="techcrunch",
        source_tier="tier3_general",
        category="tech",
        title="Apple Reports Q4 Earnings Slightly Above Expectations",
        content="Apple's Q4 results came in slightly above analyst expectations, driven by strong iPhone sales and services revenue growth.",
        url="https://techcrunch.com/apple-earnings",
        author="TechCrunch",
        keywords_matched=["apple", "earnings"],
        urgency_score=5.0,
        is_duplicate=False,
        duplicate_of=None,
        raw_data={}
    ))
    
    return events


async def demo_signal_pipeline():
    """Demonstrate the complete signal generation pipeline."""
    print("🔮 Signal Generation Pipeline Demo")
    print("=" * 60)
    
    demo_events = create_demo_events()
    all_signals = []
    
    for i, event in enumerate(demo_events, 1):
        print(f"\n📰 Event {i}: {event.title}")
        print(f"Source: {event.source} ({event.source_tier})")
        print(f"Category: {event.category} | Urgency: {event.urgency_score}/10")
        print(f"Content: {event.content[:100]}...")
        
        try:
            # Process event through complete pipeline
            print("\n🔄 Processing through pipeline...")
            signals = await process_event_to_signals(event)
            
            if signals:
                print(f"✅ Generated {len(signals)} signals:")
                
                for j, signal in enumerate(signals, 1):
                    direction_emoji = {
                        "BUY_YES": "📈",
                        "BUY_NO": "📉", 
                        "HOLD": "➖"
                    }.get(signal.direction, "❓")
                    
                    print(f"  {j}. {direction_emoji} {signal.direction}")
                    print(f"     Market: {signal.market_id}")
                    print(f"     Confidence: {signal.confidence:.1%}")
                    print(f"     Price: {signal.current_price:.3f} → {signal.expected_price:.3f}")
                    print(f"     Expected Return: {signal.expected_return:+.1%}")
                    print(f"     Reasoning: {signal.reasoning[:80]}...")
                
                all_signals.extend(signals)
            else:
                print("❌ No signals generated (low confidence or no market matches)")
                
        except Exception as e:
            print(f"❌ Error processing event: {e}")
        
        print("-" * 40)
    
    # Filter and summarize all signals
    print(f"\n📊 Pipeline Summary")
    print(f"Total events processed: {len(demo_events)}")
    print(f"Total signals generated: {len(all_signals)}")
    
    if all_signals:
        # Filter high-quality signals
        high_quality_signals = filter_signals(all_signals, min_confidence=0.6)
        print(f"High-quality signals (>60% confidence): {len(high_quality_signals)}")
        
        # Get summary statistics
        summary = get_signal_summary(high_quality_signals)
        print(f"\n📈 Signal Breakdown:")
        print(f"  BUY_YES: {summary['buy_yes']}")
        print(f"  BUY_NO: {summary['buy_no']}")
        print(f"  HOLD: {summary['hold']}")
        print(f"  Average Confidence: {summary['avg_confidence']:.1%}")
        print(f"  Max Expected Return: {summary['max_expected_return']:.1%}")
        
        # Show top 3 signals
        if len(high_quality_signals) > 0:
            print(f"\n🏆 Top Trading Opportunities:")
            sorted_signals = sorted(high_quality_signals, key=lambda s: s.confidence, reverse=True)
            
            for i, signal in enumerate(sorted_signals[:3], 1):
                direction_emoji = {
                    "BUY_YES": "📈",
                    "BUY_NO": "📉",
                    "HOLD": "➖"
                }.get(signal.direction, "❓")
                
                print(f"  {i}. {direction_emoji} {signal.direction} {signal.market_id}")
                print(f"     Confidence: {signal.confidence:.1%} | Return: {signal.expected_return:+.1%}")
    
    print(f"\n✨ Demo completed! Signal generation pipeline is fully functional.")


def show_pipeline_architecture():
    """Show the architecture of the signal generation pipeline."""
    print("\n🏗️  Signal Generation Pipeline Architecture")
    print("=" * 60)
    print("""
📥 Input: Raw Event
    ↓
🏷️  Step 1: Event Classification
    → Categories: fed, crypto, politics, tech, etc.
    → Extract keywords and entities
    ↓
📊 Step 2: Urgency Scoring  
    → Score 1-10 based on source tier, content, timing
    → Apply modifiers for breaking news, numbers, etc.
    ↓
🎯 Step 3: Market Mapping
    → Find relevant Polymarket markets
    → Calculate relevance scores
    → Determine direction hints (bullish/bearish)
    ↓
💰 Step 4: Price Fetching
    → Get current market prices from Polymarket API
    → Include volume, liquidity, active status
    ↓
🔮 Step 5: Signal Generation
    → Analyze sentiment vs market direction
    → Calculate expected price movement
    → Compute confidence score (multiple factors)
    → Generate BUY_YES/BUY_NO/HOLD signal
    ↓
⚡ Step 6: Signal Filtering
    → Remove low-confidence signals
    → Filter by minimum expected returns  
    → Sort by confidence/opportunity
    ↓
📤 Output: Actionable Trading Signals
""")


if __name__ == "__main__":
    show_pipeline_architecture()
    asyncio.run(demo_signal_pipeline())