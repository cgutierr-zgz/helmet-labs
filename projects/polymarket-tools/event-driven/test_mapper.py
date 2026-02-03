#!/usr/bin/env python3
"""
Test script for the market mapper functionality.
Demonstrates various types of event-to-market matching.
"""

from datetime import datetime
import sys
import os

# Add project root to path  
sys.path.insert(0, os.path.dirname(__file__))

from src.models import Event
from src.intelligence.mapper import MarketMapper, get_affected_markets


def test_mapper():
    """Test the market mapper with various event types."""
    print("🔍 Testing Market Mapper - TASK-008")
    print("=" * 50)
    
    # Test events covering different categories and matching types
    test_events = [
        # 1. FED/Monetary Policy event
        Event(
            id="test-fed-1",
            timestamp=datetime.now(),
            source="reuters",
            source_tier="tier1_breaking",
            category="fed",
            title="Powell Signals Dovish Stance on Interest Rates",
            content="Federal Reserve Chair Jerome Powell indicated the central bank may pause rate hikes and consider cuts if inflation continues to cool. Speaking at Jackson Hole, Powell emphasized data dependency.",
            url="https://reuters.com/fed-powell",
            author="Reuters",
            keywords_matched=["powell", "fed", "rates"],
            urgency_score=8.5,
            is_duplicate=False,
            duplicate_of=None,
            raw_data={}
        ),
        
        # 2. Crypto event
        Event(
            id="test-crypto-1", 
            timestamp=datetime.now(),
            source="coindesk",
            source_tier="tier2_reliable",
            category="crypto",
            title="Bitcoin Surges Past $95k as ETF Inflows Continue",
            content="Bitcoin reached a new all-time high above $95,000 as institutional demand via ETFs remains strong. Analysts predict potential for $100k breakthrough in Q1 2025.",
            url="https://coindesk.com/btc-surge",
            author="CoinDesk",
            keywords_matched=["bitcoin", "btc", "surge"],
            urgency_score=7.0,
            is_duplicate=False,
            duplicate_of=None,
            raw_data={}
        ),
        
        # 3. Gaming/Entertainment event
        Event(
            id="test-gaming-1",
            timestamp=datetime.now(), 
            source="ign",
            source_tier="tier2_reliable",
            category="entertainment",
            title="Rockstar Confirms GTA 6 Development on Track for 2025",
            content="Take-Two Interactive confirmed that Grand Theft Auto 6 development remains on schedule for a 2025 release window, with the studio targeting a premium price point above $100.",
            url="https://ign.com/gta6-update",
            author="IGN",
            keywords_matched=["gta 6", "rockstar", "2025"],
            urgency_score=6.5,
            is_duplicate=False,
            duplicate_of=None,
            raw_data={}
        ),
        
        # 4. Geopolitics event
        Event(
            id="test-geopolitics-1",
            timestamp=datetime.now(),
            source="bbc",
            source_tier="tier1_breaking", 
            category="geopolitics",
            title="Ukraine Reports Major Breakthrough in Eastern Front",
            content="Ukrainian forces report significant territorial gains near Donetsk as Russia appears to be withdrawing troops. Some analysts suggest this could pressure Moscow toward ceasefire negotiations.",
            url="https://bbc.com/ukraine-breakthrough",
            author="BBC",
            keywords_matched=["ukraine", "russia", "ceasefire"],
            urgency_score=9.0,
            is_duplicate=False,
            duplicate_of=None,
            raw_data={}
        )
    ]
    
    mapper = MarketMapper()
    
    for i, event in enumerate(test_events, 1):
        print(f"\n📰 Test Event {i}: {event.title}")
        print(f"Category: {event.category} | Source: {event.source} | Urgency: {event.urgency_score}")
        
        matches = mapper.get_affected_markets(event)
        
        if matches:
            print(f"Found {len(matches)} market matches:")
            for match in matches:
                print(f"  🎯 {match.market_slug}")
                print(f"     Relevance: {match.relevance_score:.2f} | Direction: {match.direction_hint}")
                print(f"     Match Type: {match.match_type} | Reasoning: {match.reasoning}")
                if match.matched_keywords:
                    print(f"     Keywords: {', '.join(match.matched_keywords)}")
                print()
        else:
            print("  ❌ No market matches found")
        
        print("-" * 50)
    
    print("\n✅ Mapper testing completed!")
    
    # Test edge cases
    print("\n🧪 Testing edge cases...")
    
    # Test fuzzy matching
    fuzzy_event = Event(
        id="fuzzy-test",
        timestamp=datetime.now(),
        source="twitter",
        source_tier="tier3_general", 
        category="tech",
        title="Bitcoin hits 100k milestone",
        content="The digital currency bitcoin-100k prediction comes true today",
        url=None,
        author="CryptoTrader",
        keywords_matched=[],
        urgency_score=5.0,
        is_duplicate=False,
        duplicate_of=None,
        raw_data={}
    )
    
    fuzzy_matches = mapper.get_affected_markets(fuzzy_event)
    print(f"Fuzzy matching test: Found {len(fuzzy_matches)} matches")
    for match in fuzzy_matches:
        if match.match_type == "fuzzy":
            print(f"  🔍 {match.market_slug}: {match.reasoning}")


if __name__ == "__main__":
    test_mapper()