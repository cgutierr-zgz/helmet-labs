#!/usr/bin/env python3
"""
Test script for RSS tier system
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.fetchers.rss import scan_rss_feeds, get_tier_status, TIER_INTERVALS
from config.settings import SOURCES
import json

def test_tier_config():
    """Test that tier configuration is loaded properly."""
    print("=== RSS TIER CONFIGURATION ===")
    
    rss_tiers = SOURCES.get("rss_tiers", {})
    print(f"Found {len(rss_tiers)} tiers:")
    
    for tier_name, feeds in rss_tiers.items():
        interval = TIER_INTERVALS.get(tier_name, "Unknown")
        print(f"  {tier_name}: {len(feeds)} feeds, interval: {interval} min")
        for feed in feeds:
            print(f"    - {feed}")
    
    print()

def test_tier_status():
    """Test tier status functionality."""
    print("=== TIER STATUS ===")
    
    status = get_tier_status()
    for tier_name, info in status.items():
        print(f"{tier_name}:")
        print(f"  Interval: {info['interval_minutes']} minutes")
        print(f"  Last fetched: {info['last_fetched'] or 'Never'}")
        print(f"  Next fetch: {info['next_fetch']}")
        print(f"  Should fetch: {info['should_fetch']}")
        print()

def test_rss_fetch():
    """Test RSS fetching with tiers."""
    print("=== RSS FETCH TEST ===")
    
    events = scan_rss_feeds()
    print(f"Found {len(events)} events")
    
    # Group by tier
    tier_events = {}
    for event in events:
        tier = event.source_category
        if tier not in tier_events:
            tier_events[tier] = []
        tier_events[tier].append(event)
    
    for tier, tier_event_list in tier_events.items():
        print(f"\n{tier}: {len(tier_event_list)} events")
        for event in tier_event_list[:3]:  # Show first 3
            print(f"  - {event.category}: {event.headline[:80]}...")

if __name__ == "__main__":
    try:
        test_tier_config()
        test_tier_status()
        test_rss_fetch()
        
        print("=== FINAL TIER STATUS ===")
        test_tier_status()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()