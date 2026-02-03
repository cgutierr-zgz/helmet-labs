"""
Event classification categories and configuration.
Defines categories, keywords, market mappings, and base scores.
"""

import re
from typing import Dict, List, Set, Pattern

CATEGORIES = {
    "POLITICS_US": {
        "keywords": ["trump", "biden", "congress", "white house", "executive order", 
                    "senate", "house", "republican", "democrat", "gop", "inauguration",
                    "cabinet", "supreme court", "scotus", "impeachment", "veto"],
        "markets": ["trump_*", "election_*", "policy_*", "politics_*"],
        "base_score": 7,
        "patterns": [
            re.compile(r'\btrump\b', re.IGNORECASE),
            re.compile(r'\bwhite\s+house\b', re.IGNORECASE),
            re.compile(r'\bexecutive\s+order\b', re.IGNORECASE),
        ]
    },
    "FED_MONETARY": {
        "keywords": ["fomc", "fed", "rate cut", "rate hike", "powell", "basis points",
                    "federal reserve", "interest rate", "monetary policy", "inflation",
                    "cpi", "unemployment", "jobs report", "wage growth"],
        "markets": ["fed_*", "inflation_*", "rates_*", "economy_*"],
        "base_score": 9,
        "patterns": [
            re.compile(r'\bfed\b', re.IGNORECASE),
            re.compile(r'\bfomc\b', re.IGNORECASE),
            re.compile(r'\brate\s+(cut|hike)\b', re.IGNORECASE),
            re.compile(r'\bbasis\s+points?\b', re.IGNORECASE),
        ]
    },
    "GEOPOLITICS": {
        "keywords": ["russia", "ukraine", "china", "taiwan", "war", "invasion",
                    "nato", "putin", "xi jinping", "military", "sanctions", 
                    "ceasefire", "conflict", "peace talks", "missile", "attack"],
        "markets": ["ukraine_*", "taiwan_*", "conflict_*", "war_*", "china_*"],
        "base_score": 8,
        "patterns": [
            re.compile(r'\b(russia|ukraine)\b', re.IGNORECASE),
            re.compile(r'\b(china|taiwan)\b', re.IGNORECASE),
            re.compile(r'\b(war|invasion|conflict)\b', re.IGNORECASE),
        ]
    },
    "CRYPTO": {
        "keywords": ["bitcoin", "btc", "ethereum", "crypto", "sec", "etf",
                    "blockchain", "altcoin", "defi", "nft", "mining", "whale",
                    "coinbase", "binance", "regulation", "custody", "wallet"],
        "markets": ["btc_*", "crypto_*", "ethereum_*", "regulation_*"],
        "base_score": 6,
        "patterns": [
            re.compile(r'\b(bitcoin|btc)\b', re.IGNORECASE),
            re.compile(r'\b(ethereum|eth)\b', re.IGNORECASE),
            re.compile(r'\bcrypto\b', re.IGNORECASE),
        ]
    },
    "ENTERTAINMENT": {
        "keywords": ["gta", "rockstar", "game release", "movie", "netflix",
                    "disney", "streaming", "box office", "gaming", "ps5", "xbox",
                    "apple tv", "hbo", "amazon prime", "meta", "vr"],
        "markets": ["gta_*", "entertainment_*", "gaming_*", "streaming_*"],
        "base_score": 5,
        "patterns": [
            re.compile(r'\bgta\s*(6|vi)\b', re.IGNORECASE),
            re.compile(r'\brockstar\s+games?\b', re.IGNORECASE),
            re.compile(r'\bgame\s+release\b', re.IGNORECASE),
        ]
    }
}

# Entity extraction patterns
ENTITY_PATTERNS = {
    "person": re.compile(r'\b([A-Z][a-z]+ [A-Z][a-z]+)\b'),
    "number": re.compile(r'\b(\d+(?:\.\d+)?(?:%|bp|bps|million|billion|trillion)?)\b'),
    "date": re.compile(r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\w+ \d{1,2}, \d{4})\b'),
    "money": re.compile(r'\$\d+(?:\.\d+)?(?:k|m|b|t)?', re.IGNORECASE),
    "percent": re.compile(r'\d+(?:\.\d+)?%'),
    "organization": re.compile(r'\b([A-Z][A-Z0-9&]{2,})\b'),  # Acronyms like SEC, FBI, etc.
}

# Urgency modifiers
URGENCY_KEYWORDS = {
    "breaking": 3.0,
    "urgent": 3.0, 
    "alert": 2.5,
    "just in": 2.5,
    "emergency": 3.0,
    "immediate": 2.5,
    "live": 2.0,
    "now": 1.5,
    "announced": 2.0,
    "confirms": 1.8,
    "official": 1.5,
    "exclusive": 1.3,
    "first": 1.2
}

# Source tier modifiers
SOURCE_MODIFIERS = {
    "tier1_breaking": 2.0,
    "tier2_reliable": 1.0,
    "tier3_general": 0.0
}

def get_category_names() -> List[str]:
    """Get list of all category names."""
    return list(CATEGORIES.keys())

def get_keywords_for_category(category: str) -> List[str]:
    """Get keywords for a specific category."""
    return CATEGORIES.get(category, {}).get("keywords", [])

def get_markets_for_category(category: str) -> List[str]:
    """Get market patterns for a specific category."""
    return CATEGORIES.get(category, {}).get("markets", [])

def get_base_score_for_category(category: str) -> int:
    """Get base score for a specific category."""
    return CATEGORIES.get(category, {}).get("base_score", 5)