"""
Dynamic Market Mapper - Searches Polymarket API for relevant markets in real-time.
No hardcoded slugs - always uses fresh data from the API.
"""
import asyncio
import aiohttp
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from datetime import datetime, timedelta
import json
from pathlib import Path
import re

GAMMA_API = "https://gamma-api.polymarket.com"
CACHE_FILE = Path("data/markets_cache.json")
CACHE_TTL_HOURS = 1  # Refresh market list every hour

@dataclass
class MarketMatch:
    market_slug: str
    market_id: str
    question: str
    relevance_score: float
    direction_hint: str = "neutral"
    reasoning: str = ""
    matched_keywords: List[str] = field(default_factory=list)
    yes_price: float = 0.5
    volume: float = 0
    
class DynamicMarketMapper:
    """Maps events to markets by searching Polymarket API dynamically."""
    
    def __init__(self):
        self.markets_cache = []
        self.cache_time = None
        self._load_cache()
    
    def _load_cache(self):
        """Load cached markets from file."""
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, 'r') as f:
                    data = json.load(f)
                    self.markets_cache = data.get('markets', [])
                    cache_ts = data.get('timestamp')
                    if cache_ts:
                        self.cache_time = datetime.fromisoformat(cache_ts)
            except Exception as e:
                print(f"Error loading cache: {e}")
    
    def _save_cache(self):
        """Save markets cache to file."""
        try:
            CACHE_FILE.parent.mkdir(exist_ok=True)
            with open(CACHE_FILE, 'w') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'markets': self.markets_cache
                }, f, indent=2)
        except Exception as e:
            print(f"Error saving cache: {e}")
    
    def _cache_valid(self) -> bool:
        """Check if cache is still fresh."""
        if not self.cache_time or not self.markets_cache:
            return False
        age = datetime.now() - self.cache_time
        return age < timedelta(hours=CACHE_TTL_HOURS)
    
    async def refresh_markets(self):
        """Fetch all active markets from Polymarket."""
        if self._cache_valid():
            print(f"Using cached markets ({len(self.markets_cache)} markets)")
            return
        
        print("Fetching fresh markets from Polymarket...")
        markets = []
        
        try:
            async with aiohttp.ClientSession() as session:
                # Fetch events (which contain markets)
                url = f"{GAMMA_API}/events?closed=false&_limit=500"
                async with session.get(url, timeout=30) as resp:
                    if resp.status == 200:
                        events = await resp.json()
                        for event in events:
                            # Extract market info
                            event_markets = event.get('markets', [])
                            for m in event_markets:
                                markets.append({
                                    'slug': m.get('slug', event.get('slug')),
                                    'question': m.get('question', event.get('title')),
                                    'title': event.get('title', ''),
                                    'volume': float(m.get('volume', 0)),
                                    'active': m.get('active', True),
                                })
                            
                            # Also add event-level market
                            if event.get('slug'):
                                markets.append({
                                    'slug': event.get('slug'),
                                    'question': event.get('title', ''),
                                    'title': event.get('title', ''),
                                    'volume': float(event.get('volume', 0)),
                                    'active': not event.get('closed', False),
                                })
            
            # Dedupe by slug
            seen = set()
            unique_markets = []
            for m in markets:
                if m['slug'] not in seen and m.get('active', True):
                    seen.add(m['slug'])
                    unique_markets.append(m)
            
            self.markets_cache = unique_markets
            self.cache_time = datetime.now()
            self._save_cache()
            print(f"Cached {len(self.markets_cache)} active markets")
            
        except Exception as e:
            print(f"Error fetching markets: {e}")
    
    def _extract_keywords(self, text: str) -> Set[str]:
        """Extract meaningful keywords from text."""
        # Lowercase and clean
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # Split and filter
        words = text.split()
        
        # Skip common words
        stopwords = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                    'will', 'would', 'could', 'should', 'may', 'might', 'to', 
                    'of', 'in', 'on', 'at', 'for', 'by', 'with', 'from', 'as',
                    'or', 'and', 'but', 'if', 'so', 'than', 'that', 'this',
                    'it', 'its', 'they', 'their', 'he', 'she', 'his', 'her',
                    'says', 'said', 'according', 'reports', 'new', 'just'}
        
        keywords = {w for w in words if len(w) > 2 and w not in stopwords}
        return keywords
    
    def _calculate_relevance(self, event_keywords: Set[str], market: Dict) -> float:
        """Calculate how relevant a market is to given keywords."""
        market_text = f"{market.get('question', '')} {market.get('title', '')}".lower()
        market_keywords = self._extract_keywords(market_text)
        
        if not event_keywords or not market_keywords:
            return 0.0
        
        # Count matching keywords
        matches = event_keywords & market_keywords
        
        if not matches:
            return 0.0
        
        # Score based on % of event keywords matched and importance
        match_ratio = len(matches) / len(event_keywords)
        
        # Boost for high-volume markets
        volume_boost = min(market.get('volume', 0) / 1000000, 0.2)  # Max 0.2 boost
        
        # Boost for exact important keyword matches
        important_keywords = {'trump', 'biden', 'ukraine', 'russia', 'bitcoin', 'btc',
                            'fed', 'china', 'iran', 'nato', 'election', 'war'}
        important_matches = matches & important_keywords
        importance_boost = len(important_matches) * 0.15
        
        score = min(match_ratio + volume_boost + importance_boost, 1.0)
        return score
    
    async def get_affected_markets(self, event) -> List[MarketMatch]:
        """Find markets affected by an event."""
        await self.refresh_markets()
        
        # Extract keywords from event
        event_text = f"{event.title} {getattr(event, 'content', '')}"
        event_keywords = self._extract_keywords(event_text)
        
        if not event_keywords:
            return []
        
        matches = []
        for market in self.markets_cache:
            score = self._calculate_relevance(event_keywords, market)
            
            if score >= 0.2:  # Minimum relevance threshold
                matched_kw = list(event_keywords & self._extract_keywords(
                    f"{market.get('question', '')} {market.get('title', '')}"
                ))
                
                matches.append(MarketMatch(
                    market_slug=market['slug'],
                    market_id=market.get('id', market['slug']),
                    question=market.get('question', market.get('title', '')),
                    relevance_score=score,
                    matched_keywords=matched_kw,
                    volume=market.get('volume', 0),
                    reasoning=f"Matched keywords: {', '.join(matched_kw[:5])}"
                ))
        
        # Sort by relevance
        matches.sort(key=lambda x: x.relevance_score, reverse=True)
        
        # Return top matches
        return matches[:10]


# Singleton instance
_mapper = None

async def get_affected_markets(event) -> List[MarketMatch]:
    """Convenience function to get affected markets."""
    global _mapper
    if _mapper is None:
        _mapper = DynamicMarketMapper()
    return await _mapper.get_affected_markets(event)


if __name__ == "__main__":
    # Test
    async def test():
        mapper = DynamicMarketMapper()
        await mapper.refresh_markets()
        print(f"Loaded {len(mapper.markets_cache)} markets")
        
        # Test with fake event
        class FakeEvent:
            title = "Trump signs bill to end government shutdown"
            content = "President Donald Trump has signed the funding bill"
        
        matches = await mapper.get_affected_markets(FakeEvent())
        print(f"\nMatches for '{FakeEvent.title}':")
        for m in matches[:5]:
            print(f"  {m.market_slug} (score: {m.relevance_score:.2f})")
            print(f"    Keywords: {m.matched_keywords}")
    
    asyncio.run(test())
