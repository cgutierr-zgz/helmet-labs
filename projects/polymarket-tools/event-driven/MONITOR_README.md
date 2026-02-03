# Event Monitor Service - Production Monitoring

🚀 **ENHANCE-002**: Production monitor service with health checks

## Overview

The Event Monitor Service provides 24/7 monitoring of the Polymarket event-driven trading system. It runs the pipeline periodically, logs signals, manages alerts, and provides health monitoring.

## Components

### Core Services

- **`services/monitor.py`**: Main `EventMonitor` class that orchestrates periodic pipeline execution
- **`services/health.py`**: Health checking and system metrics
- **`services/alert_queue.py`**: Alert queuing with deduplication and rate limiting
- **`run_monitor.py`**: Production entry point with CLI interface

### Configuration

- **`com.helmet.eventmonitor.plist`**: macOS launchd configuration for daemon mode

## Quick Start

### Manual Run (Development)

```bash
# Basic run (5 min intervals)
./run_monitor.py

# Custom interval with verbose logging
./run_monitor.py --interval 10 --verbose

# Test mode (no actual signals)
./run_monitor.py --dry-run --verbose

# Show current status
./run_monitor.py --status

# Add test alert to queue
./run_monitor.py --test-alert
```

### Production Deployment (macOS)

1. **Install the service:**
```bash
# Copy plist to LaunchDaemons
sudo cp com.helmet.eventmonitor.plist /Library/LaunchDaemons/

# Load and start the service
sudo launchctl load /Library/LaunchDaemons/com.helmet.eventmonitor.plist
sudo launchctl start com.helmet.eventmonitor
```

2. **Check status:**
```bash
# Check if service is running
sudo launchctl list | grep eventmonitor

# View logs
tail -f logs/launchd_stdout.log
tail -f logs/monitor.log
```

3. **Stop/restart service:**
```bash
# Stop
sudo launchctl stop com.helmet.eventmonitor

# Restart  
sudo launchctl stop com.helmet.eventmonitor
sudo launchctl start com.helmet.eventmonitor

# Unload (remove from auto-start)
sudo launchctl unload /Library/LaunchDaemons/com.helmet.eventmonitor.plist
```

## File Structure

```
project/
├── services/
│   ├── __init__.py          # Services package
│   ├── monitor.py           # EventMonitor class
│   ├── health.py            # HealthChecker class  
│   └── alert_queue.py       # AlertQueue class
├── data/
│   ├── signals_log.jsonl    # All generated signals
│   ├── health_status.json   # Current health status
│   └── alert_queue.json     # Alert queue state
├── logs/
│   ├── monitor.log          # Monitor service logs
│   ├── launchd_stdout.log   # Daemon stdout
│   └── launchd_stderr.log   # Daemon stderr
├── run_monitor.py           # Production entry point
└── com.helmet.eventmonitor.plist # launchd config
```

## Signal Logging

All generated signals are logged to `data/signals_log.jsonl`:

```json
{
  "timestamp": "2024-02-03T18:30:16.123456",
  "event_id": "rss_fed_decision_123", 
  "signal": {
    "id": "alert_123",
    "market": "Fed Rate Decision",
    "signal": "RATE_CUT_LIKELY",
    "confidence": 0.78,
    "urgency_score": 85
  },
  "sent": false
}
```

## Monitor Output

The monitor provides structured output with emojis for easy reading:

```
[18:30:00] 🔄 Scan #42 started
[18:30:15] 📥 Fetched 23 events (12 RSS, 11 Twitter)  
[18:30:16] 🎯 Generated 2 signals
[18:30:16] 📱 Alert queued: [Fed Rate Decision] RATE_CUT_LIKELY signal (confidence: 78%)
[18:30:16] ✅ Scan complete (16s)
[18:30:16] 💤 Sleeping 5 minutes until next scan...
```

## Health Monitoring

Health status is written to `data/health_status.json`:

```json
{
  "timestamp": "2024-02-03T18:30:16.123456",
  "health": "healthy",
  "metrics": {
    "uptime_seconds": 3600,
    "uptime_human": "1:00:00",
    "events_per_hour": 12.5,
    "signals_per_day": 8.2,
    "error_rate": 0.02,
    "total_scans": 12,
    "pending_alerts": 3
  }
}
```

View human-readable status:
```bash
./run_monitor.py --status
```

## Alert Queue Features

### Deduplication
- Prevents duplicate alerts within 24h window
- Based on market + signal type + event ID hash

### Rate Limiting  
- Default: max 5 alerts per hour
- Configurable per instance
- Tracks sent alerts in rolling window

### Prioritization
- **CRITICAL**: confidence ≥80% + urgency ≥80
- **HIGH**: Important signals + confidence ≥70%  
- **MEDIUM**: confidence ≥60%
- **LOW**: Everything else

### Persistence
- Queue state survives restarts
- Failed alerts can be retried
- Automatic cleanup of old data

## Configuration Options

### CLI Arguments
- `--interval N`: Scan interval in minutes (default: 5)
- `--verbose`: Enable debug logging
- `--dry-run`: Test mode without actual pipeline execution
- `--status`: Show current health status
- `--test-alert`: Add test alert to queue

### Environment Variables
- `PYTHONPATH`: Ensure project root is in path
- `PATH`: Include venv/bin for Python dependencies

## Monitoring and Alerting

### Log Files
- **`logs/monitor.log`**: Main service logs with structured format
- **`logs/launchd_stdout.log`**: Daemon stdout (when running via launchd)
- **`logs/launchd_stderr.log`**: Daemon stderr and crash info

### Health Checks
- Automatic cleanup of old data
- Error rate tracking
- Scan duration monitoring  
- Queue size limits
- Activity level validation

### Integration Points
- Pipeline results are logged to `data/signals_log.jsonl`
- Health status written to `data/health_status.json`
- Alert queue persisted to `data/alert_queue.json`

## Troubleshooting

### Common Issues

1. **Service won't start:**
   - Check Python path in plist file
   - Verify virtual environment exists
   - Check permissions on directories

2. **No signals generated:**
   - Verify RSS feeds and Twitter accounts are accessible
   - Check main pipeline configuration
   - Run with `--dry-run` to test monitor logic

3. **Alerts not being sent:**
   - Check rate limiting settings
   - Verify alert queue is not full
   - Check deduplication window

### Debug Mode
```bash
./run_monitor.py --interval 1 --verbose --dry-run
```

### Log Analysis
```bash
# Monitor service logs
tail -f logs/monitor.log | grep "🔄\|❌\|📱"

# Check for errors
grep "ERROR\|❌" logs/monitor.log

# Count signals generated today
grep "$(date +%Y-%m-%d)" data/signals_log.jsonl | wc -l
```

## Development

### Testing
```bash
# Test monitor components
python -m pytest tests/ -v

# Test with dry run
./run_monitor.py --dry-run --interval 1 --verbose

# Test alert queue
./run_monitor.py --test-alert
./run_monitor.py --status
```

### Extending
- Add custom health checks in `services/health.py`
- Extend alert prioritization in `services/alert_queue.py` 
- Add monitoring metrics in `services/monitor.py`

---

🏥 **Health Status**: Monitor is production-ready with comprehensive logging, error handling, and graceful shutdown.