#!/usr/bin/env python3
"""
Monitor Daemon - Async daemon that monitors multiple URLs for changes.

Watches sources defined in sources.json, detects changes, and emits events
compatible with the trading bot event system.

Events are now granular: 1 event per item (not per feed).

Usage:
    python monitor_daemon.py --once    # Single check cycle (for testing)
    python monitor_daemon.py           # Run continuously
    python monitor_daemon.py -v        # Verbose logging
"""

import argparse
import asyncio
import hashlib
import json
import logging
import signal
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import aiohttp

# Add parent dir to import browser_pool and parsers
sys.path.insert(0, str(Path(__file__).parent))
from browser_pool import BrowserPool
from parsers import get_parser, ParsedItem

# === Paths ===
SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = SCRIPT_DIR.parent
SOURCES_FILE = ROOT_DIR / "sources.json"
STATE_FILE = ROOT_DIR / "data" / "monitor_state.json"
EVENTS_FILE = ROOT_DIR / "data" / "scraped_events.json"

# === Logging ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)


def load_json(path: Path, default: Any = None) -> Any:
    """Load JSON file, return default if not exists or invalid."""
    try:
        if path.exists():
            return json.loads(path.read_text())
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Error loading {path}: {e}")
    return default if default is not None else {}


def save_json(path: Path, data: Any) -> None:
    """Save data to JSON file, creating parent dirs if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def compute_hash(content: str) -> str:
    """Compute MD5 hash of content."""
    return hashlib.md5(content.encode('utf-8')).hexdigest()


def get_domain(url: str) -> str:
    """Extract domain from URL for rate limiting."""
    return urlparse(url).netloc


class MonitorDaemon:
    """
    Async daemon that monitors multiple sources for changes.
    
    Features:
    - Parallel fetching with semaphore-based concurrency limit
    - Per-domain rate limiting
    - Browser pool for JS-rendered pages
    - State persistence for change detection
    - Per-item event generation (granular events)
    - GUID-based deduplication
    """
    
    def __init__(self, sources_file: Path = SOURCES_FILE, verbose: bool = False):
        self.sources_file = sources_file
        self.verbose = verbose
        self.sources: list[dict] = []
        self.config: dict = {}
        self.state: dict = {}
        self.events: list[dict] = []
        self.browser_pool: Optional[BrowserPool] = None
        self._shutdown = False
        self._domain_last_request: dict[str, float] = {}
        
        if verbose:
            logger.setLevel(logging.DEBUG)
    
    def load_sources(self) -> None:
        """Load sources and config from JSON file."""
        data = load_json(self.sources_file, {'sources': [], 'config': {}})
        self.sources = data.get('sources', [])
        self.config = data.get('config', {})
        logger.info(f"Loaded {len(self.sources)} sources from {self.sources_file.name}")
    
    def load_state(self) -> None:
        """Load monitor state from file."""
        self.state = load_json(STATE_FILE, {})
        logger.debug(f"Loaded state for {len(self.state)} sources")
    
    def save_state(self) -> None:
        """Save monitor state to file."""
        save_json(STATE_FILE, self.state)
        logger.debug(f"Saved state for {len(self.state)} sources")
    
    def load_events(self) -> None:
        """Load existing events from file."""
        self.events = load_json(EVENTS_FILE, [])
        logger.debug(f"Loaded {len(self.events)} existing events")
    
    def save_events(self) -> None:
        """Save events to file."""
        save_json(EVENTS_FILE, self.events)
        logger.debug(f"Saved {len(self.events)} events")
    
    def get_seen_guids(self, source_id: str) -> set[str]:
        """Get set of previously seen GUIDs for a source."""
        source_state = self.state.get(source_id, {})
        return set(source_state.get('seen_guids', []))
    
    def update_seen_guids(self, source_id: str, guids: set[str], max_guids: int = 500) -> None:
        """
        Update seen GUIDs for a source.
        
        Keeps only the most recent max_guids to prevent unbounded growth.
        """
        if source_id not in self.state:
            self.state[source_id] = {}
        
        # Convert to list and truncate if needed
        guid_list = list(guids)
        if len(guid_list) > max_guids:
            guid_list = guid_list[-max_guids:]  # Keep most recent
        
        self.state[source_id]['seen_guids'] = guid_list
    
    def create_event(self, source: dict, item: ParsedItem, change_type: str = 'new_item') -> dict:
        """Create a single event from a parsed item."""
        event = {
            'id': str(uuid.uuid4()),
            'source': 'web_scraper',
            'source_id': source['id'],
            'source_url': source['url'],
            'title': item.title,
            'link': item.link,
            'content': item.content[:5000] if item.content else "",
            'detected_at': datetime.now(timezone.utc).isoformat(),
            'published_at': item.published_at,
            'category': source.get('category', 'unknown'),
            'item_category': item.category,
            'priority': source.get('priority', 5),
            'change_type': change_type,
            'guid': item.guid,
        }
        return event
    
    async def rate_limit_domain(self, domain: str) -> None:
        """Wait if needed to respect domain rate limit."""
        rate_limit_ms = self.config.get('rate_limit_per_domain_ms', 2000)
        rate_limit_s = rate_limit_ms / 1000
        
        last_request = self._domain_last_request.get(domain, 0)
        elapsed = asyncio.get_event_loop().time() - last_request
        
        if elapsed < rate_limit_s:
            wait_time = rate_limit_s - elapsed
            logger.debug(f"Rate limiting {domain}: waiting {wait_time:.1f}s")
            await asyncio.sleep(wait_time)
        
        self._domain_last_request[domain] = asyncio.get_event_loop().time()
    
    async def fetch_http(self, url: str, user_agent: Optional[str] = None) -> str:
        """Fetch URL using aiohttp (no JS rendering)."""
        timeout = aiohttp.ClientTimeout(
            total=self.config.get('request_timeout_ms', 15000) / 1000
        )
        headers = {
            'User-Agent': user_agent or 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) WebScraper/1.0'
        }
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                return await response.text()
    
    async def fetch_browser(self, url: str, selector: Optional[str] = None) -> str:
        """Fetch URL using browser pool (with JS rendering)."""
        if not self.browser_pool:
            raise RuntimeError("Browser pool not initialized")
        
        timeout = self.config.get('request_timeout_ms', 15000) / 1000
        return await self.browser_pool.get_content(
            url, 
            selector=selector,
            timeout=timeout,
            wait=2.0
        )
    
    async def check_source(self, source: dict) -> list[dict]:
        """
        Check a single source for new items.
        
        Returns list of events for new items (one event per new item).
        """
        source_id = source['id']
        source_type = source.get('type', 'html')
        url = source['url']
        domain = get_domain(url)
        
        logger.debug(f"Checking {source_id}...")
        
        try:
            # Rate limit
            await self.rate_limit_domain(domain)
            
            # Fetch content
            if source.get('needs_js', False):
                selector = source.get('selector') if source_type == 'html' else None
                content = await self.fetch_browser(url, selector)
            else:
                content = await self.fetch_http(url, source.get('user_agent'))
            
            # Update basic state
            now = datetime.now(timezone.utc).isoformat()
            content_hash = compute_hash(content)
            
            prev_state = self.state.get(source_id, {})
            prev_hash = prev_state.get('last_hash')
            
            # Quick check: if hash unchanged, no new items
            if prev_hash == content_hash:
                logger.debug(f"✓ {source_id}: No change (hash match)")
                self.state[source_id] = {
                    **prev_state,
                    'last_check': now,
                    'consecutive_errors': 0,
                }
                return []
            
            # Parse content into items
            parser = get_parser(source_type)
            items = parser.parse(content, source)
            
            if not items:
                logger.warning(f"⚠️ {source_id}: No items parsed from content")
                self.state[source_id] = {
                    **prev_state,
                    'last_check': now,
                    'last_hash': content_hash,
                    'consecutive_errors': 0,
                }
                return []
            
            # Get previously seen GUIDs
            seen_guids = self.get_seen_guids(source_id)
            is_first_run = len(seen_guids) == 0 and prev_hash is None
            
            # Find new items
            new_items = []
            current_guids = set()
            
            for item in items:
                current_guids.add(item.guid)
                if item.guid not in seen_guids:
                    new_items.append(item)
            
            # Update state
            self.state[source_id] = {
                'last_hash': content_hash,
                'last_check': now,
                'consecutive_errors': 0,
                'items_count': len(items),
                'seen_guids': list(seen_guids.union(current_guids)),
            }
            
            # Truncate seen_guids to prevent unbounded growth
            if len(self.state[source_id]['seen_guids']) > 500:
                self.state[source_id]['seen_guids'] = self.state[source_id]['seen_guids'][-500:]
            
            # On first run, don't generate events (just record current state)
            if is_first_run:
                logger.info(f"🆕 {source_id}: First run - recorded {len(items)} items (no events)")
                return []
            
            # Generate events for new items
            events = []
            for item in new_items:
                event = self.create_event(source, item, 'new_item')
                events.append(event)
                self.events.append(event)
                logger.info(f"📢 [new_item] {source_id}: {item.title[:60]}")
            
            if new_items:
                logger.info(f"✅ {source_id}: {len(new_items)} new items of {len(items)} total")
            else:
                logger.debug(f"✓ {source_id}: {len(items)} items, none new")
            
            return events
            
        except Exception as e:
            # Track consecutive errors
            prev_state = self.state.get(source_id, {})
            errors = prev_state.get('consecutive_errors', 0) + 1
            
            self.state[source_id] = {
                **prev_state,
                'last_check': datetime.now(timezone.utc).isoformat(),
                'consecutive_errors': errors,
                'last_error': str(e)
            }
            
            logger.warning(f"⚠️ {source_id}: Error ({errors}x): {e}")
            return []
    
    async def run_cycle(self) -> list[dict]:
        """
        Run one check cycle for all sources.
        
        Returns list of detected events.
        """
        if not self.sources:
            self.load_sources()
        
        self.load_state()
        self.load_events()
        
        # Check if we need browser pool
        needs_browser = any(s.get('needs_js', False) for s in self.sources)
        
        all_events = []
        max_concurrent = self.config.get('max_concurrent_requests', 3)
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def check_with_semaphore(source: dict):
            async with semaphore:
                return await self.check_source(source)
        
        # Initialize browser pool if needed
        if needs_browser:
            async with BrowserPool(max_pages=max_concurrent) as pool:
                self.browser_pool = pool
                tasks = [check_with_semaphore(s) for s in self.sources]
                results = await asyncio.gather(*tasks, return_exceptions=True)
        else:
            tasks = [check_with_semaphore(s) for s in self.sources]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect events
        for result in results:
            if isinstance(result, list):
                all_events.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Task exception: {result}")
        
        # Save state and events
        self.save_state()
        self.save_events()
        
        return all_events
    
    async def run_forever(self) -> None:
        """Run the daemon continuously until shutdown signal."""
        logger.info("🚀 Starting monitor daemon...")
        
        self.load_sources()
        
        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._handle_shutdown)
        
        # Find minimum interval
        min_interval = min(
            (s.get('interval_seconds', 120) for s in self.sources),
            default=60
        )
        
        logger.info(f"📊 Monitoring {len(self.sources)} sources (cycle every {min_interval}s)")
        
        while not self._shutdown:
            try:
                events = await self.run_cycle()
                if events:
                    logger.info(f"🎯 Cycle complete: {len(events)} new item events")
                else:
                    logger.info("✓ Cycle complete: no new items")
                
                # Wait for next cycle
                if not self._shutdown:
                    logger.debug(f"Sleeping {min_interval}s...")
                    await asyncio.sleep(min_interval)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cycle error: {e}")
                await asyncio.sleep(10)  # Brief pause on error
        
        logger.info("👋 Daemon stopped")
    
    def _handle_shutdown(self) -> None:
        """Handle shutdown signal."""
        logger.info("🛑 Shutdown signal received...")
        self._shutdown = True


async def main():
    parser = argparse.ArgumentParser(description='Monitor daemon for web sources')
    parser.add_argument('--once', action='store_true', help='Run single cycle and exit')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose logging')
    parser.add_argument('--sources', type=Path, default=SOURCES_FILE, help='Path to sources.json')
    
    args = parser.parse_args()
    
    daemon = MonitorDaemon(sources_file=args.sources, verbose=args.verbose)
    
    if args.once:
        logger.info("🔄 Running single check cycle...")
        events = await daemon.run_cycle()
        print(f"\n{'='*60}")
        print(f"📊 Results: {len(events)} new item events")
        if events:
            for e in events:
                print(f"  • [{e['change_type']}] {e['source_id']}: {e['title'][:60]}")
        print(f"{'='*60}")
    else:
        await daemon.run_forever()


if __name__ == '__main__':
    asyncio.run(main())
