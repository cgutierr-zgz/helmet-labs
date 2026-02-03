#!/usr/bin/env python3
"""
Health Checker - System health monitoring for the event-driven system.

Tracks metrics like uptime, events/hour, signals/day, errors.
Writes status to a JSON file for external monitoring.
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional


class HealthChecker:
    """
    Health monitoring for the EventMonitor system.
    
    Tracks and reports:
    - System uptime
    - Events processed per hour
    - Signals generated per day  
    - Error rates
    - Last scan information
    """
    
    def __init__(self, monitor=None, status_file: str = "data/health_status.json"):
        self.monitor = monitor
        self.status_file = Path(status_file)
        self.status_file.parent.mkdir(exist_ok=True)
        
        # Historical data for rate calculations
        self.hourly_events = []  # (timestamp, count) tuples
        self.daily_signals = []  # (timestamp, count) tuples
        self.error_log = []      # (timestamp, error) tuples
        
        # Performance thresholds
        self.thresholds = {
            "max_scan_duration": 300,    # 5 minutes
            "max_error_rate": 0.1,       # 10% error rate
            "min_events_per_hour": 5,    # Minimum expected activity
            "max_queue_size": 100        # Maximum pending alerts
        }
        
        self.start_time = datetime.now()
    
    def _cleanup_old_data(self):
        """Remove data older than retention periods."""
        now = datetime.now()
        
        # Keep hourly data for 24 hours
        cutoff_hours = now - timedelta(hours=24)
        self.hourly_events = [(ts, count) for ts, count in self.hourly_events 
                             if ts > cutoff_hours]
        
        # Keep daily data for 30 days
        cutoff_days = now - timedelta(days=30)
        self.daily_signals = [(ts, count) for ts, count in self.daily_signals 
                             if ts > cutoff_days]
        
        # Keep error log for 7 days
        cutoff_errors = now - timedelta(days=7)
        self.error_log = [(ts, err) for ts, err in self.error_log 
                         if ts > cutoff_errors]
    
    def _calculate_events_per_hour(self) -> float:
        """Calculate events processed per hour (last 24h average)."""
        if not self.hourly_events:
            return 0.0
        
        now = datetime.now()
        last_24h = now - timedelta(hours=24)
        
        recent_events = [count for ts, count in self.hourly_events if ts > last_24h]
        
        if not recent_events:
            return 0.0
        
        hours_elapsed = min(24, (now - self.start_time).total_seconds() / 3600)
        if hours_elapsed == 0:
            return 0.0
        
        return sum(recent_events) / hours_elapsed
    
    def _calculate_signals_per_day(self) -> float:
        """Calculate signals generated per day (last 7 days average)."""
        if not self.daily_signals:
            return 0.0
        
        now = datetime.now()
        last_7d = now - timedelta(days=7)
        
        recent_signals = [count for ts, count in self.daily_signals if ts > last_7d]
        
        if not recent_signals:
            return 0.0
        
        days_elapsed = min(7, (now - self.start_time).total_seconds() / (24 * 3600))
        if days_elapsed == 0:
            return 0.0
        
        return sum(recent_signals) / days_elapsed
    
    def _calculate_error_rate(self) -> float:
        """Calculate error rate (last 24h)."""
        if not self.monitor:
            return 0.0
        
        scan_count = self.monitor.scan_count
        error_count = self.monitor.errors_count
        
        if scan_count == 0:
            return 0.0
        
        return error_count / scan_count
    
    def _get_health_status(self) -> str:
        """Determine overall health status."""
        if not self.monitor:
            return "unknown"
        
        # Check various health indicators
        issues = []
        
        # Check if monitor is running
        if self.monitor._shutdown:
            return "shutting_down"
        
        # Check scan duration
        if (self.monitor.last_scan_duration and 
            self.monitor.last_scan_duration > self.thresholds["max_scan_duration"]):
            issues.append("slow_scans")
        
        # Check error rate
        error_rate = self._calculate_error_rate()
        if error_rate > self.thresholds["max_error_rate"]:
            issues.append("high_error_rate")
        
        # Check if scans are happening
        if (self.monitor.last_scan_time and 
            (datetime.now() - self.monitor.last_scan_time).total_seconds() > 
            (self.monitor.interval_minutes * 60 * 2)):  # 2x expected interval
            issues.append("stale_scans")
        
        # Check queue size
        if self.monitor.alert_queue and len(self.monitor.get_pending_alerts()) > self.thresholds["max_queue_size"]:
            issues.append("queue_overflow")
        
        # Check activity level
        events_per_hour = self._calculate_events_per_hour()
        if events_per_hour < self.thresholds["min_events_per_hour"]:
            issues.append("low_activity")
        
        if issues:
            return "degraded"
        
        return "healthy"
    
    def record_scan_completion(self, events_count: int, signals_count: int, scan_duration: float):
        """Record completion of a scan for metrics."""
        now = datetime.now()
        
        # Record hourly events
        self.hourly_events.append((now, events_count))
        
        # Record daily signals (aggregate by day)
        today = now.date()
        if self.daily_signals and self.daily_signals[-1][0].date() == today:
            # Update today's count
            last_ts, last_count = self.daily_signals[-1]
            self.daily_signals[-1] = (now, last_count + signals_count)
        else:
            # New day
            self.daily_signals.append((now, signals_count))
    
    def record_error(self, error: str):
        """Record an error for tracking."""
        self.error_log.append((datetime.now(), error))
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current system metrics."""
        if not self.monitor:
            return {"error": "No monitor attached"}
        
        now = datetime.now()
        uptime = now - self.start_time
        
        return {
            "uptime_seconds": uptime.total_seconds(),
            "uptime_human": str(uptime).split('.')[0],  # Remove microseconds
            "events_per_hour": round(self._calculate_events_per_hour(), 2),
            "signals_per_day": round(self._calculate_signals_per_day(), 2),
            "error_rate": round(self._calculate_error_rate(), 3),
            "total_scans": self.monitor.scan_count,
            "total_signals": self.monitor.total_signals,
            "total_alerts": self.monitor.total_alerts,
            "total_errors": self.monitor.errors_count,
            "last_scan": {
                "time": self.monitor.last_scan_time.isoformat() if self.monitor.last_scan_time else None,
                "duration_seconds": round(self.monitor.last_scan_duration, 2) if self.monitor.last_scan_duration else None,
                "ago_seconds": (now - self.monitor.last_scan_time).total_seconds() if self.monitor.last_scan_time else None
            },
            "pending_alerts": len(self.monitor.get_pending_alerts()) if hasattr(self.monitor, 'get_pending_alerts') else 0,
            "queue_size": len(self.monitor.alert_queue.pending_alerts) if hasattr(self.monitor, 'alert_queue') else 0
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get complete health status."""
        health_status = self._get_health_status()
        metrics = self.get_metrics()
        
        status = {
            "timestamp": datetime.now().isoformat(),
            "health": health_status,
            "metrics": metrics,
            "thresholds": self.thresholds,
            "system": {
                "interval_minutes": self.monitor.interval_minutes if self.monitor else None,
                "dry_run": self.monitor.dry_run if self.monitor else None,
                "verbose": self.monitor.verbose if self.monitor else None
            }
        }
        
        return status
    
    def update_status(self):
        """Update and write status to file."""
        self._cleanup_old_data()
        status = self.get_status()
        
        try:
            with open(self.status_file, 'w') as f:
                json.dump(status, f, indent=2)
        except Exception as e:
            # Can't log to monitor logger here to avoid circular dependency
            print(f"Error writing health status: {e}")
    
    def get_status_summary(self) -> str:
        """Get a human-readable status summary."""
        status = self.get_status()
        health = status["health"]
        metrics = status["metrics"]
        
        summary_lines = [
            f"🏥 Health: {health.upper()}",
            f"⏰ Uptime: {metrics['uptime_human']}",
            f"📊 Scans: {metrics['total_scans']} ({metrics['error_rate']:.1%} errors)",
            f"📈 Activity: {metrics['events_per_hour']:.1f} events/hour, {metrics['signals_per_day']:.1f} signals/day",
            f"📱 Queue: {metrics['pending_alerts']} pending alerts"
        ]
        
        if metrics['last_scan']['time']:
            ago_minutes = metrics['last_scan']['ago_seconds'] // 60
            summary_lines.append(f"🕐 Last scan: {ago_minutes:.0f}m ago ({metrics['last_scan']['duration_seconds']:.1f}s)")
        
        return "\n".join(summary_lines)