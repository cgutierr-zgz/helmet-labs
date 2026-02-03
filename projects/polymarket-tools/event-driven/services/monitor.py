#!/usr/bin/env python3
"""
Event Monitor Service - Production monitoring for the Polymarket event-driven system.

Runs the pipeline periodically and logs signals to data/signals_log.jsonl
Provides graceful shutdown and structured logging.
"""

import asyncio
import json
import logging
import signal
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import time

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from main import main_once
from services.health import HealthChecker
from services.alert_queue import AlertQueue


class EventMonitor:
    """
    Production monitor that runs the event pipeline periodically.
    
    Features:
    - Configurable scan interval (default 5 minutes)
    - Structured logging to file
    - Signal persistence to data/signals_log.jsonl
    - Graceful shutdown on SIGTERM/SIGINT
    - Integration with health checker
    """
    
    def __init__(self, 
                 interval_minutes: int = 5,
                 data_dir: str = "data",
                 logs_dir: str = "logs",
                 dry_run: bool = False,
                 verbose: bool = False):
        self.interval_minutes = interval_minutes
        self.data_dir = Path(data_dir)
        self.logs_dir = Path(logs_dir)
        self.dry_run = dry_run
        self.verbose = verbose
        
        # Ensure directories exist
        self.data_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)
        
        # Signal log file
        self.signals_log_file = self.data_dir / "signals_log.jsonl"
        
        # Statistics
        self.start_time = datetime.now()
        self.scan_count = 0
        self.total_signals = 0
        self.total_alerts = 0
        self.last_scan_time = None
        self.last_scan_duration = None
        self.errors_count = 0
        
        # Shutdown flag
        self._shutdown = False
        
        # Initialize health checker and alert queue
        self.health_checker = HealthChecker(self)
        self.alert_queue = AlertQueue()
        
        # Setup logging
        self._setup_logging()
        
        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        self.logger.info(f"🚀 EventMonitor initialized - interval: {interval_minutes}min, dry_run: {dry_run}")
    
    def _setup_logging(self):
        """Configure structured logging."""
        # Create formatter with emojis for monitor output
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s %(message)s',
            datefmt='%H:%M:%S'
        )
        
        # File handler
        file_handler = logging.FileHandler(self.logs_dir / "monitor.log")
        file_handler.setFormatter(formatter)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        # Configure logger
        self.logger = logging.getLogger(f"{__name__}.EventMonitor")
        self.logger.setLevel(logging.DEBUG if self.verbose else logging.INFO)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        # Prevent propagation to avoid duplicate logs
        self.logger.propagate = False
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.logger.info(f"🛑 Received signal {signum}, initiating graceful shutdown...")
        self._shutdown = True
    
    def _log_signal_to_file(self, event_id: str, signal_data: Dict[str, Any]):
        """Log generated signal to signals_log.jsonl."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_id": event_id,
            "signal": signal_data,
            "sent": False  # Will be updated when alert is actually sent
        }
        
        with open(self.signals_log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    
    def _update_signal_sent_status(self, event_id: str, sent: bool = True):
        """Update sent status of a signal in the log."""
        # For now, we'll just log the update
        # In a production system, you might want to update the actual file
        self.logger.debug(f"📤 Signal for event {event_id} marked as sent: {sent}")
    
    async def _run_single_scan(self) -> Dict[str, Any]:
        """Execute a single pipeline scan."""
        scan_start_time = time.time()
        self.scan_count += 1
        
        self.logger.info(f"🔄 Scan #{self.scan_count} started")
        
        try:
            if self.dry_run:
                # Simulate pipeline run for testing
                await asyncio.sleep(1)  # Simulate processing time
                results = {
                    'events_fetched': 15,
                    'rss_events': 8,
                    'twitter_events': 7,
                    'signals_generated': 2,
                    'alerts': [
                        {
                            'id': f'test_alert_{self.scan_count}',
                            'market': 'Test Market',
                            'signal': 'TEST',
                            'confidence': 0.75
                        }
                    ]
                }
            else:
                # Run actual pipeline
                results = await main_once(telegram_rate_limit=5)
            
            # Update statistics
            scan_duration = time.time() - scan_start_time
            self.last_scan_time = datetime.now()
            self.last_scan_duration = scan_duration
            
            events_fetched = results.get('events_fetched', 0)
            rss_events = results.get('rss_events', 0)
            twitter_events = results.get('twitter_events', 0)
            signals_generated = results.get('signals_generated', 0)
            alerts = results.get('alerts', [])
            
            self.total_signals += signals_generated
            self.total_alerts += len(alerts)
            
            # Log results with emojis
            self.logger.info(f"📥 Fetched {events_fetched} events ({rss_events} RSS, {twitter_events} Twitter)")
            
            if signals_generated > 0:
                self.logger.info(f"🎯 Generated {signals_generated} signals")
                
                # Log each signal to file
                for i, alert in enumerate(alerts):
                    event_id = alert.get('id', f'unknown_{self.scan_count}_{i}')
                    self._log_signal_to_file(event_id, alert)
                    
                    # Queue alert
                    self.alert_queue.add_alert(alert)
                    
                    # Log alert summary
                    market = alert.get('market', 'Unknown')
                    signal_type = alert.get('signal', 'Unknown')
                    confidence = alert.get('confidence', 0)
                    self.logger.info(f"📱 Alert queued: [{market}] {signal_type} signal (confidence: {confidence:.0%})")
            
            self.logger.info(f"✅ Scan complete ({scan_duration:.1f}s)")
            
            return results
            
        except Exception as e:
            self.errors_count += 1
            scan_duration = time.time() - scan_start_time
            self.last_scan_duration = scan_duration
            self.logger.error(f"❌ Scan #{self.scan_count} failed after {scan_duration:.1f}s: {str(e)}")
            raise
    
    def get_pending_alerts(self) -> List[Dict[str, Any]]:
        """Get alerts pending to be sent."""
        return self.alert_queue.get_pending_alerts()
    
    def mark_alert_sent(self, alert_id: str):
        """Mark an alert as sent."""
        self.alert_queue.mark_sent(alert_id)
        self._update_signal_sent_status(alert_id, True)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current monitor status."""
        uptime = datetime.now() - self.start_time
        
        return {
            "status": "running" if not self._shutdown else "shutting_down",
            "uptime_seconds": uptime.total_seconds(),
            "scan_count": self.scan_count,
            "total_signals": self.total_signals,
            "total_alerts": self.total_alerts,
            "errors_count": self.errors_count,
            "last_scan_time": self.last_scan_time.isoformat() if self.last_scan_time else None,
            "last_scan_duration": self.last_scan_duration,
            "next_scan_in": self.interval_minutes * 60 - ((datetime.now() - self.last_scan_time).total_seconds() if self.last_scan_time else 0),
            "pending_alerts": len(self.get_pending_alerts())
        }
    
    async def run(self):
        """Run the monitor continuously until shutdown."""
        self.logger.info(f"🏃 EventMonitor starting continuous monitoring (interval: {self.interval_minutes} min)")
        
        while not self._shutdown:
            try:
                # Update health status
                self.health_checker.update_status()
                
                # Run scan
                await self._run_single_scan()
                
                # Sleep until next scan
                if not self._shutdown:
                    sleep_seconds = self.interval_minutes * 60
                    self.logger.info(f"💤 Sleeping {self.interval_minutes} minutes until next scan...")
                    
                    # Sleep in chunks to allow responsive shutdown
                    for _ in range(sleep_seconds):
                        if self._shutdown:
                            break
                        await asyncio.sleep(1)
                
            except Exception as e:
                self.errors_count += 1
                self.logger.error(f"💥 Error in monitor loop: {str(e)}")
                
                # Sleep before retry
                self.logger.info(f"💤 Sleeping {self.interval_minutes} minutes before retry...")
                for _ in range(self.interval_minutes * 60):
                    if self._shutdown:
                        break
                    await asyncio.sleep(1)
        
        self.logger.info("🏁 EventMonitor shutdown complete")
    
    def shutdown(self):
        """Trigger graceful shutdown."""
        self._shutdown = True