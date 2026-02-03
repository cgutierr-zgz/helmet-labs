#!/usr/bin/env python3
"""
Event Scanner - Complete Pipeline Orchestrator
Integrates all components for end-to-end event processing and signal generation.

Pipeline:
📥 Fetch Events (RSS + Twitter) → 🏷️ Classify → 📊 Score → 🔄 Deduplicate 
→ 🎯 Map to Markets → 💰 Fetch Prices → 🔮 Generate Signals → 📱 Format Alerts → 📤 Output
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pipeline.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Import all components
from src.fetchers.rss import scan_rss_feeds
from src.fetchers.twitter import scan_twitter_accounts
from src.fetchers.web_scraper import scan_web_scraper
from src.fetchers.polymarket import fetch_market_prices
from src.processors.classifier import classify_event, update_event_with_classification
from src.processors.scorer import calculate_urgency_score
from src.processors.dedup import is_duplicate, generate_alert_id
from src.intelligence.dynamic_mapper import DynamicMarketMapper as MarketMapper
from src.intelligence.signals import process_event_to_signals, filter_signals
from src.outputs.telegram import TelegramAlertManager, format_alert
from src.models import Event, ScanState
from config.settings import (
    STATE_FILE, ALERTS_FILE, MIN_URGENCY_THRESHOLD,
    STATE_RETENTION_HOURS, MAX_SEEN_IDS, MAX_RECENT_ALERTS
)


class PipelineStats:
    """Track pipeline execution statistics."""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.start_time = datetime.now()
        self.rss_events = 0
        self.twitter_events = 0
        self.web_scraper_events = 0
        self.classified_events = 0
        self.scored_events = 0
        self.deduplicated_events = 0
        self.mapped_markets = 0
        self.price_fetches = 0
        self.signals_generated = 0
        self.alerts_formatted = 0
        self.errors = []
    
    def add_error(self, step: str, error: str):
        self.errors.append(f"{step}: {error}")
        logger.error(f"Pipeline error in {step}: {error}")
    
    def duration_seconds(self) -> float:
        return (datetime.now() - self.start_time).total_seconds()
    
    def summary(self) -> Dict[str, Any]:
        return {
            'duration_seconds': self.duration_seconds(),
            'events_fetched': {
                'rss': self.rss_events,
                'twitter': self.twitter_events,
                'web_scraper': self.web_scraper_events,
                'total': self.rss_events + self.twitter_events + self.web_scraper_events
            },
            'events_processed': {
                'classified': self.classified_events,
                'scored': self.scored_events,
                'deduplicated': self.deduplicated_events
            },
            'markets': {
                'mapped': self.mapped_markets,
                'prices_fetched': self.price_fetches
            },
            'output': {
                'signals_generated': self.signals_generated,
                'alerts_formatted': self.alerts_formatted
            },
            'errors': self.errors
        }


class EventPipeline:
    """Main event processing pipeline orchestrator."""
    
    def __init__(self, telegram_rate_limit: int = 10):
        self.stats = PipelineStats()
        self.market_mapper = MarketMapper()
        self.telegram_manager = TelegramAlertManager(
            max_alerts_per_hour=telegram_rate_limit,
            state_file="data/telegram_state.json"
        )
        self.state = self.load_state()
    
    def load_state(self) -> ScanState:
        """Load scan state from file."""
        try:
            if STATE_FILE.exists():
                data = json.loads(STATE_FILE.read_text())
                return ScanState.from_dict(data)
        except Exception as e:
            self.stats.add_error("load_state", str(e))
        
        return ScanState(last_scan=None, seen_ids=[], recent_alerts=[])
    
    def save_state(self):
        """Save scan state to file."""
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATE_FILE.write_text(json.dumps(self.state.to_dict(), indent=2))
        except Exception as e:
            self.stats.add_error("save_state", str(e))
    
    def clean_state(self):
        """Clean up state by removing old data."""
        try:
            cutoff_time = datetime.now() - timedelta(hours=STATE_RETENTION_HOURS)
            recent_alerts = []
            
            for alert_data in self.state.recent_alerts[-MAX_RECENT_ALERTS:]:
                try:
                    alert_time = datetime.fromisoformat(alert_data.get('timestamp', ''))
                    if alert_time > cutoff_time:
                        recent_alerts.append(alert_data)
                except Exception:
                    continue  # Skip invalid timestamps
            
            # Limit seen IDs
            seen_ids = self.state.seen_ids[-MAX_SEEN_IDS:] if len(self.state.seen_ids) > MAX_SEEN_IDS else self.state.seen_ids
            
            self.state.seen_ids = seen_ids
            self.state.recent_alerts = recent_alerts
            
        except Exception as e:
            self.stats.add_error("clean_state", str(e))
    
    async def step_1_fetch_events(self) -> List[Event]:
        """Step 1: Fetch events from all sources."""
        logger.info("📥 Step 1: Fetching events from all sources")
        all_events = []
        
        # Fetch RSS events
        try:
            logger.info("📰 Fetching RSS feeds...")
            rss_events = scan_rss_feeds()
            all_events.extend(rss_events)
            self.stats.rss_events = len(rss_events)
            logger.info(f"   Found {len(rss_events)} potential events from RSS")
        except Exception as e:
            self.stats.add_error("rss_fetch", str(e))
        
        # Fetch Twitter events (with timeout)
        try:
            logger.info("🐦 Fetching Twitter feeds...")
            # Add timeout for Twitter to prevent hanging
            twitter_task = asyncio.create_task(asyncio.to_thread(scan_twitter_accounts))
            twitter_events = await asyncio.wait_for(twitter_task, timeout=60.0)
            all_events.extend(twitter_events)
            self.stats.twitter_events = len(twitter_events)
            logger.info(f"   Found {len(twitter_events)} potential events from Twitter")
        except asyncio.TimeoutError:
            self.stats.add_error("twitter_fetch", "Twitter fetch timed out after 60s")
            logger.warning("⚠️  Twitter fetch timed out, continuing with RSS only")
        except Exception as e:
            self.stats.add_error("twitter_fetch", str(e))
            logger.warning(f"⚠️  Twitter fetch failed: {str(e)}, continuing with RSS only")
        
        # Fetch Web Scraper events (from OpenClaw web-scraper skill)
        try:
            logger.info("🌐 Fetching web scraper events...")
            scraper_events = scan_web_scraper()
            all_events.extend(scraper_events)
            # Track web scraper events in stats (add to twitter for simplicity or create new field)
            if not hasattr(self.stats, 'web_scraper_events'):
                self.stats.web_scraper_events = 0
            self.stats.web_scraper_events = len(scraper_events)
            logger.info(f"   Found {len(scraper_events)} potential events from web scraper")
        except Exception as e:
            self.stats.add_error("web_scraper_fetch", str(e))
            logger.warning(f"⚠️  Web scraper fetch failed: {str(e)}, continuing without scraper events")
        
        logger.info(f"✅ Step 1 complete: {len(all_events)} total events fetched")
        return all_events
    
    def step_2_classify_events(self, events: List[Event]) -> List[Event]:
        """Step 2: Classify all events."""
        logger.info("🏷️ Step 2: Classifying events")
        classified_events = []
        
        for event in events:
            try:
                # Classify event if not already classified
                if not hasattr(event, 'category') or not event.category or event.category == "unknown":
                    classification_result = classify_event(event)
                    event = update_event_with_classification(event, classification_result)
                
                classified_events.append(event)
                self.stats.classified_events += 1
                
            except Exception as e:
                self.stats.add_error("classify_event", f"{event.id}: {str(e)}")
                # Still include event with default classification
                if not hasattr(event, 'category') or not event.category:
                    event.category = "GENERAL"
                classified_events.append(event)
        
        logger.info(f"✅ Step 2 complete: {len(classified_events)} events classified")
        return classified_events
    
    def step_3_score_events(self, events: List[Event]) -> List[Event]:
        """Step 3: Score all events for urgency."""
        logger.info("📊 Step 3: Scoring events for urgency")
        scored_events = []
        
        for event in events:
            try:
                # Score event if not already scored
                if not hasattr(event, 'urgency_score') or event.urgency_score == 0:
                    event.urgency_score = calculate_urgency_score(event)
                
                scored_events.append(event)
                self.stats.scored_events += 1
                
            except Exception as e:
                self.stats.add_error("score_event", f"{event.id}: {str(e)}")
                # Still include event with default score
                event.urgency_score = 5.0
                scored_events.append(event)
        
        # Sort by urgency score (highest first)
        scored_events.sort(key=lambda x: x.urgency_score, reverse=True)
        
        logger.info(f"✅ Step 3 complete: {len(scored_events)} events scored")
        if scored_events:
            avg_score = sum(e.urgency_score for e in scored_events) / len(scored_events)
            max_score = max(e.urgency_score for e in scored_events)
            logger.info(f"   Score range: max={max_score:.1f}, avg={avg_score:.1f}")
        
        return scored_events
    
    def step_4_deduplicate_events(self, events: List[Event]) -> List[Event]:
        """Step 4: Remove duplicate events."""
        logger.info("🔄 Step 4: Deduplicating events")
        new_events = []
        seen = set(self.state.seen_ids)
        
        for event in events:
            try:
                # Traditional ID-based deduplication
                event_id = generate_alert_id(event)
                if event_id in seen:
                    continue
                
                # Content-based deduplication
                if is_duplicate(event, self.state.recent_alerts):
                    logger.debug(f"   Skipping duplicate: {event.title[:40]}...")
                    continue
                
                # Only process events with urgency >= threshold
                if event.urgency_score >= MIN_URGENCY_THRESHOLD:
                    seen.add(event_id)
                    new_events.append(event)
                    self.state.recent_alerts.append(event.to_dict())
                    self.stats.deduplicated_events += 1
                
            except Exception as e:
                self.stats.add_error("deduplicate_event", f"{event.id}: {str(e)}")
        
        # Update seen IDs in state
        self.state.seen_ids = list(seen)
        
        logger.info(f"✅ Step 4 complete: {len(new_events)} unique events (urgency ≥{MIN_URGENCY_THRESHOLD})")
        return new_events
    
    async def step_5_map_to_markets(self, events: List[Event]) -> List[tuple]:
        """Step 5: Map events to affected markets."""
        logger.info("🎯 Step 5: Mapping events to markets")
        event_market_pairs = []
        
        for event in events:
            try:
                market_matches = self.market_mapper.get_affected_markets(event)
                
                if market_matches:
                    # Store event with its market matches
                    event_market_pairs.append((event, market_matches))
                    self.stats.mapped_markets += len(market_matches)
                    
                    logger.debug(f"   {event.id}: {len(market_matches)} market matches")
                
            except Exception as e:
                self.stats.add_error("map_markets", f"{event.id}: {str(e)}")
        
        logger.info(f"✅ Step 5 complete: {len(event_market_pairs)} events mapped to {self.stats.mapped_markets} markets")
        return event_market_pairs
    
    async def step_6_fetch_prices(self, event_market_pairs: List[tuple]) -> List[tuple]:
        """Step 6: Fetch current prices for mapped markets."""
        logger.info("💰 Step 6: Fetching market prices")
        
        # Collect all unique market slugs
        all_market_slugs = set()
        for event, market_matches in event_market_pairs:
            for match in market_matches:
                all_market_slugs.add(match.market_slug)
        
        logger.info(f"   Fetching prices for {len(all_market_slugs)} unique markets")
        
        # Fetch prices
        try:
            market_prices = await fetch_market_prices(list(all_market_slugs))
            price_lookup = {price.market_slug: price for price in market_prices}
            self.stats.price_fetches = len(market_prices)
            
            logger.info(f"   Retrieved {len(market_prices)} market prices")
            
        except Exception as e:
            self.stats.add_error("fetch_prices", str(e))
            return []
        
        # Filter event-market pairs to only those with available prices
        event_market_price_tuples = []
        for event, market_matches in event_market_pairs:
            valid_matches = []
            for match in market_matches:
                if match.market_slug in price_lookup:
                    valid_matches.append((match, price_lookup[match.market_slug]))
            
            if valid_matches:
                event_market_price_tuples.append((event, valid_matches))
        
        logger.info(f"✅ Step 6 complete: {len(event_market_price_tuples)} events with market prices")
        return event_market_price_tuples
    
    async def step_7_generate_signals(self, event_market_price_tuples: List[tuple]) -> List[tuple]:
        """Step 7: Generate trading signals."""
        logger.info("🔮 Step 7: Generating trading signals")
        event_signals_pairs = []
        total_signals = 0
        
        for event, market_matches_prices in event_market_price_tuples:
            try:
                # Process each event to generate all possible signals
                all_signals = await process_event_to_signals(event)
                
                # Filter signals for quality
                filtered_signals = filter_signals(all_signals, min_confidence=0.3)
                
                if filtered_signals:
                    event_signals_pairs.append((event, filtered_signals))
                    total_signals += len(filtered_signals)
                    self.stats.signals_generated += len(filtered_signals)
                    
                    logger.debug(f"   {event.id}: {len(filtered_signals)} signals generated")
                
            except Exception as e:
                self.stats.add_error("generate_signals", f"{event.id}: {str(e)}")
        
        logger.info(f"✅ Step 7 complete: {total_signals} signals generated for {len(event_signals_pairs)} events")
        return event_signals_pairs
    
    async def step_8_format_alerts(self, event_signals_pairs: List[tuple]) -> List[str]:
        """Step 8: Format alerts for Telegram."""
        logger.info("📱 Step 8: Formatting alerts")
        formatted_alerts = []
        
        # Sort by priority (TelegramAlertManager handles this)
        prioritized_pairs = self.telegram_manager.get_pending_alerts_sorted(event_signals_pairs)
        
        for event, signals in prioritized_pairs:
            try:
                # Check if we can send this alert (rate limiting, dedup)
                if self.telegram_manager.can_send_alert(event, signals):
                    alert_text = self.telegram_manager.format_alert(event, signals)
                    formatted_alerts.append(alert_text)
                    
                    # Record that we're planning to send this alert
                    self.telegram_manager.record_sent_alert(event, signals)
                    self.stats.alerts_formatted += 1
                    
                    logger.debug(f"   Formatted alert for {event.id}")
                else:
                    logger.debug(f"   Skipping alert for {event.id} (rate limited or duplicate)")
            
            except Exception as e:
                self.stats.add_error("format_alert", f"{event.id}: {str(e)}")
        
        logger.info(f"✅ Step 8 complete: {len(formatted_alerts)} alerts formatted")
        return formatted_alerts
    
    async def run_pipeline(self) -> Dict[str, Any]:
        """Execute the complete pipeline end-to-end."""
        logger.info("🚀 Starting complete event processing pipeline")
        self.stats.reset()
        
        try:
            # Step 1: Fetch Events
            events = await self.step_1_fetch_events()
            if not events:
                logger.warning("No events fetched, pipeline stopping")
                return self.finalize_pipeline([])
            
            # Step 2: Classify Events  
            events = self.step_2_classify_events(events)
            
            # Step 3: Score Events
            events = self.step_3_score_events(events)
            
            # Step 4: Deduplicate Events
            events = self.step_4_deduplicate_events(events)
            if not events:
                logger.info("No new events after deduplication")
                return self.finalize_pipeline([])
            
            # Step 5: Map to Markets
            event_market_pairs = await self.step_5_map_to_markets(events)
            if not event_market_pairs:
                logger.info("No events mapped to markets")
                return self.finalize_pipeline([])
            
            # Step 6: Fetch Prices
            event_market_price_tuples = await self.step_6_fetch_prices(event_market_pairs)
            if not event_market_price_tuples:
                logger.warning("No market prices available")
                return self.finalize_pipeline([])
            
            # Step 7: Generate Signals
            event_signals_pairs = await self.step_7_generate_signals(event_market_price_tuples)
            if not event_signals_pairs:
                logger.info("No signals generated")
                return self.finalize_pipeline([])
            
            # Step 8: Format Alerts
            formatted_alerts = await self.step_8_format_alerts(event_signals_pairs)
            
            return self.finalize_pipeline(formatted_alerts)
            
        except Exception as e:
            logger.error(f"Pipeline execution failed: {str(e)}")
            self.stats.add_error("pipeline", str(e))
            return self.finalize_pipeline([])
    
    def finalize_pipeline(self, alerts: List[str]) -> Dict[str, Any]:
        """Finalize pipeline execution and return results."""
        # Update state
        self.state.last_scan = datetime.now().isoformat()
        self.clean_state()
        self.save_state()
        
        # Log alerts to file
        if alerts:
            try:
                ALERTS_FILE.parent.mkdir(parents=True, exist_ok=True)
                with open(ALERTS_FILE, "a") as f:
                    for alert in alerts:
                        # Create a JSON record for the alert
                        alert_record = {
                            "timestamp": datetime.now().isoformat(),
                            "alert_text": alert,
                            "pipeline_run_id": self.stats.start_time.isoformat()
                        }
                        f.write(json.dumps(alert_record) + "\n")
            except Exception as e:
                self.stats.add_error("log_alerts", str(e))
        
        # Prepare results
        results = {
            "success": True,
            "alerts": alerts,
            "stats": self.stats.summary(),
            "telegram_stats": self.telegram_manager.get_stats()
        }
        
        # Log summary
        stats = self.stats.summary()
        duration = stats['duration_seconds']
        total_events = stats['events_fetched']['total']
        total_signals = stats['output']['signals_generated']
        total_alerts = len(alerts)
        
        logger.info("🎯 PIPELINE SUMMARY:")
        logger.info(f"   Duration: {duration:.1f}s")
        logger.info(f"   Events: {total_events} fetched → {stats['events_processed']['deduplicated']} processed")
        logger.info(f"   Markets: {stats['markets']['mapped']} mapped, {stats['markets']['prices_fetched']} prices fetched")
        logger.info(f"   Output: {total_signals} signals → {total_alerts} alerts ready")
        
        if stats['errors']:
            logger.warning(f"   Errors: {len(stats['errors'])} (see details above)")
        
        if alerts:
            logger.info("📤 ALERTS READY FOR TELEGRAM:")
            for i, alert in enumerate(alerts, 1):
                logger.info(f"\n--- Alert {i}/{len(alerts)} ---")
                # Log first few lines of each alert
                alert_lines = alert.strip().split('\n')[:4]
                for line in alert_lines:
                    logger.info(f"   {line}")
                if len(alert.split('\n')) > 4:
                    logger.info("   [...]")
        
        logger.info("✅ Pipeline execution complete")
        return results


async def main_once(telegram_rate_limit: int = 10) -> Dict[str, Any]:
    """Run pipeline once and return results."""
    pipeline = EventPipeline(telegram_rate_limit=telegram_rate_limit)
    return await pipeline.run_pipeline()


async def main_continuous(interval_minutes: int = 30, telegram_rate_limit: int = 10):
    """Run pipeline continuously with given interval."""
    logger.info(f"🔄 Starting continuous mode: scanning every {interval_minutes} minutes")
    
    pipeline = EventPipeline(telegram_rate_limit=telegram_rate_limit)
    
    while True:
        try:
            logger.info(f"\n{'='*60}")
            logger.info(f"🕐 Starting scheduled scan at {datetime.now().isoformat()}")
            
            results = await pipeline.run_pipeline()
            
            if results['alerts']:
                logger.info(f"✨ {len(results['alerts'])} alerts generated this run")
            else:
                logger.info("😴 No alerts this run")
            
            # Sleep until next run
            sleep_seconds = interval_minutes * 60
            logger.info(f"💤 Sleeping for {interval_minutes} minutes until next scan...")
            await asyncio.sleep(sleep_seconds)
            
        except KeyboardInterrupt:
            logger.info("\n🛑 Shutting down continuous mode")
            break
        except Exception as e:
            logger.error(f"Error in continuous mode: {str(e)}")
            logger.info(f"💤 Sleeping for {interval_minutes} minutes before retry...")
            await asyncio.sleep(interval_minutes * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Event-Driven Polymarket Scanner - Complete Pipeline")
    parser.add_argument("--once", action="store_true", help="Run pipeline once and exit")
    parser.add_argument("--interval", type=int, default=30, help="Continuous mode: scan interval in minutes (default: 30)")
    parser.add_argument("--telegram-rate-limit", type=int, default=10, help="Max Telegram alerts per hour (default: 10)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.info("🔍 Verbose logging enabled")
    
    try:
        if args.once:
            logger.info("🎯 Running pipeline once")
            results = asyncio.run(main_once(telegram_rate_limit=args.telegram_rate_limit))
            
            if results['alerts']:
                print(f"\n🎉 Generated {len(results['alerts'])} alerts:")
                for i, alert in enumerate(results['alerts'], 1):
                    print(f"\n--- Alert {i} ---")
                    print(alert)
            else:
                print("\n😴 No alerts generated")
        else:
            logger.info("🔄 Running pipeline in continuous mode")
            asyncio.run(main_continuous(
                interval_minutes=args.interval,
                telegram_rate_limit=args.telegram_rate_limit
            ))
    
    except KeyboardInterrupt:
        logger.info("\n🛑 Graceful shutdown")
        sys.exit(0)
    except Exception as e:
        logger.error(f"💥 Fatal error: {str(e)}")
        sys.exit(1)