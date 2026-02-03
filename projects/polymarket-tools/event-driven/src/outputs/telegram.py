"""
Telegram alert formatting and rate limiting.

This module handles formatting of alerts for Telegram notifications,
including rate limiting, deduplication, and prioritization features.
"""
import json
import hashlib
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from pathlib import Path

try:
    from ..models import Event, Signal, Alert
except ImportError:
    # Fallback for standalone usage
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from models import Event, Signal, Alert


class TelegramAlertManager:
    """Manages Telegram alerts with rate limiting, deduplication, and prioritization."""
    
    def __init__(self, 
                 max_alerts_per_hour: int = 10,
                 state_file: Optional[str] = "data/telegram_state.json"):
        self.max_alerts_per_hour = max_alerts_per_hour
        self.state_file = Path(state_file) if state_file else None
        self.state = self._load_state()
    
    def _load_state(self) -> Dict[str, Any]:
        """Load alert state from disk."""
        if self.state_file and self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        
        return {
            "sent_alerts": [],  # Recent sent alert hashes
            "alert_history": [],  # Alert timestamps for rate limiting
            "last_cleanup": datetime.now().isoformat()
        }
    
    def _save_state(self):
        """Save alert state to disk."""
        if self.state_file:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
    
    def _cleanup_old_data(self):
        """Remove old entries from state to prevent unbounded growth."""
        now = datetime.now()
        cutoff = now - timedelta(hours=24)
        
        # Remove old alert hashes (keep 24h for dedup)
        self.state["sent_alerts"] = [
            entry for entry in self.state["sent_alerts"]
            if datetime.fromisoformat(entry["timestamp"]) > cutoff
        ]
        
        # Remove old alert timestamps (keep 1h for rate limiting)
        rate_limit_cutoff = now - timedelta(hours=1)
        self.state["alert_history"] = [
            timestamp for timestamp in self.state["alert_history"]
            if datetime.fromisoformat(timestamp) > rate_limit_cutoff
        ]
        
        self.state["last_cleanup"] = now.isoformat()
        self._save_state()
    
    def _get_alert_hash(self, event: Event, signals: List[Signal]) -> str:
        """Generate unique hash for alert deduplication."""
        # Create hash based on event ID and signal market IDs
        content = f"{event.id}:{sorted([s.market_id for s in signals])}"
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    def _is_rate_limited(self) -> bool:
        """Check if rate limit is exceeded."""
        now = datetime.now()
        cutoff = now - timedelta(hours=1)
        
        # Count alerts in last hour
        recent_alerts = [
            timestamp for timestamp in self.state["alert_history"]
            if datetime.fromisoformat(timestamp) > cutoff
        ]
        
        return len(recent_alerts) >= self.max_alerts_per_hour
    
    def _is_duplicate(self, event: Event, signals: List[Signal]) -> bool:
        """Check if alert is a duplicate."""
        alert_hash = self._get_alert_hash(event, signals)
        
        return any(
            entry["hash"] == alert_hash 
            for entry in self.state["sent_alerts"]
        )
    
    def _calculate_priority(self, event: Event, signals: List[Signal]) -> int:
        """Calculate alert priority (1-10, 10 = highest)."""
        base_priority = int(event.urgency_score)
        
        # Boost priority based on signal confidence
        if signals:
            avg_confidence = sum(s.confidence for s in signals) / len(signals)
            if avg_confidence >= 0.8:
                base_priority += 2
            elif avg_confidence >= 0.6:
                base_priority += 1
        
        # Boost for multiple strong signals
        strong_signals = [s for s in signals if s.confidence >= 0.7]
        if len(strong_signals) >= 3:
            base_priority += 1
        
        # Boost for high-value trades
        max_expected_return = max(
            [abs((s.expected_price - s.current_price) / s.current_price) for s in signals],
            default=0
        )
        if max_expected_return >= 0.2:  # 20%+ expected return
            base_priority += 1
        
        return min(max(base_priority, 1), 10)
    
    def _get_age_minutes(self, event: Event) -> int:
        """Calculate event age in minutes."""
        now = datetime.now()
        if event.timestamp.tzinfo:
            # Make now timezone-aware to match event.timestamp
            from datetime import timezone
            now = now.replace(tzinfo=timezone.utc)
        
        age = now - event.timestamp
        return int(age.total_seconds() / 60)
    
    def can_send_alert(self, event: Event, signals: List[Signal]) -> bool:
        """Check if alert can be sent (not rate limited or duplicate)."""
        self._cleanup_old_data()
        
        if self._is_rate_limited():
            return False
        
        if self._is_duplicate(event, signals):
            return False
        
        return True
    
    def format_alert(self, event: Event, signals: List[Signal]) -> str:
        """Format alert for Telegram notification."""
        # Determine emoji based on urgency score
        score = int(event.urgency_score)
        if score <= 3:
            emoji = "🟢"  # Low priority
        elif score <= 6:
            emoji = "🟡"  # Medium priority
        elif score <= 8:
            emoji = "🟠"  # High priority
        else:
            emoji = "🔴"  # Critical priority
        
        # Calculate age in minutes
        age_minutes = self._get_age_minutes(event)
        
        # Format basic alert
        msg = f"""
{emoji} **{event.category}** (Score: {event.urgency_score:.1f}/10)

📰 {event.title}

🔗 {event.url or 'No URL'}

⏰ {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')} ({age_minutes}m ago)
📡 Source: {event.source}
"""
        
        # Add signal information if available
        if signals:
            msg += "\n**Affected Markets:**\n"
            for signal in signals:
                # Determine direction arrow
                if signal.direction == "BUY_YES":
                    arrow = "📈"
                elif signal.direction == "BUY_NO":
                    arrow = "📉"
                else:  # HOLD
                    arrow = "➖"
                
                # Format signal info
                msg += f"{arrow} {signal.market_id}: {signal.direction} (conf: {signal.confidence:.0%})\n"
                msg += f"   Current: {signal.current_price:.0%} → Expected: {signal.expected_price:.0%}\n"
                
                # Add reasoning if available and significant
                if signal.reasoning and signal.confidence >= 0.7:
                    # Truncate reasoning to keep message concise
                    reasoning = signal.reasoning[:100] + "..." if len(signal.reasoning) > 100 else signal.reasoning
                    msg += f"   💭 {reasoning}\n"
        
        return msg.strip()
    
    def record_sent_alert(self, event: Event, signals: List[Signal]):
        """Record that an alert was sent."""
        now = datetime.now()
        alert_hash = self._get_alert_hash(event, signals)
        
        # Add to sent alerts for deduplication
        self.state["sent_alerts"].append({
            "hash": alert_hash,
            "timestamp": now.isoformat(),
            "event_id": event.id,
            "priority": self._calculate_priority(event, signals)
        })
        
        # Add to rate limiting history
        self.state["alert_history"].append(now.isoformat())
        
        self._save_state()
    
    def get_pending_alerts_sorted(self, alerts: List[tuple]) -> List[tuple]:
        """Sort alerts by priority (highest first) for processing."""
        def get_priority(alert_tuple):
            event, signals = alert_tuple
            return self._calculate_priority(event, signals)
        
        return sorted(alerts, key=get_priority, reverse=True)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current alert manager statistics."""
        now = datetime.now()
        cutoff = now - timedelta(hours=1)
        
        recent_count = len([
            timestamp for timestamp in self.state["alert_history"]
            if datetime.fromisoformat(timestamp) > cutoff
        ])
        
        return {
            "alerts_sent_last_hour": recent_count,
            "rate_limit": self.max_alerts_per_hour,
            "rate_limited": self._is_rate_limited(),
            "total_unique_alerts": len(self.state["sent_alerts"]),
            "last_cleanup": self.state["last_cleanup"]
        }


def format_alert(event: Event, signals: List[Signal]) -> str:
    """
    Simple formatting function for backward compatibility.
    
    This function provides the basic alert formatting without 
    the full alert management features.
    """
    manager = TelegramAlertManager()
    return manager.format_alert(event, signals)


def create_alert_manager(max_alerts_per_hour: int = 10, 
                        state_file: Optional[str] = "data/telegram_state.json") -> TelegramAlertManager:
    """Create a new TelegramAlertManager instance."""
    return TelegramAlertManager(
        max_alerts_per_hour=max_alerts_per_hour,
        state_file=state_file
    )