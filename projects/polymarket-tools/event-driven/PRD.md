# PRD: Event-Driven Trading System for Polymarket

## 1. Overview

### 1.1 Vision
Un sistema automatizado que monitorea fuentes de información en tiempo real, detecta eventos market-moving, y genera señales de trading accionables para mercados de predicción (Polymarket, Kalshi).

### 1.2 Goals
- **Primary**: Detectar eventos relevantes ANTES de que el mercado reaccione
- **Secondary**: Reducir ruido y falsos positivos al mínimo
- **Tertiary**: Generar recomendaciones de trading con confidence scores

### 1.3 Success Metrics
| Metric | MVP | Target | Stretch |
|--------|-----|--------|---------|
| Relevant alerts/day | 3-5 | 10-15 | 20+ |
| False positive rate | <50% | <20% | <10% |
| Event→Alert latency | <10 min | <2 min | <30 sec |
| Signal accuracy | >50% | >60% | >70% |

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA LAYER                                │
├─────────────┬─────────────┬─────────────┬─────────────┬─────────┤
│   RSS       │   Twitter   │  Webhooks   │   APIs      │ Scrapers│
│   Feeds     │   Stream    │  (alerts)   │  (markets)  │         │
└──────┬──────┴──────┬──────┴──────┬──────┴──────┬──────┴────┬────┘
       │             │             │             │           │
       └─────────────┴─────────────┴─────────────┴───────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                     PROCESSING LAYER                             │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │  Ingest  │→ │  Parse   │→ │ Classify │→ │  Score   │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                       │
│  │  Dedup   │→ │  Enrich  │→ │  Store   │                       │
│  └──────────┘  └──────────┘  └──────────┘                       │
└─────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                     INTELLIGENCE LAYER                           │
├─────────────────────────────────────────────────────────────────┤
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐     │
│  │ Market Mapping │  │ Price Fetcher  │  │ Signal Gen     │     │
│  │ (event→market) │  │ (Polymarket)   │  │ (BUY/SELL/HOLD)│     │
│  └────────────────┘  └────────────────┘  └────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                      OUTPUT LAYER                                │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ Telegram │  │ Dashboard│  │  Logs    │  │  Trades  │        │
│  │  Alerts  │  │   Web    │  │  JSONL   │  │  (future)│        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Components Specification

### 3.1 Data Sources (`sources/`)

#### 3.1.1 RSS Feeds
```python
RSS_FEEDS = {
    "tier1_breaking": [  # Check every 1 min
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://feeds.reuters.com/reuters/topNews",
    ],
    "tier2_politics": [  # Check every 5 min
        "https://feeds.reuters.com/Reuters/PoliticsNews",
        "https://thehill.com/feed/",
        "https://www.politico.com/rss/politicopicks.xml",
    ],
    "tier3_finance": [  # Check every 5 min
        "https://feeds.reuters.com/reuters/businessNews",
        "https://feeds.bloomberg.com/markets/news.rss",
    ],
}
```

#### 3.1.2 Twitter Accounts
```python
TWITTER_PRIORITY = {
    "critical": [  # Check every 1 min
        "BNONews", "disclosetv", "DeItaone", "unusual_whales"
    ],
    "politics": [  # Check every 5 min
        "realDonaldTrump", "WhiteHouse", "ABORDELOMKT"
    ],
    "crypto": [  # Check every 5 min
        "whale_alert", "DocumentingBTC", "tier10k"
    ],
    "geopolitics": [  # Check every 10 min
        "TheStudyofWar", "sentdefender", "RALee85"
    ],
}
```

### 3.2 Event Classification (`classifier.py`)

#### Categories
```python
CATEGORIES = {
    "POLITICS_US": {
        "keywords": ["trump", "biden", "congress", "white house", "executive order"],
        "markets": ["trump_*", "election_*", "policy_*"],
        "base_score": 7
    },
    "FED_MONETARY": {
        "keywords": ["fomc", "fed", "rate cut", "rate hike", "powell", "basis points"],
        "markets": ["fed_*", "inflation_*", "rates_*"],
        "base_score": 9
    },
    "GEOPOLITICS": {
        "keywords": ["russia", "ukraine", "china", "taiwan", "war", "invasion"],
        "markets": ["ukraine_*", "taiwan_*", "conflict_*"],
        "base_score": 8
    },
    "CRYPTO": {
        "keywords": ["bitcoin", "btc", "ethereum", "crypto", "sec"],
        "markets": ["btc_*", "crypto_*"],
        "base_score": 6
    },
    "ENTERTAINMENT": {
        "keywords": ["gta", "rockstar", "game release", "movie"],
        "markets": ["gta_*", "entertainment_*"],
        "base_score": 5
    }
}
```

#### Scoring Algorithm
```python
def calculate_score(event) -> int:
    score = CATEGORIES[event.category]["base_score"]
    
    # Source reliability modifier
    if event.source in TIER1_SOURCES: score += 2
    if event.source in TIER2_SOURCES: score += 1
    
    # Recency modifier
    if event.age_minutes < 5: score += 2
    elif event.age_minutes < 15: score += 1
    elif event.age_minutes > 60: score -= 2
    
    # Confirmation modifier
    if event.confirmed_by_multiple_sources: score += 2
    
    # Market impact modifier
    if event.contains_numbers: score += 1  # Specific data
    if event.is_breaking: score += 2
    
    return min(max(score, 1), 10)  # Clamp to 1-10
```

### 3.3 Deduplication (`dedup.py`)

```python
def is_duplicate(new_event, recent_events, threshold=0.8):
    """
    Check if event is duplicate using:
    1. Exact URL match
    2. Title similarity (Levenshtein)
    3. Content hash
    4. Entity extraction overlap
    """
    for existing in recent_events:
        # URL match
        if new_event.url == existing.url:
            return True
        
        # Title similarity
        similarity = levenshtein_ratio(new_event.title, existing.title)
        if similarity > threshold:
            return True
        
        # Same entities + same category + within 1 hour
        if (new_event.entities & existing.entities 
            and new_event.category == existing.category
            and new_event.age_diff(existing) < 3600):
            return True
    
    return False
```

### 3.4 Market Mapping (`markets.py`)

```python
MARKET_MAPPING = {
    # Pattern: keyword/entity → list of Polymarket market slugs
    "trump": [
        "will-trump-be-impeached-2025",
        "trump-deportations-2025",
        "trump-tariffs-revenue"
    ],
    "fed": [
        "fed-rate-cut-march-2025",
        "inflation-above-3-percent"
    ],
    "russia_ukraine": [
        "russia-ukraine-ceasefire-2025",
        "zelensky-president-end-2025"
    ],
    "btc": [
        "btc-above-100k-2025",
        "btc-above-150k-2025"
    ],
    "gta": [
        "gta-6-release-2025",
        "gta-6-price-above-100"
    ]
}

def get_affected_markets(event):
    """Return list of markets potentially affected by this event."""
    markets = []
    for key, market_list in MARKET_MAPPING.items():
        if key in event.text.lower() or key in event.entities:
            markets.extend(market_list)
    return list(set(markets))
```

### 3.5 Signal Generation (`signals.py`)

```python
@dataclass
class Signal:
    market_id: str
    direction: Literal["BUY_YES", "BUY_NO", "HOLD"]
    confidence: float  # 0.0 - 1.0
    reasoning: str
    current_price: float
    expected_price: float
    event_id: str

def generate_signal(event, market) -> Signal:
    """
    Generate trading signal based on event and current market state.
    """
    current_price = fetch_market_price(market.id)
    
    # Determine direction based on event sentiment
    sentiment = analyze_sentiment(event, market)
    
    if sentiment > 0.6:
        direction = "BUY_YES"
        expected_move = sentiment * 0.1  # Max 10% move
    elif sentiment < 0.4:
        direction = "BUY_NO" 
        expected_move = (1 - sentiment) * 0.1
    else:
        direction = "HOLD"
        expected_move = 0
    
    expected_price = current_price + (expected_move if direction == "BUY_YES" else -expected_move)
    
    # Calculate confidence
    confidence = calculate_confidence(event, market, current_price)
    
    return Signal(
        market_id=market.id,
        direction=direction,
        confidence=confidence,
        reasoning=f"Event: {event.title[:100]}... Sentiment: {sentiment:.2f}",
        current_price=current_price,
        expected_price=expected_price,
        event_id=event.id
    )
```

### 3.6 Alert Output (`alerts.py`)

```python
def format_alert(event, signals) -> str:
    """Format alert for Telegram notification."""
    
    emoji = {
        1-3: "🟢",   # Low priority
        4-6: "🟡",   # Medium
        7-8: "🟠",   # High
        9-10: "🔴"   # Critical
    }[event.score]
    
    msg = f"""
{emoji} **{event.category}** (Score: {event.score}/10)

📰 {event.title}

🔗 {event.url}

⏰ {event.timestamp} ({event.age_minutes}m ago)
📡 Source: {event.source}
"""
    
    if signals:
        msg += "\n**Affected Markets:**\n"
        for s in signals:
            arrow = "📈" if s.direction == "BUY_YES" else "📉" if s.direction == "BUY_NO" else "➖"
            msg += f"{arrow} {s.market_id}: {s.direction} (conf: {s.confidence:.0%})\n"
            msg += f"   Current: {s.current_price:.0%} → Expected: {s.expected_price:.0%}\n"
    
    return msg
```

---

## 4. Implementation Tasks

### Sprint 1: Core Infrastructure (Week 1)
- [ ] **TASK-001**: Refactor scan.py into modular components
- [ ] **TASK-002**: Implement improved RSS fetcher with tiers
- [ ] **TASK-003**: Add Twitter fetcher with rate limiting
- [ ] **TASK-004**: Create event data model and storage

### Sprint 2: Intelligence (Week 2)
- [ ] **TASK-005**: Implement classifier with scoring
- [ ] **TASK-006**: Add deduplication logic
- [ ] **TASK-007**: Create market mapping database
- [ ] **TASK-008**: Implement Polymarket price fetcher

### Sprint 3: Signals & Alerts (Week 3)
- [ ] **TASK-009**: Build signal generation logic
- [ ] **TASK-010**: Create Telegram alert integration
- [ ] **TASK-011**: Add alert formatting and priorities
- [ ] **TASK-012**: Implement alert rate limiting (no spam)

### Sprint 4: Polish & Testing (Week 4)
- [ ] **TASK-013**: Add comprehensive logging
- [ ] **TASK-014**: Write unit tests for core components
- [ ] **TASK-015**: Create backtest framework
- [ ] **TASK-016**: Documentation and deployment guide

---

## 5. File Structure

```
event-driven/
├── PRD.md                 # This document
├── ROADMAP.md             # High-level roadmap
├── README.md              # Quick start guide
├── requirements.txt       # Python dependencies
├── config/
│   ├── sources.json       # Data sources config
│   ├── markets.json       # Market mappings
│   └── settings.py        # Runtime settings
├── src/
│   ├── __init__.py
│   ├── fetchers/
│   │   ├── rss.py         # RSS feed fetcher
│   │   ├── twitter.py     # Twitter fetcher
│   │   └── polymarket.py  # Market data fetcher
│   ├── processors/
│   │   ├── classifier.py  # Event classification
│   │   ├── scorer.py      # Urgency scoring
│   │   └── dedup.py       # Deduplication
│   ├── intelligence/
│   │   ├── mapper.py      # Event→Market mapping
│   │   └── signals.py     # Signal generation
│   ├── outputs/
│   │   ├── telegram.py    # Telegram alerts
│   │   └── logger.py      # File logging
│   └── main.py            # Entry point
├── tests/
│   └── ...
└── data/
    ├── events.jsonl       # Event log
    ├── alerts.jsonl       # Alert log
    └── signals.jsonl      # Signal log
```

---

## 6. Configuration

### Environment Variables
```bash
# Required
TELEGRAM_BOT_TOKEN=xxx        # For alerts
TELEGRAM_CHAT_ID=xxx          # Where to send alerts

# Optional
TWITTER_BEARER_TOKEN=xxx      # For Twitter API (if not using bird CLI)
POLYMARKET_API_KEY=xxx        # For authenticated requests
LOG_LEVEL=INFO
SCAN_INTERVAL_SECONDS=60
```

### Runtime Settings
```python
# settings.py
SETTINGS = {
    "scan_interval": 60,           # Seconds between scans
    "min_score_to_alert": 6,       # Don't alert below this
    "max_alerts_per_hour": 10,     # Rate limiting
    "dedup_window_hours": 24,      # How long to remember events
    "price_fetch_timeout": 5,      # Seconds
}
```

---

## 7. Agent Task Assignment

Each task should be completable by a single sub-agent session.

### TASK-001: Refactor scan.py
**Input**: Current monolithic scan.py
**Output**: Modular structure with src/ directory
**Acceptance**: Code runs, existing functionality preserved

### TASK-002: RSS Fetcher
**Input**: RSS feed URLs from config
**Output**: src/fetchers/rss.py with tiered fetching
**Acceptance**: Fetches from all feeds, returns normalized events

### TASK-003: Twitter Fetcher  
**Input**: Twitter account lists from config
**Output**: src/fetchers/twitter.py using bird CLI
**Acceptance**: Fetches recent tweets, handles rate limits

### TASK-004: Event Data Model
**Input**: PRD specifications
**Output**: src/models.py with Event, Signal, Alert dataclasses
**Acceptance**: Type-safe data structures with serialization

### TASK-005: Classifier
**Input**: Raw event text
**Output**: src/processors/classifier.py
**Acceptance**: Categorizes events, returns category + keywords matched

### TASK-006: Scorer
**Input**: Classified event
**Output**: src/processors/scorer.py
**Acceptance**: Returns score 1-10 with reasoning

### TASK-007: Deduplicator
**Input**: New event + recent events
**Output**: src/processors/dedup.py
**Acceptance**: Correctly identifies duplicates with >90% accuracy

### TASK-008: Market Mapper
**Input**: Classified event
**Output**: src/intelligence/mapper.py
**Acceptance**: Returns relevant Polymarket market IDs

### TASK-009: Polymarket Fetcher
**Input**: Market IDs
**Output**: src/fetchers/polymarket.py
**Acceptance**: Returns current prices for markets

### TASK-010: Signal Generator
**Input**: Event + Market data
**Output**: src/intelligence/signals.py
**Acceptance**: Returns BUY_YES/BUY_NO/HOLD with confidence

### TASK-011: Telegram Alerts
**Input**: Alert data
**Output**: src/outputs/telegram.py
**Acceptance**: Sends formatted message to Telegram

### TASK-012: Main Orchestrator
**Input**: All components
**Output**: src/main.py
**Acceptance**: Runs full pipeline, handles errors gracefully

---

*Document Version: 1.0*
*Created: 2026-02-03*
*Author: Helmet 🪖*
