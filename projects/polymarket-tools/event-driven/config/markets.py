"""
Market mapping configuration for Polymarket.
Maps keywords, entities, and categories to specific market slugs.
UPDATED: 2026-02-03 with REAL Polymarket slugs
"""

# Main market mapping: keyword/entity → list of Polymarket market slugs
MARKET_MAPPING = {
    # Trump-related markets (REAL SLUGS)
    "trump": [
        "how-many-people-will-trump-deport-in-2025",
        "will-trump-deport-750000-or-more-people-in-2025",
        "trump-cabinet-member-out-by",
    ],
    "deportation": [
        "how-many-people-will-trump-deport-in-2025",
        "will-trump-deport-750000-or-more-people-in-2025",
    ],
    "doge": [
        "how-much-spending-will-elon-and-doge-cut-in-2025",
        "will-elon-cut-the-budget-by-at-least-10-in-2025",
        "will-elon-cut-the-budget-by-at-least-5-in-2025",
    ],
    "elon": [
        "how-much-spending-will-elon-and-doge-cut-in-2025",
        "will-elon-cut-the-budget-by-at-least-10-in-2025",
    ],
    
    # Russia-Ukraine (REAL SLUGS)
    "russia": [
        "natoeu-troops-fighting-in-ukraine-in-2025",
        "ukraine-recognizes-russian-sovereignty-over-ukrainian-territory-in-2025",
    ],
    "ukraine": [
        "natoeu-troops-fighting-in-ukraine-in-2025",
        "ukraine-recognizes-russian-sovereignty-over-ukrainian-territory-in-2025",
        "ukraine-election-called-in-2025",
        "ukraine-election-held-in-2025",
    ],
    "nato": [
        "natoeu-troops-fighting-in-ukraine-in-2025",
        "will-any-country-leave-nato-in-2025",
    ],
    
    # Crypto (REAL SLUGS)
    "microstrategy": [
        "microstrategy-sell-any-bitcoin-in-2025",
    ],
    "bitcoin": [
        "microstrategy-sell-any-bitcoin-in-2025",
    ],
    "btc": [
        "microstrategy-sell-any-bitcoin-in-2025",
    ],
    "kraken": [
        "kraken-ipo-in-2025",
    ],
    "ipo": [
        "kraken-ipo-in-2025",
    ],
    
    # Gaming (REAL SLUGS)  
    "gta": [
        "will-gta-6-cost-100",
    ],
    "gta 6": [
        "will-gta-6-cost-100",
    ],
    
    # European Politics (REAL SLUGS)
    "macron": [
        "macron-out-in-2025",
    ],
    "france": [
        "macron-out-in-2025",
    ],
    "starmer": [
        "starmer-out-in-2025",
    ],
    "uk election": [
        "uk-election-called-by",
    ],
    
    # China (REAL SLUGS)
    "china": [
        "china-x-india-military-clash-by-december-31",
    ],
    "india": [
        "china-x-india-military-clash-by-december-31",
    ],
}

# Category mapping: category → list of market slugs
CATEGORY_MAPPING = {
    "politics_us": [
        "how-many-people-will-trump-deport-in-2025",
        "trump-cabinet-member-out-by",
        "how-much-spending-will-elon-and-doge-cut-in-2025",
    ],
    "geopolitics": [
        "natoeu-troops-fighting-in-ukraine-in-2025",
        "ukraine-recognizes-russian-sovereignty-over-ukrainian-territory-in-2025",
        "china-x-india-military-clash-by-december-31",
        "will-any-country-leave-nato-in-2025",
    ],
    "crypto": [
        "microstrategy-sell-any-bitcoin-in-2025",
        "kraken-ipo-in-2025",
    ],
    "entertainment": [
        "will-gta-6-cost-100",
    ],
}

# Direction hints: market_slug → {"bullish_keywords": [], "bearish_keywords": []}
MARKET_DIRECTION_HINTS = {
    "how-many-people-will-trump-deport-in-2025": {
        "bullish_keywords": ["record", "mass", "surge", "increase", "accelerate"],
        "bearish_keywords": ["slow", "halt", "court", "blocked", "delay"],
    },
    "natoeu-troops-fighting-in-ukraine-in-2025": {
        "bullish_keywords": ["troops", "deploy", "nato", "escalation", "intervention"],
        "bearish_keywords": ["ceasefire", "peace", "negotiate", "withdraw"],
    },
    "macron-out-in-2025": {
        "bullish_keywords": ["resign", "quit", "step down", "crisis", "vote of no confidence"],
        "bearish_keywords": ["support", "stable", "coalition", "survive"],
    },
    "microstrategy-sell-any-bitcoin-in-2025": {
        "bullish_keywords": ["sell", "liquidate", "forced", "margin call"],
        "bearish_keywords": ["buy more", "hodl", "accumulate", "treasury"],
    },
}

# Fuzzy match configuration
FUZZY_MATCH_THRESHOLD = 0.6
MIN_RELEVANCE_SCORE = 0.3

# Aliases for common variations
MARKET_ALIASES = {
    "trump deportations": "how-many-people-will-trump-deport-in-2025",
    "ukraine war": "natoeu-troops-fighting-in-ukraine-in-2025", 
    "russia ukraine": "natoeu-troops-fighting-in-ukraine-in-2025",
    "elon budget": "will-elon-cut-the-budget-by-at-least-10-in-2025",
    "doge cuts": "how-much-spending-will-elon-and-doge-cut-in-2025",
}
