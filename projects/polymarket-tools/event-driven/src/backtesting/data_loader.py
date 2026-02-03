"""
Data loader for backtesting framework.
Loads historical events and market prices. Generates mock data for testing.
"""
import json
import random
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from pathlib import Path
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.models import Event
from src.fetchers.polymarket import MarketPrice


def load_historical_events(data_path: str = "data/historical/events.json") -> List[Event]:
    """Load historical events from JSON file."""
    try:
        with open(data_path, 'r') as f:
            events_data = json.load(f)
        
        events = []
        for event_data in events_data:
            events.append(Event.from_dict(event_data))
        
        return sorted(events, key=lambda e: e.timestamp)
    except FileNotFoundError:
        print(f"Historical events file not found: {data_path}")
        return []
    except json.JSONDecodeError as e:
        print(f"Error parsing historical events: {e}")
        return []


def load_market_prices(data_path: str = "data/historical/prices.json") -> Dict[str, List[MarketPrice]]:
    """Load historical market prices from JSON file."""
    try:
        with open(data_path, 'r') as f:
            prices_data = json.load(f)
        
        market_prices = {}
        for market_id, price_points in prices_data.items():
            prices = []
            for price_data in price_points:
                # Convert to MarketPrice object
                prices.append(MarketPrice(
                    market_id=market_id,
                    market_slug=price_data.get('market_slug', market_id),
                    question=price_data.get('market_title', ''),
                    yes_price=price_data['yes_price'],
                    no_price=price_data['no_price'],
                    volume=price_data.get('volume', 0),
                    liquidity=price_data.get('liquidity', 0),
                    last_updated=datetime.fromisoformat(price_data['timestamp']),
                    is_active=price_data.get('is_active', True),
                    raw_data={}
                ))
            market_prices[market_id] = sorted(prices, key=lambda p: p.timestamp)
        
        return market_prices
    except FileNotFoundError:
        print(f"Historical prices file not found: {data_path}")
        return {}
    except json.JSONDecodeError as e:
        print(f"Error parsing historical prices: {e}")
        return {}


def generate_mock_data(days: int = 30) -> Tuple[List[Event], Dict[str, List[MarketPrice]]]:
    """Generate realistic mock data for backtesting."""
    
    # Market templates with realistic categories
    market_templates = [
        {
            "id": "mkt_fed_rate_dec_2024",
            "title": "Will the Fed cut rates by 0.25% in December 2024?",
            "category": "fed",
            "keywords": ["fed", "federal reserve", "interest rates", "powell", "fomc"],
            "initial_price": 0.65,
            "volatility": 0.15
        },
        {
            "id": "mkt_bitcoin_100k_2024", 
            "title": "Will Bitcoin reach $100,000 by end of 2024?",
            "category": "crypto",
            "keywords": ["bitcoin", "btc", "crypto", "cryptocurrency"],
            "initial_price": 0.35,
            "volatility": 0.25
        },
        {
            "id": "mkt_trump_president_2024",
            "title": "Will Donald Trump be elected President in 2024?",
            "category": "politics", 
            "keywords": ["trump", "election", "president", "republican"],
            "initial_price": 0.52,
            "volatility": 0.20
        },
        {
            "id": "mkt_nvidia_split_2024",
            "title": "Will NVIDIA announce a stock split in 2024?",
            "category": "stocks",
            "keywords": ["nvidia", "nvda", "stock split", "shares"],
            "initial_price": 0.28,
            "volatility": 0.18
        },
        {
            "id": "mkt_recession_q1_2024",
            "title": "Will US enter recession by Q1 2024?",
            "category": "economy",
            "keywords": ["recession", "gdp", "economy", "unemployment"],
            "initial_price": 0.42,
            "volatility": 0.12
        }
    ]
    
    # Generate events
    events = []
    start_date = datetime.now() - timedelta(days=days)
    
    # Event templates by category
    event_templates = {
        "fed": [
            "Fed Chair Powell signals dovish stance in Jackson Hole speech",
            "FOMC minutes reveal split decision on interest rate policy", 
            "Federal Reserve officials debate inflation target adjustments",
            "Fed Governor Williams suggests gradual rate normalization",
            "Regional Fed presidents express concern over inflation persistence"
        ],
        "crypto": [
            "Bitcoin reaches new all-time high as institutions pile in",
            "SEC approves first Bitcoin ETF amid regulatory clarity",
            "Major crypto exchange faces regulatory scrutiny",
            "Ethereum upgrade promises reduced transaction fees",
            "Crypto adoption accelerates among Fortune 500 companies"
        ],
        "politics": [
            "Trump leads in latest Republican primary polls",
            "Biden campaign announces major fundraising milestone",
            "Supreme Court ruling impacts 2024 election procedures",
            "Key swing states show tight presidential race polling",
            "Congressional leaders negotiate debt ceiling agreement"
        ],
        "stocks": [
            "NVIDIA reports record quarterly earnings beat",
            "Tech giants announce massive AI infrastructure investments",
            "Market volatility spikes amid geopolitical tensions",
            "S&P 500 reaches new record high on strong earnings",
            "Banking sector faces stress test concerns"
        ],
        "economy": [
            "GDP growth exceeds economist expectations",
            "Unemployment rate drops to multi-decade low",
            "Consumer confidence index shows concerning decline",
            "Housing market shows signs of cooling",
            "Inflation data reveals persistent price pressures"
        ]
    }
    
    # Generate events over the period
    events_per_day = random.randint(2, 6)
    event_id_counter = 1
    
    for day in range(days):
        current_date = start_date + timedelta(days=day)
        
        for _ in range(random.randint(1, events_per_day)):
            # Choose random market and category
            market = random.choice(market_templates)
            category = market["category"]
            
            # Generate event content
            title = random.choice(event_templates[category])
            
            # Add some variation
            variations = [
                " - Market analysts react",
                " as trading volume surges",
                " amid increased institutional interest",
                " following regulatory developments",
                " in major policy shift"
            ]
            
            if random.random() < 0.3:  # 30% chance to add variation
                title += random.choice(variations)
            
            # Create event
            event_time = current_date + timedelta(
                hours=random.randint(9, 17),
                minutes=random.randint(0, 59)
            )
            
            event = Event(
                id=f"evt_{event_id_counter:04d}",
                timestamp=event_time,
                source=random.choice(["rss", "twitter"]),
                source_tier=random.choice(["tier1_breaking", "tier2_reliable", "tier3_general"]),
                category=category,
                title=title,
                content=title,  # Simple mock
                url=f"https://example.com/news/{event_id_counter}",
                author=random.choice(["Reuters", "Bloomberg", "WSJ", "CNN", "Financial Times"]),
                keywords_matched=market["keywords"][:random.randint(1, len(market["keywords"]))],
                urgency_score=round(random.uniform(3.0, 9.0), 1),
                is_duplicate=False,
                duplicate_of=None,
                raw_data={}
            )
            
            events.append(event)
            event_id_counter += 1
    
    # Generate market prices
    market_prices = {}
    
    for market in market_templates:
        prices = []
        current_price = market["initial_price"]
        
        # Generate price history
        for hour in range(days * 24):
            timestamp = start_date + timedelta(hours=hour)
            
            # Add random walk with mean reversion
            price_change = random.gauss(0, market["volatility"] / 100)
            # Mean reversion towards initial price
            mean_reversion = (market["initial_price"] - current_price) * 0.01
            current_price += price_change + mean_reversion
            
            # Keep in valid range
            current_price = max(0.01, min(0.99, current_price))
            
            price = MarketPrice(
                market_id=market["id"],
                market_slug=market["id"],
                question=market["title"],
                yes_price=current_price,
                no_price=1.0 - current_price,
                volume=random.randint(1000, 50000),
                liquidity=random.randint(5000, 100000),
                last_updated=timestamp,
                is_active=True,
                raw_data={}
            )
            
            prices.append(price)
        
        market_prices[market["id"]] = prices
    
    return events, market_prices


def save_mock_data(events: List[Event], prices: Dict[str, List[MarketPrice]], 
                  data_dir: str = "data/historical"):
    """Save generated mock data to files."""
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    
    # Save events
    events_data = [event.to_dict() for event in events]
    with open(f"{data_dir}/events.json", 'w') as f:
        json.dump(events_data, f, indent=2, default=str)
    
    # Save prices
    prices_data = {}
    for market_id, price_list in prices.items():
        prices_data[market_id] = [
            {
                'market_slug': p.market_slug,
                'market_title': p.question,
                'yes_price': p.yes_price,
                'no_price': p.no_price,
                'volume': p.volume,
                'liquidity': p.liquidity,
                'timestamp': p.last_updated.isoformat(),
                'is_active': p.is_active
            }
            for p in price_list
        ]
    
    with open(f"{data_dir}/prices.json", 'w') as f:
        json.dump(prices_data, f, indent=2)
    
    print(f"✅ Saved {len(events)} events and {len(prices)} markets to {data_dir}")


if __name__ == "__main__":
    # Generate and save mock data for testing
    print("🎲 Generating mock data...")
    events, prices = generate_mock_data(days=30)
    save_mock_data(events, prices)
    
    print(f"Generated {len(events)} events across {len(prices)} markets")