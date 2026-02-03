#!/usr/bin/env python3
"""
Integration test for semantic diff in monitor daemon.

Creates test HTML files, runs monitor, verifies noise is ignored.

Run:
    python test_integration.py
"""

import json
import sys
import tempfile
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))


def create_test_html_with_noise(base_content: str, noise_suffix: str) -> str:
    """Create HTML with base content + timestamp noise."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head><title>Test Page</title></head>
    <body>
        <div class="content">
            {base_content}
        </div>
        <div class="metadata">
            <p>Last updated: 2024-01-15T{noise_suffix}</p>
            <p>Page views: {hash(noise_suffix) % 10000}</p>
            <p>Session ID: session_{noise_suffix}</p>
        </div>
    </body>
    </html>
    """


def create_test_html_with_real_change(base_content: str, noise_suffix: str) -> str:
    """Create HTML with real content change + noise."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head><title>Test Page</title></head>
    <body>
        <div class="content">
            {base_content}
            <p class="new-content">BREAKING: New development announced!</p>
        </div>
        <div class="metadata">
            <p>Last updated: 2024-01-15T{noise_suffix}</p>
            <p>Page views: {hash(noise_suffix) % 10000}</p>
            <p>Session ID: session_{noise_suffix}</p>
        </div>
    </body>
    </html>
    """


def test_monitor_ignores_noise():
    """Test that monitor correctly ignores noise-only changes."""
    print("Test 1: Monitor should ignore noise-only changes")
    print("-" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create test files
        base_content = "<h1>Important Announcement</h1><p>The Fed holds rates steady.</p>"
        
        v1_html = create_test_html_with_noise(base_content, "10:00:00Z")
        v2_html = create_test_html_with_noise(base_content, "14:30:00Z")  # Only noise changed
        
        (tmpdir / "page_v1.html").write_text(v1_html)
        (tmpdir / "page_v2.html").write_text(v2_html)
        
        # Simulate diff check
        from diff_engine import SemanticDiff
        
        diff = SemanticDiff(threshold=0.1)
        is_sig, ratio, summary = diff.is_significant_change(v1_html, v2_html)
        
        print(f"  v1 size: {len(v1_html)} bytes")
        print(f"  v2 size: {len(v2_html)} bytes")
        print(f"  Significant change: {is_sig} (expected: False)")
        print(f"  Change ratio: {ratio:.2%}")
        print(f"  Summary: {summary}")
        
        if not is_sig:
            print("  ✅ PASS: Noise correctly ignored\n")
            return True
        else:
            print("  ❌ FAIL: Noise was not ignored\n")
            return False


def test_monitor_detects_real_change():
    """Test that monitor detects real content changes."""
    print("Test 2: Monitor should detect real content changes")
    print("-" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        base_content = "<h1>Important Announcement</h1><p>The Fed holds rates steady.</p>"
        
        v1_html = create_test_html_with_noise(base_content, "10:00:00Z")
        v2_html = create_test_html_with_real_change(base_content, "14:30:00Z")  # Real change + noise
        
        (tmpdir / "page_v1.html").write_text(v1_html)
        (tmpdir / "page_v2.html").write_text(v2_html)
        
        # Simulate diff check
        from diff_engine import SemanticDiff
        
        diff = SemanticDiff(threshold=0.05)
        is_sig, ratio, summary = diff.is_significant_change(v1_html, v2_html)
        
        print(f"  v1 size: {len(v1_html)} bytes")
        print(f"  v2 size: {len(v2_html)} bytes")
        print(f"  Significant change: {is_sig} (expected: True)")
        print(f"  Change ratio: {ratio:.2%}")
        print(f"  Summary: {summary[:100]}...")
        
        if is_sig and ("BREAKING" in summary or "development" in summary or "announced" in summary):
            print("  ✅ PASS: Real change detected\n")
            return True
        else:
            print("  ❌ FAIL: Real change not detected\n")
            return False


def test_threshold_configuration():
    """Test that per-source threshold configuration works."""
    print("Test 3: Per-source threshold configuration")
    print("-" * 60)
    
    from diff_engine import create_diff_engine
    
    # Low threshold source (sensitive)
    source_low = {
        'id': 'sec_filings',
        'diff_threshold': 0.03,
    }
    
    # High threshold source (less sensitive)
    source_high = {
        'id': 'news_feed',
        'diff_threshold': 0.15,
    }
    
    # Default threshold source
    source_default = {
        'id': 'generic',
    }
    
    diff_low = create_diff_engine(source_low)
    diff_high = create_diff_engine(source_high)
    diff_default = create_diff_engine(source_default)
    
    print(f"  Low threshold: {diff_low.threshold} (expected: 0.03)")
    print(f"  High threshold: {diff_high.threshold} (expected: 0.15)")
    print(f"  Default threshold: {diff_default.threshold} (expected: 0.1)")
    
    if (diff_low.threshold == 0.03 and 
        diff_high.threshold == 0.15 and 
        diff_default.threshold == 0.1):
        print("  ✅ PASS: Threshold configuration works\n")
        return True
    else:
        print("  ❌ FAIL: Threshold configuration broken\n")
        return False


def test_custom_patterns():
    """Test that per-source custom patterns work."""
    print("Test 4: Per-source custom ignore patterns")
    print("-" * 60)
    
    from diff_engine import create_diff_engine
    
    source = {
        'id': 'treasury',
        'ignore_patterns': [
            r'Press Release \d+-\d+',
            r'Document ID: \d+'
        ]
    }
    
    diff = create_diff_engine(source)
    
    old = "Treasury announces policy. Press Release 2024-001. Document ID: 12345"
    new = "Treasury announces policy. Press Release 2024-999. Document ID: 67890"
    
    is_sig, ratio, summary = diff.is_significant_change(old, new)
    
    print(f"  Custom patterns added: {len(source['ignore_patterns'])}")
    print(f"  Significant: {is_sig} (expected: False)")
    print(f"  Ratio: {ratio:.2%}")
    
    if not is_sig:
        print("  ✅ PASS: Custom patterns work\n")
        return True
    else:
        print("  ❌ FAIL: Custom patterns not working\n")
        return False


def test_state_persistence():
    """Test that content is stored in state for future diffs."""
    print("Test 5: State persistence for semantic diff")
    print("-" * 60)
    
    # This is more of a documentation test - verify the monitor code
    # stores 'last_content' in state
    
    with open(Path(__file__).parent.parent / 'scripts' / 'monitor_daemon.py', 'r') as f:
        monitor_code = f.read()
    
    has_last_content = "'last_content'" in monitor_code or '"last_content"' in monitor_code
    has_truncation = "[:50000]" in monitor_code  # Content truncation
    
    print(f"  Monitor stores 'last_content': {has_last_content}")
    print(f"  Monitor truncates content: {has_truncation}")
    
    if has_last_content and has_truncation:
        print("  ✅ PASS: State persistence implemented\n")
        return True
    else:
        print("  ❌ FAIL: State persistence not properly implemented\n")
        return False


if __name__ == '__main__':
    print("="*70)
    print("SEMANTIC DIFF INTEGRATION - TEST SUITE")
    print("="*70 + "\n")
    
    results = []
    
    try:
        results.append(test_monitor_ignores_noise())
        results.append(test_monitor_detects_real_change())
        results.append(test_threshold_configuration())
        results.append(test_custom_patterns())
        results.append(test_state_persistence())
        
        print("="*70)
        if all(results):
            print("✅ ALL INTEGRATION TESTS PASSED!")
            print("="*70)
            sys.exit(0)
        else:
            failed = sum(1 for r in results if not r)
            print(f"❌ {failed}/{len(results)} TESTS FAILED")
            print("="*70)
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
