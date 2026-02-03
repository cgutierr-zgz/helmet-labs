#!/usr/bin/env python3
"""
Demo script for AI-powered event analysis.
Shows how the new AI analysis system works with sample events.
"""
import sys
import os
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.models import Event
from src.intelligence import create_ai_integration


def create_sample_events():
    """Create sample events to test AI analysis."""
    events = [
        Event(
            id="evt_fed_signal",
            timestamp=datetime.now(),
            source="rss",
            source_tier="tier1_breaking",
            category="fed",
            title="Fed Chair Powell Signals Potential March Rate Cut",
            content="Federal Reserve Chairman Jerome Powell indicated in today's speech that the central bank is considering a rate cut as early as March, citing cooling inflation and labor market concerns.",
            url="https://reuters.com/fed-march-cut",
            author="Reuters",
            keywords_matched=["fed", "rate cut", "powell", "march"],
            urgency_score=8.5,
            is_duplicate=False,
            duplicate_of=None,
            raw_data={}
        ),
        
        Event(
            id="evt_btc_news",
            timestamp=datetime.now(),
            source="twitter",
            source_tier="tier2_reliable",
            category="crypto",
            title="MicroStrategy Announces $500M Additional Bitcoin Purchase",
            content="MicroStrategy (MSTR) announced plans to purchase an additional $500 million worth of Bitcoin, bringing their total holdings to over 200,000 BTC.",
            url="https://twitter.com/microstrategy/status/123",
            author="@MicroStrategy",
            keywords_matched=["bitcoin", "microstrategy", "purchase"],
            urgency_score=6.0,
            is_duplicate=False,
            duplicate_of=None,
            raw_data={}
        ),
        
        Event(
            id="evt_low_relevance",
            timestamp=datetime.now(),
            source="rss",
            source_tier="tier3_general",
            category="sports",
            title="Local Team Wins Championship",
            content="The local sports team won their championship game last night.",
            url="https://localnews.com/sports",
            author="Local News",
            keywords_matched=[],
            urgency_score=2.0,
            is_duplicate=False,
            duplicate_of=None,
            raw_data={}
        )
    ]
    
    return events


def demo_ai_analysis():
    """Demonstrate the AI analysis system."""
    print("🧠 AI-Powered Event Analysis Demo")
    print("=" * 50)
    
    # Create AI integration service
    ai_service = create_ai_integration()
    
    # Sample market prices
    market_prices = {
        "fed_rate_cut_march_2025": 0.45,
        "btc_price_100k_2025": 0.72,
        "trump_reelected_2024": 0.83
    }
    
    # Update market prices in the service
    ai_service.update_market_prices(market_prices)
    
    # Create sample events
    events = create_sample_events()
    
    print(f"\n📥 Processing {len(events)} sample events...\n")
    
    processed_count = 0
    queued_decisions = []
    
    for event in events:
        print(f"📰 Processing: {event.title}")
        print(f"   Source: {event.source} ({event.source_tier})")
        print(f"   Category: {event.category}")
        print(f"   Urgency: {event.urgency_score}/10")
        
        # Process event through AI
        decision_id = ai_service.process_event(event, market_prices)
        
        if decision_id:
            print(f"   ✅ Queued for decision: {decision_id}")
            queued_decisions.append(decision_id)
            processed_count += 1
        else:
            print(f"   ⏭️  Not queued (filtered out)")
        
        print()
    
    print(f"📊 Results: {processed_count}/{len(events)} events queued for decision\n")
    
    # Show pending decisions summary
    print("📋 Pending Decisions Summary:")
    print("-" * 30)
    summary = ai_service.get_pending_decisions_summary()
    print(summary)
    
    # Show detailed review for first queued decision
    if queued_decisions:
        print("\n🔍 Detailed Review for First Decision:")
        print("-" * 40)
        first_decision = queued_decisions[0]
        review = ai_service.get_decision_for_review(first_decision)
        if review:
            print(review)
        
        # Simulate main agent decision
        print(f"\n🎯 Simulating main agent decision on {first_decision}...")
        success = ai_service.mark_decision_processed(
            first_decision, 
            "REVIEWED", 
            "Demo completed - would need real market analysis for actual trading"
        )
        print(f"   {'✅' if success else '❌'} Decision marked as processed")


def demo_integration_points():
    """Show how this integrates with existing system."""
    print("\n🔗 Integration Points")
    print("=" * 50)
    
    integration_info = """
The AI analysis system integrates with the existing event-driven system as follows:

1. **Event Flow Integration**:
   • Events pass through normal keyword filtering first
   • Promising events (urgency ≥ 4, relevant categories) go to AI analysis  
   • AI analyzes sentiment, significance, market impact
   • High-potential events get queued for main agent review

2. **Main Agent Integration**:
   • Heartbeat checks pending_decisions.jsonl for new analyses
   • Main agent reviews AI recommendations in formatted messages
   • Agent makes final trading decision based on AI + own judgment
   • Decisions get marked as processed (TRADED/PASSED/IGNORED)

3. **Cost Optimization**:
   • Only analyzes events that pass basic relevance filters
   • Uses Haiku (cheap model) for analysis  
   • Caches similar analyses to avoid duplicate API calls
   • Batches events when possible

4. **File Structure**:
   • data/pending_decisions.jsonl - Queue for main agent review
   • data/processed_decisions.jsonl - History of decisions made
   • Analysis results include confidence scores and reasoning

5. **Usage in Main Loop**:
   ```python
   # In your main event processing loop:
   from intelligence import create_ai_integration
   
   ai_service = create_ai_integration()
   
   for event in filtered_events:
       decision_id = ai_service.process_event(event, current_market_prices)
       if decision_id:
           logger.info(f"Event queued for AI decision: {decision_id}")
   ```

6. **Heartbeat Integration**:
   ```python
   # In heartbeat checks:
   summary = ai_service.get_pending_decisions_summary(max_decisions=3)
   if "pending" in summary.lower():
       send_notification(summary)
   ```
   """
   
    print(integration_info)


if __name__ == "__main__":
    demo_ai_analysis()
    demo_integration_points()