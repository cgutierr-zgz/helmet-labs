#!/usr/bin/env python3
"""
Alert Queue - Alert queuing system with deduplication and rate limiting.

Features:
- Alert queuing with priority based on urgency score
- Deduplication to prevent spam
- Rate limiting (max N alerts per hour)
- Persistent storage
"""

import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class AlertPriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class QueuedAlert:
    """Represents an alert in the queue."""
    id: str
    alert_data: Dict[str, Any]
    priority: AlertPriority
    created_at: datetime
    sent_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'alert_data': self.alert_data,
            'priority': self.priority.value,
            'created_at': self.created_at.isoformat(),
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QueuedAlert':
        """Create from dictionary."""
        return cls(
            id=data['id'],
            alert_data=data['alert_data'],
            priority=AlertPriority(data['priority']),
            created_at=datetime.fromisoformat(data['created_at']),
            sent_at=datetime.fromisoformat(data['sent_at']) if data['sent_at'] else None,
            retry_count=data['retry_count'],
            max_retries=data['max_retries']
        )


class AlertQueue:
    """
    Alert queuing system with deduplication and rate limiting.
    
    Features:
    - Priority-based queue (higher priority alerts sent first)
    - Deduplication based on alert content hash
    - Rate limiting to prevent spam
    - Persistent storage for queue state
    """
    
    def __init__(self,
                 max_alerts_per_hour: int = 5,
                 queue_file: str = "data/alert_queue.json",
                 dedup_window_hours: int = 24):
        self.max_alerts_per_hour = max_alerts_per_hour
        self.queue_file = Path(queue_file)
        self.dedup_window_hours = dedup_window_hours
        
        # Ensure data directory exists
        self.queue_file.parent.mkdir(exist_ok=True)
        
        # In-memory queue
        self.pending_alerts: List[QueuedAlert] = []
        self.sent_alerts: List[QueuedAlert] = []
        
        # Deduplication cache (content_hash -> timestamp)
        self.dedup_cache: Dict[str, datetime] = {}
        
        # Load existing queue state
        self._load_queue_state()
    
    def _generate_alert_hash(self, alert_data: Dict[str, Any]) -> str:
        """Generate a hash for deduplication."""
        # Use key fields to generate hash
        key_fields = {
            'market': alert_data.get('market', ''),
            'signal': alert_data.get('signal', ''),
            'event_id': alert_data.get('id', ''),
            # Don't include timestamp or confidence in hash to allow similar alerts
        }
        
        content = json.dumps(key_fields, sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()
    
    def _determine_priority(self, alert_data: Dict[str, Any]) -> AlertPriority:
        """Determine alert priority based on urgency score and other factors."""
        confidence = alert_data.get('confidence', 0)
        urgency = alert_data.get('urgency_score', 0)
        signal_type = alert_data.get('signal', '').lower()
        
        # Critical signals (high confidence + high urgency)
        if confidence >= 0.8 and urgency >= 80:
            return AlertPriority.CRITICAL
        
        # High priority for important market signals
        high_priority_signals = ['fed_decision', 'major_event', 'breaking_news']
        if any(sig in signal_type for sig in high_priority_signals) and confidence >= 0.7:
            return AlertPriority.HIGH
        
        # Medium priority for good confidence
        if confidence >= 0.6:
            return AlertPriority.MEDIUM
        
        # Low priority for everything else
        return AlertPriority.LOW
    
    def _is_duplicate(self, alert_data: Dict[str, Any]) -> bool:
        """Check if alert is a duplicate within the dedup window."""
        content_hash = self._generate_alert_hash(alert_data)
        
        if content_hash in self.dedup_cache:
            last_seen = self.dedup_cache[content_hash]
            if (datetime.now() - last_seen).total_seconds() < self.dedup_window_hours * 3600:
                return True
        
        return False
    
    def _cleanup_old_entries(self):
        """Remove old entries from dedup cache and sent alerts."""
        now = datetime.now()
        cutoff = now - timedelta(hours=self.dedup_window_hours)
        
        # Clean dedup cache
        self.dedup_cache = {h: ts for h, ts in self.dedup_cache.items() if ts > cutoff}
        
        # Clean old sent alerts (keep last 1000 for stats)
        self.sent_alerts = sorted(self.sent_alerts, key=lambda x: x.created_at, reverse=True)[:1000]
    
    def _check_rate_limit(self) -> bool:
        """Check if we're under the rate limit."""
        if self.max_alerts_per_hour <= 0:
            return True  # No rate limit
        
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        
        # Count alerts sent in the last hour
        recent_sent = [alert for alert in self.sent_alerts 
                      if alert.sent_at and alert.sent_at > one_hour_ago]
        
        return len(recent_sent) < self.max_alerts_per_hour
    
    def _save_queue_state(self):
        """Save queue state to file."""
        state = {
            'pending_alerts': [alert.to_dict() for alert in self.pending_alerts],
            'sent_alerts': [alert.to_dict() for alert in self.sent_alerts[-100:]],  # Keep last 100
            'dedup_cache': {h: ts.isoformat() for h, ts in self.dedup_cache.items()},
            'last_updated': datetime.now().isoformat()
        }
        
        try:
            with open(self.queue_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            print(f"Error saving queue state: {e}")
    
    def _load_queue_state(self):
        """Load queue state from file."""
        if not self.queue_file.exists():
            return
        
        try:
            with open(self.queue_file, 'r') as f:
                state = json.load(f)
            
            # Load pending alerts
            self.pending_alerts = [QueuedAlert.from_dict(data) 
                                 for data in state.get('pending_alerts', [])]
            
            # Load sent alerts
            self.sent_alerts = [QueuedAlert.from_dict(data) 
                              for data in state.get('sent_alerts', [])]
            
            # Load dedup cache
            dedup_data = state.get('dedup_cache', {})
            self.dedup_cache = {h: datetime.fromisoformat(ts) 
                              for h, ts in dedup_data.items()}
            
        except Exception as e:
            print(f"Error loading queue state: {e}")
    
    def add_alert(self, alert_data: Dict[str, Any]) -> bool:
        """
        Add an alert to the queue.
        
        Returns True if added, False if rejected (duplicate or rate limit).
        """
        # Check for duplicates
        if self._is_duplicate(alert_data):
            return False
        
        # Generate unique ID
        alert_id = alert_data.get('id', f"alert_{int(datetime.now().timestamp())}")
        
        # Determine priority
        priority = self._determine_priority(alert_data)
        
        # Create queued alert
        queued_alert = QueuedAlert(
            id=alert_id,
            alert_data=alert_data,
            priority=priority,
            created_at=datetime.now()
        )
        
        # Add to queue (insert in priority order)
        self.pending_alerts.append(queued_alert)
        self.pending_alerts.sort(key=lambda x: (x.priority.value, x.created_at), reverse=True)
        
        # Update dedup cache
        content_hash = self._generate_alert_hash(alert_data)
        self.dedup_cache[content_hash] = datetime.now()
        
        # Cleanup old entries
        self._cleanup_old_entries()
        
        # Save state
        self._save_queue_state()
        
        return True
    
    def get_next_alert(self) -> Optional[QueuedAlert]:
        """Get the next alert to send (respecting rate limits)."""
        if not self.pending_alerts:
            return None
        
        # Check rate limit
        if not self._check_rate_limit():
            return None
        
        # Get highest priority alert
        return self.pending_alerts[0]
    
    def mark_sent(self, alert_id: str) -> bool:
        """Mark an alert as sent."""
        for i, alert in enumerate(self.pending_alerts):
            if alert.id == alert_id:
                # Remove from pending
                alert = self.pending_alerts.pop(i)
                
                # Mark as sent and move to sent list
                alert.sent_at = datetime.now()
                self.sent_alerts.append(alert)
                
                # Save state
                self._save_queue_state()
                
                return True
        
        return False
    
    def mark_failed(self, alert_id: str) -> bool:
        """Mark an alert as failed (for retry logic)."""
        for alert in self.pending_alerts:
            if alert.id == alert_id:
                alert.retry_count += 1
                
                # Remove if max retries exceeded
                if alert.retry_count >= alert.max_retries:
                    self.pending_alerts.remove(alert)
                    # Could move to a failed alerts list here
                
                # Save state
                self._save_queue_state()
                
                return True
        
        return False
    
    def get_pending_alerts(self) -> List[Dict[str, Any]]:
        """Get all pending alerts."""
        return [alert.alert_data for alert in self.pending_alerts]
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        one_day_ago = now - timedelta(days=1)
        
        recent_sent = [alert for alert in self.sent_alerts 
                      if alert.sent_at and alert.sent_at > one_hour_ago]
        
        daily_sent = [alert for alert in self.sent_alerts 
                     if alert.sent_at and alert.sent_at > one_day_ago]
        
        priority_counts = {}
        for priority in AlertPriority:
            priority_counts[priority.name] = len([alert for alert in self.pending_alerts 
                                                 if alert.priority == priority])
        
        return {
            'pending_count': len(self.pending_alerts),
            'sent_last_hour': len(recent_sent),
            'sent_last_24h': len(daily_sent),
            'total_sent': len(self.sent_alerts),
            'rate_limit_status': {
                'max_per_hour': self.max_alerts_per_hour,
                'sent_this_hour': len(recent_sent),
                'remaining_this_hour': max(0, self.max_alerts_per_hour - len(recent_sent)),
                'can_send_now': self._check_rate_limit()
            },
            'priority_breakdown': priority_counts,
            'dedup_cache_size': len(self.dedup_cache),
            'oldest_pending': min([alert.created_at for alert in self.pending_alerts]).isoformat() if self.pending_alerts else None
        }
    
    def clear_queue(self):
        """Clear all pending alerts (for testing/maintenance)."""
        self.pending_alerts.clear()
        self._save_queue_state()
    
    def set_rate_limit(self, max_per_hour: int):
        """Update rate limit."""
        self.max_alerts_per_hour = max_per_hour