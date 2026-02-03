#!/usr/bin/env python3
"""
Tests for semantic diff engine.

Run:
    python test_diff_engine.py
    python -m pytest test_diff_engine.py -v
"""

import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from diff_engine import SemanticDiff, create_diff_engine


def test_noise_only_changes():
    """Test that noise-only changes are correctly ignored."""
    diff = SemanticDiff(threshold=0.1)
    
    old = """
    <div class="article">
        <h1>Breaking News</h1>
        <p>Published: 2024-01-15T10:30:00Z</p>
        <p>Views: 1234</p>
        <p>Session ID: abc123xyz</p>
        <p>The Fed announces rate decision.</p>
    </div>
    """
    
    new = """
    <div class="article">
        <h1>Breaking News</h1>
        <p>Published: 2024-01-15T14:45:00Z</p>
        <p>Views: 5678</p>
        <p>Session ID: xyz789def</p>
        <p>The Fed announces rate decision.</p>
    </div>
    """
    
    is_sig, ratio, summary = diff.is_significant_change(old, new)
    
    print("Test 1: Noise-only changes")
    print(f"  Significant: {is_sig} (expected: False)")
    print(f"  Ratio: {ratio:.1%}")
    print(f"  Summary: {summary}")
    
    assert not is_sig, "Noise-only changes should not be significant"
    assert ratio < 0.1, f"Change ratio {ratio} should be < 0.1"
    print("  ✅ PASS\n")


def test_real_content_change():
    """Test that real content changes are detected."""
    diff = SemanticDiff(threshold=0.05)
    
    old = """
    <div class="article">
        <h1>Breaking News</h1>
        <p>Published: 2024-01-15T10:30:00Z</p>
        <p>Views: 1234</p>
        <p>The Fed announces rate decision.</p>
    </div>
    """
    
    new = """
    <div class="article">
        <h1>Breaking News</h1>
        <p>Published: 2024-01-15T14:45:00Z</p>
        <p>Views: 5678</p>
        <p>The Fed announces rate increase to 5.5%.</p>
    </div>
    """
    
    is_sig, ratio, summary = diff.is_significant_change(old, new)
    
    print("Test 2: Real content change")
    print(f"  Significant: {is_sig} (expected: True)")
    print(f"  Ratio: {ratio:.1%}")
    print(f"  Summary: {summary}")
    
    assert is_sig, "Real content changes should be significant"
    assert ratio >= 0.05, f"Change ratio {ratio} should be >= 0.05"
    assert "5.5" in summary or "increase" in summary, "Summary should mention new content"
    print("  ✅ PASS\n")


def test_utm_tracking_ignored():
    """Test that UTM tracking params and analytics IDs are ignored."""
    diff = SemanticDiff(threshold=0.1)
    
    old = "Check out our site: https://example.com/article?utm_source=twitter&utm_medium=social&_ga=GA1.2.12345"
    new = "Check out our site: https://example.com/article?utm_source=facebook&utm_medium=cpc&_ga=GA1.2.67890&_gid=GA1.2.99999"
    
    is_sig, ratio, summary = diff.is_significant_change(old, new)
    
    print("Test 3: UTM tracking ignored")
    print(f"  Significant: {is_sig} (expected: False)")
    print(f"  Ratio: {ratio:.1%}")
    
    assert not is_sig, "UTM param changes should be ignored"
    print("  ✅ PASS\n")


def test_relative_timestamps_ignored():
    """Test that relative timestamps are ignored."""
    diff = SemanticDiff(threshold=0.1)
    
    old = "Posted 5 minutes ago: The Fed meets today."
    new = "Posted 2 hours ago: The Fed meets today."
    
    is_sig, ratio, summary = diff.is_significant_change(old, new)
    
    print("Test 4: Relative timestamps ignored")
    print(f"  Significant: {is_sig} (expected: False)")
    print(f"  Ratio: {ratio:.1%}")
    
    assert not is_sig, "Relative timestamp changes should be ignored"
    print("  ✅ PASS\n")


def test_custom_patterns():
    """Test custom noise patterns per source."""
    # Create diff with custom pattern to ignore "Document #12345" style strings
    diff = SemanticDiff(threshold=0.1, custom_patterns=[
        r'Document #\d+',
        r'File-\d{4}-\d{3}'
    ])
    
    old = "Document #12345: Important SEC filing. File-2024-001"
    new = "Document #98765: Important SEC filing. File-2024-999"
    
    is_sig, ratio, summary = diff.is_significant_change(old, new)
    
    print("Test 5: Custom ignore patterns")
    print(f"  Significant: {is_sig} (expected: False)")
    print(f"  Ratio: {ratio:.1%}")
    
    assert not is_sig, "Custom patterns should be ignored"
    print("  ✅ PASS\n")


def test_threshold_sensitivity():
    """Test that threshold setting affects detection."""
    old = "The market moved today. Views: 100"
    new = "The market moved yesterday. Views: 500"
    
    # Low threshold (5%) - should detect
    diff_low = SemanticDiff(threshold=0.05)
    is_sig_low, ratio, _ = diff_low.is_significant_change(old, new)
    
    # High threshold (50%) - should not detect
    diff_high = SemanticDiff(threshold=0.5)
    is_sig_high, _, _ = diff_high.is_significant_change(old, new)
    
    print("Test 6: Threshold sensitivity")
    print(f"  Change ratio: {ratio:.1%}")
    print(f"  Low threshold (5%): {is_sig_low} (expected: True)")
    print(f"  High threshold (50%): {is_sig_high} (expected: False)")
    
    assert is_sig_low, "Low threshold should detect change"
    assert not is_sig_high, "High threshold should not detect change"
    print("  ✅ PASS\n")


def test_extract_new_items():
    """Test extraction of truly new items from lists."""
    diff = SemanticDiff()
    
    old_items = [
        "Article 1: Fed meeting (Views: 100)",
        "Article 2: SEC filing (Views: 50)",
    ]
    
    new_items = [
        "Article 1: Fed meeting (Views: 500)",  # Same but noise changed
        "Article 2: SEC filing (Views: 200)",   # Same but noise changed
        "Article 3: Treasury statement (Views: 10)",  # Actually new
    ]
    
    new_unique = diff.extract_new_items(old_items, new_items)
    
    print("Test 7: Extract new items")
    print(f"  Found {len(new_unique)} new items (expected: 1)")
    print(f"  New: {new_unique}")
    
    assert len(new_unique) == 1, "Should find exactly 1 new item"
    assert "Treasury" in new_unique[0], "Should be the Treasury article"
    print("  ✅ PASS\n")


def test_create_diff_engine_from_config():
    """Test factory function with source config."""
    source_config = {
        'id': 'test_source',
        'diff_threshold': 0.05,
        'ignore_patterns': [r'CustomID:\d+']
    }
    
    diff = create_diff_engine(source_config)
    
    print("Test 8: Create from config")
    print(f"  Threshold: {diff.threshold} (expected: 0.05)")
    print(f"  Custom patterns: {len(diff.noise_patterns)} (should include default + 1)")
    
    assert diff.threshold == 0.05, "Threshold should be from config"
    assert r'CustomID:\d+' in diff.noise_patterns, "Custom pattern should be added"
    print("  ✅ PASS\n")


def test_unix_timestamps_ignored():
    """Test that unix timestamps are ignored."""
    diff = SemanticDiff(threshold=0.1)
    
    old = "Event occurred at 1705316400. Record ID: 1234567890123"
    new = "Event occurred at 1705402800. Record ID: 9876543210987"
    
    is_sig, ratio, summary = diff.is_significant_change(old, new)
    
    print("Test 9: Unix timestamps ignored")
    print(f"  Significant: {is_sig} (expected: False)")
    print(f"  Ratio: {ratio:.1%}")
    
    assert not is_sig, "Unix timestamps should be ignored"
    print("  ✅ PASS\n")


def test_view_counters_ignored():
    """Test that various counter formats are ignored."""
    diff = SemanticDiff(threshold=0.1)
    
    old = "Article has 1234 views and 56 clicks. 10 visitors today."
    new = "Article has 5678 views and 123 clicks. 45 visitors today."
    
    is_sig, ratio, summary = diff.is_significant_change(old, new)
    
    print("Test 10: View/click counters ignored")
    print(f"  Significant: {is_sig} (expected: False)")
    print(f"  Ratio: {ratio:.1%}")
    
    assert not is_sig, "Counters should be ignored"
    print("  ✅ PASS\n")


if __name__ == '__main__':
    print("="*70)
    print("SEMANTIC DIFF ENGINE - TEST SUITE")
    print("="*70 + "\n")
    
    try:
        test_noise_only_changes()
        test_real_content_change()
        test_utm_tracking_ignored()
        test_relative_timestamps_ignored()
        test_custom_patterns()
        test_threshold_sensitivity()
        test_extract_new_items()
        test_create_diff_engine_from_config()
        test_unix_timestamps_ignored()
        test_view_counters_ignored()
        
        print("="*70)
        print("✅ ALL TESTS PASSED!")
        print("="*70)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
