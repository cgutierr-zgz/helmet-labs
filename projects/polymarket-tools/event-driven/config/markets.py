"""
Market mapping configuration for Polymarket.
Maps keywords, entities, and categories to specific market slugs.
"""

# Main market mapping: keyword/entity → list of Polymarket market slugs
MARKET_MAPPING = {
    # Trump-related markets
    "trump": [
        "will-trump-be-impeached-2025",
        "trump-deportations-2025", 
        "trump-tariffs-revenue",
        "trump-approval-rating-2025"
    ],
    "donald trump": [
        "will-trump-be-impeached-2025",
        "trump-deportations-2025",
        "trump-tariffs-revenue"
    ],
    
    # Federal Reserve / Monetary Policy
    "fed": [
        "fed-rate-cut-march-2025",
        "inflation-above-3-percent",
        "fed-rate-cut-december-2025"
    ],
    "federal reserve": [
        "fed-rate-cut-march-2025",
        "inflation-above-3-percent"
    ],
    "jerome powell": [
        "fed-rate-cut-march-2025",
        "inflation-above-3-percent"
    ],
    "fomc": [
        "fed-rate-cut-march-2025",
        "fed-rate-cut-december-2025"
    ],
    "interest rates": [
        "fed-rate-cut-march-2025",
        "fed-rate-cut-december-2025"
    ],
    "inflation": [
        "inflation-above-3-percent"
    ],
    
    # Russia-Ukraine conflict
    "russia": [
        "russia-ukraine-ceasefire-2025",
        "zelensky-president-end-2025",
        "putin-president-end-2025"
    ],
    "ukraine": [
        "russia-ukraine-ceasefire-2025",
        "zelensky-president-end-2025"
    ],
    "russia_ukraine": [
        "russia-ukraine-ceasefire-2025",
        "zelensky-president-end-2025"
    ],
    "zelensky": [
        "zelensky-president-end-2025"
    ],
    "putin": [
        "putin-president-end-2025"
    ],
    
    # Cryptocurrency
    "btc": [
        "btc-above-100k-2025",
        "btc-above-150k-2025",
        "btc-below-50k-2025"
    ],
    "bitcoin": [
        "btc-above-100k-2025",
        "btc-above-150k-2025",
        "btc-below-50k-2025"
    ],
    "ethereum": [
        "eth-above-5k-2025",
        "eth-staking-rewards-2025"
    ],
    "crypto": [
        "btc-above-100k-2025",
        "crypto-regulation-2025"
    ],
    "sec": [
        "crypto-regulation-2025",
        "bitcoin-etf-approval"
    ],
    
    # Gaming / Entertainment
    "gta": [
        "gta-6-release-2025",
        "gta-6-price-above-100"
    ],
    "gta 6": [
        "gta-6-release-2025", 
        "gta-6-price-above-100"
    ],
    "grand theft auto": [
        "gta-6-release-2025",
        "gta-6-price-above-100"
    ],
    "rockstar": [
        "gta-6-release-2025"
    ],
    
    # Tech / AI
    "openai": [
        "openai-ipo-2025",
        "gpt5-release-2025"
    ],
    "chatgpt": [
        "gpt5-release-2025"
    ],
    "nvidia": [
        "nvidia-above-200-2025"
    ],
    
    # Elections / Politics
    "biden": [
        "biden-2024-election",
        "biden-approval-rating"
    ],
    "election": [
        "biden-2024-election",
        "trump-2024-election"
    ]
}

# Category-based market mapping
CATEGORY_MAPPING = {
    "fed": [
        "fed-rate-cut-march-2025",
        "inflation-above-3-percent",
        "fed-rate-cut-december-2025"
    ],
    "crypto": [
        "btc-above-100k-2025",
        "btc-above-150k-2025",
        "eth-above-5k-2025"
    ],
    "politics": [
        "will-trump-be-impeached-2025",
        "biden-approval-rating",
        "election-2024-winner"
    ],
    "geopolitics": [
        "russia-ukraine-ceasefire-2025",
        "zelensky-president-end-2025",
        "putin-president-end-2025"
    ],
    "entertainment": [
        "gta-6-release-2025",
        "gta-6-price-above-100"
    ],
    "tech": [
        "openai-ipo-2025",
        "gpt5-release-2025",
        "nvidia-above-200-2025"
    ]
}

# Market direction hints based on event sentiment
MARKET_DIRECTION_HINTS = {
    # FED markets - rate cuts generally bullish for markets, bearish for rate cut predictions
    "fed-rate-cut-march-2025": {
        "hawkish": "bearish",  # Less likely rate cut
        "dovish": "bullish",   # More likely rate cut
        "inflation": "bearish", # High inflation = less likely cut
        "employment": "neutral"
    },
    "inflation-above-3-percent": {
        "inflation": "bullish", # High inflation = bullish for this market
        "cpi": "bullish",
        "pce": "bullish"
    },
    
    # Crypto markets
    "btc-above-100k-2025": {
        "bullish": "bullish",
        "bearish": "bearish",
        "adoption": "bullish",
        "regulation": "bearish",
        "etf": "bullish"
    },
    
    # Gaming
    "gta-6-release-2025": {
        "delay": "bearish",
        "development": "neutral",
        "release": "bullish",
        "trailer": "bullish"
    }
}

# Fuzzy matching configuration
FUZZY_MATCH_THRESHOLD = 0.8
MIN_RELEVANCE_SCORE = 0.1

# Market slug aliases for fuzzy matching
MARKET_ALIASES = {
    "trump-impeachment": "will-trump-be-impeached-2025",
    "bitcoin-100k": "btc-above-100k-2025",
    "fed-rates": "fed-rate-cut-march-2025",
    "ukraine-peace": "russia-ukraine-ceasefire-2025",
    "gta6": "gta-6-release-2025"
}