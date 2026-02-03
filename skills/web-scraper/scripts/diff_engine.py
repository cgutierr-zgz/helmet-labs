#!/usr/bin/env python3
"""
Semantic Diff Engine - Detects significant content changes while ignoring noise.

Filters out HTML noise like timestamps, session IDs, ads, counters to reduce
false positives in change detection.
"""

import re
from typing import Tuple, List
from difflib import SequenceMatcher


class SemanticDiff:
    """
    Semantic diff engine that ignores noise and detects meaningful changes.
    
    Usage:
        diff = SemanticDiff(threshold=0.1)
        is_sig, ratio, summary = diff.is_significant_change(old_html, new_html)
        if is_sig:
            print(f"Change detected: {ratio:.1%} - {summary}")
    """
    
    # Default patterns to ignore (can be extended per-source)
    DEFAULT_NOISE_PATTERNS = [
        r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?',  # ISO timestamps
        r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}',  # datetime stamps
        r'\d{10,13}',  # Unix timestamps (10-13 digits)
        r'session[_-]?id[=:][a-zA-Z0-9]+',  # Session IDs
        r'token[=:][a-zA-Z0-9]+',  # Tokens
        r'csrf[_-]?token[=:][a-zA-Z0-9]+',  # CSRF tokens
        r'_ga=[^&\s]+',  # Google Analytics
        r'_gid=[^&\s]+',  # Google Analytics ID
        r'fbclid=[^&\s]+',  # Facebook click ID
        r'utm_[a-z]+=[^&\s]+',  # UTM tracking params
        r'\d+\s*(views?|visits?|visitors?|clicks?)',  # View/visit counters (e.g., "100 views")
        r'(views?|visits?|visitors?|clicks?)[:=\s]+\d+',  # Counters with label first (e.g., "Views: 100")
        r'posted\s+\d+\s+(second|minute|hour|day)s?\s+ago',  # Relative timestamps
        r'\d+\s+(second|minute|hour|day)s?\s+ago',  # "5 minutes ago"
        r'cache[_-]?buster[=:][a-zA-Z0-9]+',  # Cache busters
        r'\?v=\d+',  # Version query params
        r'&amp;t=\d+',  # Timestamp query params
        r'nonce[=:][a-zA-Z0-9]+',  # Nonces
        r'__RequestVerificationToken[^&\s]*',  # ASP.NET tokens
        r'PHPSESSID=[^&\s]+',  # PHP session IDs
        r'JSESSIONID=[^&\s]+',  # Java session IDs
    ]
    
    def __init__(self, threshold: float = 0.1, custom_patterns: List[str] = None):
        """
        Initialize semantic diff engine.
        
        Args:
            threshold: Minimum ratio of changed content to consider significant (0.1 = 10%)
            custom_patterns: Additional regex patterns to ignore (beyond defaults)
        """
        self.threshold = threshold
        self.noise_patterns = self.DEFAULT_NOISE_PATTERNS.copy()
        
        if custom_patterns:
            self.noise_patterns.extend(custom_patterns)
        
        # Compile patterns for performance
        self._compiled_patterns = [
            re.compile(pattern, flags=re.IGNORECASE) 
            for pattern in self.noise_patterns
        ]
    
    def normalize(self, text: str) -> str:
        """
        Remove noise patterns from text and normalize whitespace.
        
        Args:
            text: Raw text content (HTML, JSON, etc.)
            
        Returns:
            Normalized text with noise removed
        """
        result = text
        
        # Remove all noise patterns
        for pattern in self._compiled_patterns:
            result = pattern.sub('', result)
        
        # Normalize whitespace: collapse multiple spaces/newlines to single space
        result = ' '.join(result.split())
        
        return result
    
    def is_significant_change(self, old: str, new: str) -> Tuple[bool, float, str]:
        """
        Compare two texts and determine if the change is significant.
        
        Args:
            old: Previous version of content
            new: New version of content
            
        Returns:
            Tuple of (is_significant, change_ratio, diff_summary):
                - is_significant: True if change exceeds threshold
                - change_ratio: Float 0.0-1.0 indicating how much changed
                - diff_summary: Human-readable summary of what changed
        """
        # Normalize both versions
        old_norm = self.normalize(old)
        new_norm = self.normalize(new)
        
        # If identical after normalization, it's just noise
        if old_norm == new_norm:
            return (False, 0.0, "No significant change (noise only)")
        
        # Calculate similarity ratio using difflib
        ratio = SequenceMatcher(None, old_norm, new_norm).ratio()
        change_ratio = 1 - ratio
        
        # Generate diff summary by comparing word sets
        old_words = set(old_norm.split())
        new_words = set(new_norm.split())
        added = new_words - old_words
        removed = old_words - new_words
        
        # Build human-readable summary
        diff_parts = []
        if added:
            # Show first 20 added words
            added_sample = ' '.join(sorted(added)[:20])
            diff_parts.append(f"Added: {added_sample}")
            if len(added) > 20:
                diff_parts.append(f"(+{len(added)-20} more)")
        
        if removed:
            # Show first 10 removed words
            removed_sample = ' '.join(sorted(removed)[:10])
            diff_parts.append(f"Removed: {removed_sample}")
            if len(removed) > 10:
                diff_parts.append(f"(-{len(removed)-10} more)")
        
        diff_summary = " | ".join(diff_parts) if diff_parts else "Content modified"
        
        # Check if change exceeds threshold
        is_significant = change_ratio >= self.threshold
        
        return (is_significant, change_ratio, diff_summary)
    
    def extract_new_items(self, old_items: List[str], new_items: List[str]) -> List[str]:
        """
        For parsed feed items, find truly new items (not just reordered).
        
        Compares by normalized content, not exact match. This prevents
        treating reordered items as "new".
        
        Args:
            old_items: List of previous item contents
            new_items: List of current item contents
            
        Returns:
            List of truly new items (normalized content not in old set)
        """
        # Normalize all old items into a set for O(1) lookup
        old_normalized = {self.normalize(item) for item in old_items}
        
        # Find items in new that aren't in old (by normalized content)
        new_unique = []
        for item in new_items:
            if self.normalize(item) not in old_normalized:
                new_unique.append(item)
        
        return new_unique
    
    def get_change_summary(self, old: str, new: str, max_chars: int = 200) -> str:
        """
        Get a concise summary of what changed (for logging/debugging).
        
        Args:
            old: Previous content
            new: New content
            max_chars: Maximum characters in summary
            
        Returns:
            Brief summary of changes
        """
        is_sig, ratio, summary = self.is_significant_change(old, new)
        
        if not is_sig:
            return f"No significant change (noise only, {ratio:.1%})"
        
        result = f"Changed {ratio:.1%}: {summary}"
        
        if len(result) > max_chars:
            result = result[:max_chars-3] + "..."
        
        return result


def create_diff_engine(source_config: dict) -> SemanticDiff:
    """
    Factory function to create a SemanticDiff instance from source config.
    
    Reads per-source configuration:
        - diff_threshold: Override default 0.1 threshold
        - ignore_patterns: Additional regex patterns to ignore
    
    Args:
        source_config: Source dict from sources.json
        
    Returns:
        Configured SemanticDiff instance
    """
    threshold = source_config.get('diff_threshold', 0.1)
    custom_patterns = source_config.get('ignore_patterns', [])
    
    return SemanticDiff(threshold=threshold, custom_patterns=custom_patterns)


# === Example Usage ===
if __name__ == '__main__':
    # Example: Detect changes in HTML with timestamps
    
    old_html = """
    <div class="article">
        <h1>Breaking News</h1>
        <p>Published: 2024-01-15T10:30:00Z</p>
        <p>Views: 1234</p>
        <p>The Fed announces rate decision.</p>
    </div>
    """
    
    # Case 1: Only noise changed (timestamp, views)
    new_html_noise = """
    <div class="article">
        <h1>Breaking News</h1>
        <p>Published: 2024-01-15T11:45:00Z</p>
        <p>Views: 5678</p>
        <p>The Fed announces rate decision.</p>
    </div>
    """
    
    # Case 2: Real content changed
    new_html_real = """
    <div class="article">
        <h1>Breaking News</h1>
        <p>Published: 2024-01-15T11:45:00Z</p>
        <p>Views: 5678</p>
        <p>The Fed announces rate increase to 5.5%.</p>
    </div>
    """
    
    diff = SemanticDiff(threshold=0.05)
    
    print("Test 1: Only noise changed")
    is_sig, ratio, summary = diff.is_significant_change(old_html, new_html_noise)
    print(f"  Significant: {is_sig}, Ratio: {ratio:.1%}")
    print(f"  Summary: {summary}\n")
    
    print("Test 2: Real content changed")
    is_sig, ratio, summary = diff.is_significant_change(old_html, new_html_real)
    print(f"  Significant: {is_sig}, Ratio: {ratio:.1%}")
    print(f"  Summary: {summary}")
