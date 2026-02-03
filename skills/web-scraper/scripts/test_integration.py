#!/usr/bin/env python3
"""
Integration test for monitor_daemon with rate limiting.

Tests the rate limiter integration without requiring browser pool.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent))

# Mock browser_pool before importing monitor_daemon
sys.modules['browser_pool'] = MagicMock()

from monitor_daemon import MonitorDaemon, get_random_user_agent


async def test_fetch_http_with_rate_limiting():
    """Test that fetch_http integrates with rate limiter correctly."""
    print("\n" + "="*60)
    print("TEST: HTTP Fetch with Rate Limiting")
    print("="*60)
    
    daemon = MonitorDaemon()
    daemon.load_sources()
    
    # Verify rate limiter and retry handler are initialized
    assert daemon.rate_limiter is not None, "Rate limiter should be initialized"
    assert daemon.retry_handler is not None, "Retry handler should be initialized"
    
    print(f"  ✓ Rate limiter initialized (default_delay: {daemon.rate_limiter.default_delay}s)")
    print(f"  ✓ Retry handler initialized (max_retries: {daemon.retry_handler.max_retries})")
    
    # Test user agent rotation
    user_agents = set()
    for _ in range(20):
        ua = get_random_user_agent()
        user_agents.add(ua)
    
    print(f"  ✓ User-Agent rotation working ({len(user_agents)} unique agents)")
    assert len(user_agents) > 1, "Should have multiple user agents"
    
    # Test that rate limiter tracks domains
    url1 = "https://example.com/page1"
    url2 = "https://example.com/page2"
    url3 = "https://other.com/page1"
    
    domain1 = daemon.rate_limiter._get_domain(url1)
    domain2 = daemon.rate_limiter._get_domain(url2)
    domain3 = daemon.rate_limiter._get_domain(url3)
    
    assert domain1 == domain2, "Same domain should be detected"
    assert domain1 != domain3, "Different domains should be detected"
    
    print(f"  ✓ Domain tracking working")
    
    # Test error reporting
    daemon.rate_limiter.report_error(url1)
    errors = daemon.rate_limiter._consecutive_errors[domain1]
    assert errors == 1, "Error should be tracked"
    print(f"  ✓ Error reporting working (consecutive errors: {errors})")
    
    # Test success reporting
    daemon.rate_limiter.report_success(url1)
    errors_after = daemon.rate_limiter._consecutive_errors[domain1]
    assert errors_after == 0, "Errors should reset on success"
    print(f"  ✓ Success reporting working (errors reset to {errors_after})")
    
    print("\n✅ INTEGRATION TEST PASSED")


async def test_config_loading():
    """Test that configuration is properly loaded."""
    print("\n" + "="*60)
    print("TEST: Configuration Loading")
    print("="*60)
    
    daemon = MonitorDaemon()
    daemon.load_sources()
    
    # Check that config values are loaded
    config_keys = [
        'rate_limit_per_domain_ms',
        'max_retries',
        'retry_base_delay_ms',
        'max_consecutive_errors',
        'user_agent_rotation'
    ]
    
    for key in config_keys:
        value = daemon.config.get(key)
        print(f"  • {key}: {value}")
        assert value is not None, f"Config key {key} should be set"
    
    # Verify rate limiter uses config values
    expected_delay = daemon.config['rate_limit_per_domain_ms'] / 1000
    actual_delay = daemon.rate_limiter.default_delay
    assert abs(actual_delay - expected_delay) < 0.01, "Rate limiter should use config delay"
    
    print(f"\n  ✓ Rate limiter using config delay: {actual_delay}s")
    print("\n✅ CONFIG TEST PASSED")


async def test_domain_skip_logic():
    """Test that domains are skipped after max errors."""
    print("\n" + "="*60)
    print("TEST: Domain Skip Logic")
    print("="*60)
    
    daemon = MonitorDaemon()
    daemon.load_sources()
    
    url = "https://failing.com/page"
    max_errors = daemon.config.get('max_consecutive_errors', 5)
    
    print(f"  • Max consecutive errors: {max_errors}")
    
    # Simulate errors up to the limit
    for i in range(max_errors):
        daemon.rate_limiter.report_error(url)
        should_skip = daemon.rate_limiter.should_skip(url, max_errors)
        print(f"  • Error #{i+1}: should_skip={should_skip}")
    
    assert daemon.rate_limiter.should_skip(url, max_errors), "Should skip after max errors"
    
    # Verify fetch would raise error
    try:
        # This should fail because domain is marked to skip
        with patch('aiohttp.ClientSession') as mock_session:
            await daemon.fetch_http(url)
        assert False, "Should have raised RuntimeError"
    except RuntimeError as e:
        assert "skipped" in str(e).lower(), "Error should mention skipping"
        print(f"  ✓ Fetch correctly raises: {e}")
    
    print("\n✅ SKIP LOGIC TEST PASSED")


async def main():
    """Run all integration tests."""
    print("\n🧪 Running Integration Tests for Monitor Daemon")
    print("="*60)
    
    try:
        await test_fetch_http_with_rate_limiting()
        await test_config_loading()
        await test_domain_skip_logic()
        
        print("\n" + "="*60)
        print("🎉 ALL INTEGRATION TESTS PASSED!")
        print("="*60 + "\n")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
