#!/usr/bin/env python3
"""
Event Monitor Service Runner
Production entry point for the Polymarket event-driven monitoring system.

This script starts the EventMonitor service with configurable parameters
and provides graceful shutdown handling.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add current directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent))

from services.monitor import EventMonitor
from services.health import HealthChecker


async def run_monitor(interval: int, verbose: bool, dry_run: bool):
    """Run the event monitor with given parameters."""
    
    # Create monitor
    monitor = EventMonitor(
        interval_minutes=interval,
        data_dir="data",
        logs_dir="logs",
        dry_run=dry_run,
        verbose=verbose
    )
    
    try:
        # Run the monitor
        await monitor.run()
    except Exception as e:
        monitor.logger.error(f"🔥 Fatal error in monitor: {str(e)}")
        raise
    finally:
        monitor.logger.info("🔚 Monitor service stopped")


def setup_logging(verbose: bool = False):
    """Setup basic logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=level,
        format='[%(asctime)s] %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler('logs/monitor.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )


def validate_args(args):
    """Validate command line arguments."""
    if args.interval < 1:
        raise ValueError("Interval must be at least 1 minute")
    
    if args.interval > 1440:  # 24 hours
        raise ValueError("Interval cannot exceed 1440 minutes (24 hours)")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Event Monitor Service for Polymarket Event-Driven Trading",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Run with default settings (5 min interval)
  %(prog)s --interval 10 --verbose  # 10 min interval with verbose logging
  %(prog)s --dry-run                # Test mode without actual trading signals
  %(prog)s --interval 1 --verbose --dry-run  # Debug mode
  
Logs:
  Monitor logs: logs/monitor.log
  Health status: data/health_status.json
  Signals log: data/signals_log.jsonl
  Alert queue: data/alert_queue.json
"""
    )
    
    parser.add_argument(
        "--interval", 
        type=int, 
        default=5,
        help="Scan interval in minutes (default: 5)"
    )
    
    parser.add_argument(
        "--verbose", 
        action="store_true",
        help="Enable verbose logging"
    )
    
    parser.add_argument(
        "--dry-run", 
        action="store_true",
        help="Run in test mode without actual pipeline execution"
    )
    
    parser.add_argument(
        "--status", 
        action="store_true",
        help="Show current health status and exit"
    )
    
    parser.add_argument(
        "--test-alert", 
        action="store_true",
        help="Add a test alert to the queue and exit"
    )
    
    args = parser.parse_args()
    
    try:
        validate_args(args)
    except ValueError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    
    # Ensure directories exist
    Path("logs").mkdir(exist_ok=True)
    Path("data").mkdir(exist_ok=True)
    
    # Handle special commands
    if args.status:
        show_status()
        return
    
    if args.test_alert:
        test_alert_queue()
        return
    
    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    # Show startup banner
    print("🚀 Event Monitor Service - Polymarket Event-Driven Trading")
    print("=" * 60)
    print(f"📊 Scan interval: {args.interval} minutes")
    print(f"🔧 Dry run mode: {'Yes' if args.dry_run else 'No'}")
    print(f"📝 Verbose logging: {'Yes' if args.verbose else 'No'}")
    print(f"📁 Data directory: {Path('data').absolute()}")
    print(f"📋 Logs directory: {Path('logs').absolute()}")
    print("=" * 60)
    
    if args.dry_run:
        print("⚠️  Running in DRY RUN mode - no actual signals will be generated")
        print()
    
    logger.info("🌟 Starting Event Monitor Service")
    logger.info(f"⚙️  Configuration: interval={args.interval}min, verbose={args.verbose}, dry_run={args.dry_run}")
    
    try:
        # Run the monitor
        asyncio.run(run_monitor(args.interval, args.verbose, args.dry_run))
    except KeyboardInterrupt:
        logger.info("🛑 Received shutdown signal")
    except Exception as e:
        logger.error(f"💥 Fatal error: {str(e)}")
        sys.exit(1)
    
    logger.info("👋 Event Monitor Service stopped")


def show_status():
    """Show current system status."""
    from services.health import HealthChecker
    
    try:
        # Try to read existing health status
        health_file = Path("data/health_status.json")
        if health_file.exists():
            import json
            with open(health_file) as f:
                status = json.load(f)
            
            print("📊 Current System Status")
            print("=" * 40)
            print(f"🏥 Health: {status['health'].upper()}")
            print(f"⏰ Last Update: {status['timestamp']}")
            
            if 'metrics' in status:
                metrics = status['metrics']
                print(f"📈 Uptime: {metrics.get('uptime_human', 'Unknown')}")
                print(f"🔄 Total Scans: {metrics.get('total_scans', 0)}")
                print(f"🎯 Total Signals: {metrics.get('total_signals', 0)}")
                print(f"📱 Total Alerts: {metrics.get('total_alerts', 0)}")
                print(f"❌ Error Rate: {metrics.get('error_rate', 0):.1%}")
                print(f"📊 Events/Hour: {metrics.get('events_per_hour', 0):.1f}")
                print(f"🎯 Signals/Day: {metrics.get('signals_per_day', 0):.1f}")
                print(f"📋 Pending Alerts: {metrics.get('pending_alerts', 0)}")
                
                if metrics.get('last_scan', {}).get('time'):
                    ago_min = metrics['last_scan'].get('ago_seconds', 0) // 60
                    duration = metrics['last_scan'].get('duration_seconds', 0)
                    print(f"🕐 Last Scan: {ago_min:.0f}m ago ({duration:.1f}s)")
        else:
            print("⚠️  No health status file found. Monitor may not be running.")
    
    except Exception as e:
        print(f"❌ Error reading status: {e}")


def test_alert_queue():
    """Add a test alert to the queue."""
    from services.alert_queue import AlertQueue
    from datetime import datetime
    
    try:
        queue = AlertQueue()
        
        test_alert = {
            'id': f'test_alert_{int(datetime.now().timestamp())}',
            'market': 'Test Market',
            'signal': 'TEST_SIGNAL',
            'confidence': 0.85,
            'urgency_score': 75,
            'timestamp': datetime.now().isoformat(),
            'description': 'This is a test alert generated by --test-alert'
        }
        
        if queue.add_alert(test_alert):
            print("✅ Test alert added to queue successfully")
            
            stats = queue.get_queue_stats()
            print(f"📋 Queue now has {stats['pending_count']} pending alerts")
            print(f"🚦 Rate limit: {stats['rate_limit_status']['remaining_this_hour']} alerts remaining this hour")
        else:
            print("❌ Failed to add test alert (possibly duplicate or rate limited)")
        
    except Exception as e:
        print(f"❌ Error testing alert queue: {e}")


if __name__ == "__main__":
    main()