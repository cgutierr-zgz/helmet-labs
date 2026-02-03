#!/usr/bin/env python3
"""
Demonstration of semantic diff engine for web scraper.

Shows how the engine correctly:
1. Ignores timestamp-only changes (no alert)
2. Detects real content changes (alerts)
"""

import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent / 'scripts'))

from diff_engine import SemanticDiff


def demo():
    """Run demonstration of semantic diff functionality."""
    
    print("=" * 70)
    print("SEMANTIC DIFF ENGINE - DEMONSTRATION")
    print("=" * 70)
    print()
    
    # Create diff engine with 10% threshold (default)
    diff = SemanticDiff(threshold=0.1)
    
    # === SCENARIO 1: Only noise changed (timestamp, session ID, views) ===
    print("SCENARIO 1: Only noise changed (timestamp, session, views)")
    print("-" * 70)
    
    old_page = """
    <html>
    <body>
        <h1>Fed Rate Decision</h1>
        <article>
            <p>Published: 2024-01-15T10:30:00Z</p>
            <p>Session: sess_abc123</p>
            <p>Views: 1,234</p>
            <div class="content">
                The Federal Reserve announced today that interest rates
                will remain unchanged at 5.25% to 5.50%.
            </div>
        </article>
    </body>
    </html>
    """
    
    new_page_noise = """
    <html>
    <body>
        <h1>Fed Rate Decision</h1>
        <article>
            <p>Published: 2024-01-15T14:45:00Z</p>
            <p>Session: sess_xyz789</p>
            <p>Views: 8,567</p>
            <div class="content">
                The Federal Reserve announced today that interest rates
                will remain unchanged at 5.25% to 5.50%.
            </div>
        </article>
    </body>
    </html>
    """
    
    is_sig, ratio, summary = diff.is_significant_change(old_page, new_page_noise)
    
    print(f"Old content: {len(old_page)} bytes")
    print(f"New content: {len(new_page_noise)} bytes")
    print(f"\nResult:")
    print(f"  Significant: {is_sig}")
    print(f"  Change ratio: {ratio:.2%}")
    print(f"  Summary: {summary}")
    
    if is_sig:
        print("\n❌ ALERT: Would generate event (UNEXPECTED)")
    else:
        print("\n✅ NO ALERT: Noise correctly ignored (EXPECTED)")
    
    print()
    
    # === SCENARIO 2: Real content changed ===
    print("SCENARIO 2: Real content changed (rate increase announced)")
    print("-" * 70)
    
    new_page_real = """
    <html>
    <body>
        <h1>Fed Rate Decision</h1>
        <article>
            <p>Published: 2024-01-15T16:00:00Z</p>
            <p>Session: sess_def456</p>
            <p>Views: 15,234</p>
            <div class="content">
                The Federal Reserve announced today a surprise rate increase
                to 5.50% to 5.75%, citing persistent inflation concerns.
                Markets reacted sharply to the news.
            </div>
        </article>
    </body>
    </html>
    """
    
    is_sig, ratio, summary = diff.is_significant_change(old_page, new_page_real)
    
    print(f"Old content: {len(old_page)} bytes")
    print(f"New content: {len(new_page_real)} bytes")
    print(f"\nResult:")
    print(f"  Significant: {is_sig}")
    print(f"  Change ratio: {ratio:.2%}")
    print(f"  Summary: {summary[:150]}...")
    
    if is_sig:
        print("\n✅ ALERT: Would generate event (EXPECTED)")
    else:
        print("\n❌ NO ALERT: Real change not detected (UNEXPECTED)")
    
    print()
    
    # === SCENARIO 3: Custom patterns ===
    print("SCENARIO 3: Custom ignore patterns (document IDs)")
    print("-" * 70)
    
    # Create diff with custom pattern for document IDs
    diff_custom = SemanticDiff(
        threshold=0.1,
        custom_patterns=[r'Document #\d+', r'File-\d{4}-\d{3}']
    )
    
    old_doc = "Document #12345: SEC filing approved. File-2024-001"
    new_doc = "Document #98765: SEC filing approved. File-2024-999"
    
    is_sig, ratio, summary = diff_custom.is_significant_change(old_doc, new_doc)
    
    print(f"Old: {old_doc}")
    print(f"New: {new_doc}")
    print(f"\nResult:")
    print(f"  Significant: {is_sig}")
    print(f"  Change ratio: {ratio:.2%}")
    
    if is_sig:
        print("\n❌ ALERT: Custom patterns not working (UNEXPECTED)")
    else:
        print("\n✅ NO ALERT: Custom patterns correctly ignored (EXPECTED)")
    
    print()
    print("=" * 70)
    print("DEMONSTRATION COMPLETE")
    print("=" * 70)


if __name__ == '__main__':
    demo()
