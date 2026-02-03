"""
Decision queue system for AI-analyzed events.
Queues events and recommendations for main agent (Helmet) review.
"""
import json
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Dict, Any
from ..models import Event, Signal
from .ai_analyzer import AIAnalysis, TradingRecommendation

logger = logging.getLogger(__name__)


@dataclass
class PendingDecision:
    """A pending decision that needs main agent review."""
    id: str
    event: Event
    ai_analysis: AIAnalysis
    trading_recommendation: TradingRecommendation
    market_data: Dict[str, float]  # current market prices
    created_at: datetime
    priority: int  # 1-10 scale
    expires_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'event': self.event.to_dict(),
            'ai_analysis': self.ai_analysis.to_dict(),
            'trading_recommendation': self.trading_recommendation.to_dict(),
            'market_data': self.market_data,
            'created_at': self.created_at.isoformat(),
            'priority': self.priority,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PendingDecision':
        """Create PendingDecision from dictionary."""
        from ..models import Event
        
        return cls(
            id=data['id'],
            event=Event.from_dict(data['event']),
            ai_analysis=AIAnalysis(**{
                k: datetime.fromisoformat(v) if k == 'timestamp' and isinstance(v, str) else v
                for k, v in data['ai_analysis'].items()
            }),
            trading_recommendation=TradingRecommendation(**{
                k: datetime.fromisoformat(v) if k == 'timestamp' and isinstance(v, str) else v
                for k, v in data['trading_recommendation'].items()
            }),
            market_data=data['market_data'],
            created_at=datetime.fromisoformat(data['created_at']),
            priority=data['priority'],
            expires_at=datetime.fromisoformat(data['expires_at']) if data.get('expires_at') else None
        )
    
    def format_for_review(self) -> str:
        """Format the decision for main agent review."""
        age_minutes = (datetime.now() - self.created_at).total_seconds() / 60
        
        # Format market data
        market_info = ""
        if self.market_data:
            market_info = "\n".join([
                f"  • {market}: ${price:.2f}" 
                for market, price in self.market_data.items()
            ])
        
        # Calculate potential return
        rec = self.trading_recommendation
        return_info = ""
        if rec.current_price and rec.target_price:
            return_pct = ((rec.target_price - rec.current_price) / rec.current_price) * 100
            return_info = f" → potential {return_pct:+.1f}% gain"
        
        return f"""🔔 EVENT ANALYSIS REQUEST

📰 Event: "{self.event.title}"
📡 Source: {self.event.source} ({self.event.source_tier})
⏰ Age: {age_minutes:.0f} minutes

🤖 AI Analysis:
• Sentiment: {self.ai_analysis.sentiment} for {', '.join(self.ai_analysis.affected_markets)}
• Significance: {self.ai_analysis.significance}/10
• Expected impact: {self.ai_analysis.expected_impact}
• Confidence: {self.ai_analysis.confidence:.0%}
• Reasoning: "{self.ai_analysis.reasoning}"

💰 Current Markets:
{market_info}

🎯 AI Recommendation:
• Action: {rec.should_trade}
• Market: {rec.market_id or 'None specified'}
• Direction: {rec.direction or 'N/A'}
• Size: {rec.position_size or 'N/A'}
• Target: ${rec.target_price:.2f} (from ${rec.current_price:.2f}){return_info}
• Confidence: {rec.confidence:.0%}
• Urgency: {rec.urgency}/10
• Reasoning: "{rec.reasoning}"

❓ DECISION NEEDED: Trade or pass?"""


class DecisionQueue:
    """Manages the queue of pending decisions for main agent review."""
    
    def __init__(self, data_dir: str = "data"):
        """
        Initialize the decision queue.
        
        Args:
            data_dir: Directory to store pending decisions
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.queue_file = self.data_dir / "pending_decisions.jsonl"
        self.processed_file = self.data_dir / "processed_decisions.jsonl"
        
    def add_decision(self, event: Event, ai_analysis: AIAnalysis, 
                    trading_recommendation: TradingRecommendation, 
                    market_data: Dict[str, float]) -> PendingDecision:
        """
        Add a new decision to the queue.
        
        Args:
            event: The event that triggered analysis
            ai_analysis: AI analysis results  
            trading_recommendation: Trading recommendation
            market_data: Current market prices
            
        Returns:
            PendingDecision object that was added
        """
        # Generate decision ID
        decision_id = f"decision_{event.id}_{int(datetime.now().timestamp())}"
        
        # Calculate priority based on AI analysis
        priority = self._calculate_priority(ai_analysis, trading_recommendation)
        
        # Set expiration (decisions expire after some time)
        expires_at = None
        if trading_recommendation.urgency >= 7:
            expires_at = datetime.now() + timedelta(hours=1)
        elif trading_recommendation.urgency >= 4:
            expires_at = datetime.now() + timedelta(hours=6)
        else:
            expires_at = datetime.now() + timedelta(days=1)
        
        decision = PendingDecision(
            id=decision_id,
            event=event,
            ai_analysis=ai_analysis,
            trading_recommendation=trading_recommendation,
            market_data=market_data,
            created_at=datetime.now(),
            priority=priority,
            expires_at=expires_at
        )
        
        # Write to queue file
        self._write_to_queue(decision)
        
        logger.info(f"Added decision {decision_id} to queue with priority {priority}")
        return decision
    
    def get_pending_decisions(self, max_count: Optional[int] = None) -> List[PendingDecision]:
        """
        Get all pending decisions, sorted by priority and age.
        
        Args:
            max_count: Maximum number of decisions to return
            
        Returns:
            List of pending decisions
        """
        if not self.queue_file.exists():
            return []
        
        decisions = []
        try:
            with open(self.queue_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            decision = PendingDecision.from_dict(data)
                            
                            # Skip expired decisions
                            if decision.expires_at and datetime.now() > decision.expires_at:
                                logger.info(f"Skipping expired decision {decision.id}")
                                continue
                                
                            decisions.append(decision)
                        except Exception as e:
                            logger.error(f"Error parsing decision line: {e}")
                            continue
                            
        except Exception as e:
            logger.error(f"Error reading queue file: {e}")
            return []
        
        # Sort by priority (desc) then by age (desc = newest first)
        decisions.sort(key=lambda d: (-d.priority, -d.created_at.timestamp()))
        
        if max_count:
            decisions = decisions[:max_count]
            
        return decisions
    
    def mark_processed(self, decision_id: str, action_taken: str, notes: str = "") -> bool:
        """
        Mark a decision as processed and move it to processed file.
        
        Args:
            decision_id: ID of the decision to mark as processed
            action_taken: What action was taken (e.g., "TRADED", "PASSED", "IGNORED")
            notes: Additional notes about the decision
            
        Returns:
            True if decision was found and processed
        """
        if not self.queue_file.exists():
            return False
        
        decisions = []
        processed_decision = None
        
        # Read all decisions, find the one to process
        try:
            with open(self.queue_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        data = json.loads(line)
                        if data['id'] == decision_id:
                            processed_decision = data
                        else:
                            decisions.append(data)
        except Exception as e:
            logger.error(f"Error processing decision {decision_id}: {e}")
            return False
        
        if not processed_decision:
            return False
        
        # Write remaining decisions back to queue file
        with open(self.queue_file, 'w') as f:
            for decision in decisions:
                f.write(json.dumps(decision) + '\n')
        
        # Add processed info and write to processed file
        processed_decision['processed_at'] = datetime.now().isoformat()
        processed_decision['action_taken'] = action_taken
        processed_decision['notes'] = notes
        
        with open(self.processed_file, 'a') as f:
            f.write(json.dumps(processed_decision) + '\n')
        
        logger.info(f"Marked decision {decision_id} as processed with action: {action_taken}")
        return True
    
    def clean_expired(self) -> int:
        """
        Remove expired decisions from the queue.
        
        Returns:
            Number of decisions removed
        """
        if not self.queue_file.exists():
            return 0
        
        valid_decisions = []
        expired_count = 0
        
        try:
            with open(self.queue_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            decision = PendingDecision.from_dict(data)
                            
                            if decision.expires_at and datetime.now() > decision.expires_at:
                                expired_count += 1
                                logger.info(f"Removing expired decision {decision.id}")
                            else:
                                valid_decisions.append(data)
                        except Exception as e:
                            logger.error(f"Error processing decision for cleanup: {e}")
                            continue
            
            # Write back only valid decisions
            with open(self.queue_file, 'w') as f:
                for decision in valid_decisions:
                    f.write(json.dumps(decision) + '\n')
                    
        except Exception as e:
            logger.error(f"Error cleaning expired decisions: {e}")
            return 0
        
        logger.info(f"Cleaned {expired_count} expired decisions")
        return expired_count
    
    def _write_to_queue(self, decision: PendingDecision):
        """Write decision to the queue file."""
        with open(self.queue_file, 'a') as f:
            f.write(json.dumps(decision.to_dict()) + '\n')
    
    def _calculate_priority(self, ai_analysis: AIAnalysis, trading_rec: TradingRecommendation) -> int:
        """Calculate priority score for a decision (1-10 scale)."""
        priority = 5  # base priority
        
        # Boost for high significance
        if ai_analysis.significance >= 8:
            priority += 2
        elif ai_analysis.significance >= 6:
            priority += 1
        
        # Boost for high confidence
        if ai_analysis.confidence >= 0.8:
            priority += 1
        elif ai_analysis.confidence >= 0.6:
            priority += 0.5
        
        # Boost for trading recommendations
        if trading_rec.should_trade == "YES":
            priority += 2
            if trading_rec.confidence >= 0.7:
                priority += 1
        elif trading_rec.should_trade == "MAYBE":
            priority += 1
        
        # Boost for urgency
        if trading_rec.urgency >= 8:
            priority += 1
        
        # Cap at 10
        return min(10, int(priority))