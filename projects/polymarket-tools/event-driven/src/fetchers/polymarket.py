"""
Polymarket price fetcher.
Fetches current market prices from Polymarket Gamma API with caching and rate limiting.
"""
import asyncio
import aiohttp
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from pathlib import Path
import hashlib
import time

# Configuration
GAMMA_API_BASE = "https://gamma-api.polymarket.com"
CLOB_API_BASE = "https://clob.polymarket.com" 
CACHE_DURATION_MINUTES = 1  # Don't fetch if data is less than 1 minute old
MAX_REQUESTS_PER_MINUTE = 60  # Rate limit
MAX_CONCURRENT_REQUESTS = 10  # Concurrent request limit
REQUEST_TIMEOUT_SECONDS = 10
CACHE_FILE = Path("data/polymarket_cache.json")

# Rate limiting state
_rate_limiter = {
    "requests": [],
    "last_cleanup": time.time()
}

@dataclass
class MarketPrice:
    """Represents current price data for a Polymarket market."""
    market_id: str
    market_slug: str
    question: str
    yes_price: float  # 0.0-1.0 
    no_price: float   # 0.0-1.0
    volume: float
    liquidity: float
    last_updated: datetime
    is_active: bool
    raw_data: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'market_id': self.market_id,
            'market_slug': self.market_slug,
            'question': self.question,
            'yes_price': self.yes_price,
            'no_price': self.no_price,
            'volume': self.volume,
            'liquidity': self.liquidity,
            'last_updated': self.last_updated.isoformat() if isinstance(self.last_updated, datetime) else self.last_updated,
            'is_active': self.is_active,
            'raw_data': self.raw_data
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'MarketPrice':
        """Create MarketPrice from dictionary."""
        data = data.copy()
        
        # Convert timestamp
        if isinstance(data.get('last_updated'), str):
            try:
                data['last_updated'] = datetime.fromisoformat(data['last_updated'].replace('Z', '+00:00'))
            except ValueError:
                data['last_updated'] = datetime.now()
        
        return cls(**data)


class PriceCache:
    """Manages caching of market prices to avoid excessive API calls."""
    
    def __init__(self, cache_file: Path = CACHE_FILE):
        self.cache_file = cache_file
        self.cache = self._load_cache()
    
    def _load_cache(self) -> Dict:
        """Load cache from disk."""
        if not self.cache_file.exists():
            return {}
        
        try:
            with open(self.cache_file, 'r') as f:
                data = json.load(f)
                
            # Convert timestamps back to datetime
            for slug, market_data in data.items():
                if isinstance(market_data.get('last_updated'), str):
                    try:
                        market_data['last_updated'] = datetime.fromisoformat(
                            market_data['last_updated'].replace('Z', '+00:00')
                        )
                    except ValueError:
                        market_data['last_updated'] = datetime.now()
            
            return data
        except Exception as e:
            print(f"Error loading price cache: {e}")
            return {}
    
    def _save_cache(self):
        """Save cache to disk."""
        try:
            # Ensure data directory exists
            self.cache_file.parent.mkdir(exist_ok=True)
            
            # Convert to JSON-serializable format
            serializable_cache = {}
            for slug, market_data in self.cache.items():
                serializable_data = dict(market_data)
                if isinstance(serializable_data.get('last_updated'), datetime):
                    serializable_data['last_updated'] = serializable_data['last_updated'].isoformat()
                serializable_cache[slug] = serializable_data
            
            with open(self.cache_file, 'w') as f:
                json.dump(serializable_cache, f, indent=2)
        except Exception as e:
            print(f"Error saving price cache: {e}")
    
    def get(self, market_slug: str) -> Optional[MarketPrice]:
        """Get cached market price if still fresh."""
        if market_slug not in self.cache:
            return None
        
        cached_data = self.cache[market_slug]
        last_updated = cached_data.get('last_updated')
        
        if not isinstance(last_updated, datetime):
            return None
        
        # Check if cache is still fresh
        cache_age = datetime.now() - last_updated
        if cache_age <= timedelta(minutes=CACHE_DURATION_MINUTES):
            return MarketPrice.from_dict(cached_data)
        
        return None
    
    def set(self, market_price: MarketPrice):
        """Cache market price data."""
        self.cache[market_price.market_slug] = market_price.to_dict()
        self._save_cache()
    
    def get_multiple(self, market_slugs: List[str]) -> Dict[str, MarketPrice]:
        """Get multiple cached prices."""
        results = {}
        for slug in market_slugs:
            cached = self.get(slug)
            if cached:
                results[slug] = cached
        return results
    
    def set_multiple(self, market_prices: List[MarketPrice]):
        """Cache multiple market prices."""
        for price in market_prices:
            self.cache[price.market_slug] = price.to_dict()
        self._save_cache()


def _check_rate_limit() -> bool:
    """Check if we can make a request without exceeding rate limits."""
    now = time.time()
    
    # Clean up old requests (older than 1 minute)
    if now - _rate_limiter["last_cleanup"] > 60:
        cutoff = now - 60
        _rate_limiter["requests"] = [req_time for req_time in _rate_limiter["requests"] if req_time > cutoff]
        _rate_limiter["last_cleanup"] = now
    
    # Check if we're under the rate limit
    return len(_rate_limiter["requests"]) < MAX_REQUESTS_PER_MINUTE


def _record_request():
    """Record that we made a request for rate limiting."""
    _rate_limiter["requests"].append(time.time())


async def _fetch_market_data(session: aiohttp.ClientSession, market_slug: str) -> Optional[Dict]:
    """
    Fetch market data for a single market from Polymarket Gamma API.
    
    Args:
        session: aiohttp session
        market_slug: Market slug to fetch
        
    Returns:
        Market data dict or None if error
    """
    if not _check_rate_limit():
        print(f"Rate limit reached, skipping {market_slug}")
        return None
    
    try:
        url = f"{GAMMA_API_BASE}/markets?slug={market_slug}"
        
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)) as response:
            _record_request()
            
            if response.status == 200:
                data = await response.json()
                return data
            elif response.status == 404:
                print(f"Market not found: {market_slug}")
                return None
            else:
                print(f"API error for {market_slug}: HTTP {response.status}")
                return None
                
    except asyncio.TimeoutError:
        print(f"Timeout fetching {market_slug}")
        return None
    except Exception as e:
        print(f"Error fetching {market_slug}: {e}")
        return None


def _parse_market_data(market_slug: str, api_data: Dict) -> Optional[MarketPrice]:
    """
    Parse API response into MarketPrice object.
    
    Args:
        market_slug: Market slug
        api_data: Raw API response
        
    Returns:
        MarketPrice object or None if parsing failed
    """
    try:
        # API can return array or single object
        if isinstance(api_data, list):
            if not api_data:
                return None
            market_data = api_data[0]  # Take first result
        else:
            market_data = api_data
        
        # Extract basic market info
        market_id = market_data.get('id', market_slug)
        question = market_data.get('question', 'Unknown')
        
        # Check if market is active
        is_active = market_data.get('active', True)
        closed = market_data.get('closed', False)
        if closed:
            is_active = False
        
        # Extract pricing info
        tokens = market_data.get('tokens', [])
        yes_token = None
        no_token = None
        
        for token in tokens:
            if token.get('outcome') == 'Yes':
                yes_token = token
            elif token.get('outcome') == 'No':
                no_token = token
        
        # Get prices (fallback to 0.5 if not available)
        yes_price = 0.5
        no_price = 0.5
        
        if yes_token and 'price' in yes_token:
            yes_price = float(yes_token['price'])
        if no_token and 'price' in no_token:
            no_price = float(no_token['price'])
        
        # Ensure prices are complementary and in valid range
        if yes_price + no_price > 0:
            total = yes_price + no_price
            yes_price = yes_price / total
            no_price = no_price / total
        
        yes_price = max(0.0, min(1.0, yes_price))
        no_price = max(0.0, min(1.0, no_price))
        
        # Extract volume and liquidity
        volume = float(market_data.get('volume', 0))
        liquidity = float(market_data.get('liquidity', 0))
        
        # Alternative fields for liquidity
        if liquidity == 0:
            liquidity = float(market_data.get('totalLiquidity', 0))
        
        return MarketPrice(
            market_id=market_id,
            market_slug=market_slug,
            question=question,
            yes_price=yes_price,
            no_price=no_price,
            volume=volume,
            liquidity=liquidity,
            last_updated=datetime.now(),
            is_active=is_active,
            raw_data=market_data
        )
        
    except Exception as e:
        print(f"Error parsing market data for {market_slug}: {e}")
        return None


async def fetch_market_prices(market_slugs: List[str]) -> List[MarketPrice]:
    """
    Fetch current prices for given markets from Polymarket API.
    
    Args:
        market_slugs: List of market slugs to fetch
        
    Returns:
        List of MarketPrice objects for successful fetches
    """
    if not market_slugs:
        return []
    
    # Initialize cache
    cache = PriceCache()
    
    # Check cache first
    cached_prices = cache.get_multiple(market_slugs)
    remaining_slugs = [slug for slug in market_slugs if slug not in cached_prices]
    
    if cached_prices:
        print(f"Using cached data for {len(cached_prices)} markets")
    
    if not remaining_slugs:
        return list(cached_prices.values())
    
    # Fetch remaining markets from API
    print(f"Fetching {len(remaining_slugs)} markets from Polymarket API")
    
    # Create semaphore to limit concurrent requests
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    
    async def fetch_with_semaphore(session: aiohttp.ClientSession, slug: str):
        async with semaphore:
            return await _fetch_market_data(session, slug)
    
    # Fetch all markets concurrently
    fetched_prices = []
    
    try:
        async with aiohttp.ClientSession() as session:
            # Create tasks for concurrent fetching
            tasks = [fetch_with_semaphore(session, slug) for slug in remaining_slugs]
            
            # Execute with timeout
            api_results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=REQUEST_TIMEOUT_SECONDS * 2
            )
            
            # Process results
            for i, result in enumerate(api_results):
                if isinstance(result, Exception):
                    print(f"Exception for {remaining_slugs[i]}: {result}")
                    continue
                
                if result is None:
                    continue
                
                market_price = _parse_market_data(remaining_slugs[i], result)
                if market_price:
                    fetched_prices.append(market_price)
    
    except asyncio.TimeoutError:
        print("Timeout fetching markets from API")
    except Exception as e:
        print(f"Error during batch fetch: {e}")
    
    # Cache the fetched prices
    if fetched_prices:
        cache.set_multiple(fetched_prices)
        print(f"Cached {len(fetched_prices)} new market prices")
    
    # Combine cached and fetched results
    all_prices = list(cached_prices.values()) + fetched_prices
    
    return all_prices


async def fetch_market_price(market_slug: str) -> Optional[MarketPrice]:
    """
    Fetch current price for a single market.
    
    Args:
        market_slug: Market slug to fetch
        
    Returns:
        MarketPrice object or None if not found
    """
    prices = await fetch_market_prices([market_slug])
    return prices[0] if prices else None


def get_cache_status() -> Dict:
    """Get status of the price cache."""
    cache = PriceCache()
    
    status = {
        "cache_file": str(cache.cache_file),
        "cached_markets": len(cache.cache),
        "fresh_markets": 0,
        "stale_markets": 0,
        "last_updated": None
    }
    
    now = datetime.now()
    latest_update = None
    
    for slug, market_data in cache.cache.items():
        last_updated = market_data.get('last_updated')
        if isinstance(last_updated, datetime):
            cache_age = now - last_updated
            if cache_age <= timedelta(minutes=CACHE_DURATION_MINUTES):
                status["fresh_markets"] += 1
            else:
                status["stale_markets"] += 1
            
            if latest_update is None or last_updated > latest_update:
                latest_update = last_updated
    
    if latest_update:
        status["last_updated"] = latest_update.isoformat()
    
    return status


# Example usage and testing
if __name__ == "__main__":
    async def test_fetcher():
        """Test the price fetcher with some sample markets."""
        test_slugs = [
            "fed-rate-cut-march-2025",
            "trump-deportations-2025", 
            "russia-ukraine-ceasefire-2025"
        ]
        
        print(f"Testing price fetcher with {len(test_slugs)} markets...")
        
        prices = await fetch_market_prices(test_slugs)
        
        print(f"\nFetched {len(prices)} market prices:")
        for price in prices:
            print(f"- {price.market_slug}: Yes=${price.yes_price:.3f}, No=${price.no_price:.3f}")
            print(f"  Question: {price.question}")
            print(f"  Volume: ${price.volume:,.0f}, Liquidity: ${price.liquidity:,.0f}")
            print(f"  Active: {price.is_active}, Updated: {price.last_updated}")
            print()
        
        # Test cache status
        print("Cache status:")
        status = get_cache_status()
        for key, value in status.items():
            print(f"  {key}: {value}")
    
    # Run the test
    asyncio.run(test_fetcher())