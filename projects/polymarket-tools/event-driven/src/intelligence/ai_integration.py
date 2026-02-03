"""
AI Integration module - connects AI analysis with the main event flow.
This module processes events after basic filtering and queues AI-analyzed decisions.
"""
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
from ..models import Event, Signal
from .ai_analyzer import AIEventAnalyzer, AIAnalysis, TradingRecommendation
from .decision_queue import DecisionQueue

logger = logging.getLogger(__name__)


class AIIntegrationService:
    """Integrates AI analysis into the main event processing flow."""
    
    def __init__(self, data_dir: str = "data", model: str = "anthropic/claude-haiku-4"):
        """
        Initialize the AI integration service.
        
        Args:
            data_dir: Directory for storing decision queue data
            model: LLM model to use for analysis
        """
        self.analyzer = AIEventAnalyzer(model=model)
        self.decision_queue = DecisionQueue(data_dir=data_dir)
        
        # Minimum thresholds for AI analysis (cost optimization)
        self.min_urgency_score = 4.0
        self.min_significance_for_analysis = 3
        
        # Market data cache (would be populated by market fetchers)
        self.market_prices = {}
        
    def process_event(self, event: Event, market_prices: Optional[Dict[str, float]] = None) -> Optional[str]:
        """
        Process an event through AI analysis and queue for decision if promising.
        
        Args:
            event: The event to process
            market_prices: Current market prices (optional)
            
        Returns:
            Decision ID if queued, None if not processed
        """
        # Use provided market prices or cached ones
        current_prices = market_prices or self.market_prices.copy()
        
        try:
            # Check if event passes basic filtering for AI analysis
            if not self._should_analyze_event(event):
                logger.debug(f"Event {event.id} does not meet criteria for AI analysis")
                return None
            
            logger.info(f"Starting AI analysis for event {event.id}: {event.title[:100]}...")
            
            # Get AI analysis
            ai_analysis = self.analyzer.analyze_event(event)
            
            # Check if analysis suggests potential trading opportunity
            if not self._analysis_suggests_trading(ai_analysis):
                logger.info(f"AI analysis for event {event.id} does not suggest trading opportunity")
                return None
            
            # Get trading recommendation
            trading_rec = self.analyzer.get_trading_recommendation(event, current_prices)
            
            # Queue for main agent decision if recommendation is actionable
            if self._should_queue_for_decision(trading_rec, ai_analysis):
                decision = self.decision_queue.add_decision(
                    event=event,
                    ai_analysis=ai_analysis,
                    trading_recommendation=trading_rec,
                    market_data=current_prices
                )
                
                logger.info(f"Queued decision {decision.id} for main agent review")
                return decision.id
            else:
                logger.info(f"Trading recommendation for event {event.id} not actionable enough to queue")
                return None
                
        except Exception as e:
            logger.error(f"Error processing event {event.id} through AI analysis: {e}")
            return None
    
    def get_pending_decisions_summary(self, max_decisions: int = 5) -> str:
        """
        Get a formatted summary of pending decisions for main agent review.
        
        Args:
            max_decisions: Maximum number of decisions to include
            
        Returns:
            Formatted string summary
        """
        decisions = self.decision_queue.get_pending_decisions(max_count=max_decisions)
        
        if not decisions:
            return "📭 No pending AI analysis decisions."
        
        summary_lines = [f"📋 {len(decisions)} pending AI analysis decisions:\n"]
        
        for i, decision in enumerate(decisions, 1):
            age_minutes = (datetime.now() - decision.created_at).total_seconds() / 60
            summary_lines.append(
                f"{i}. [{decision.priority}/10] {decision.event.title[:60]}..."
                f"\n   📊 {decision.ai_analysis.sentiment} | "
                f"Rec: {decision.trading_recommendation.should_trade} | "
                f"Age: {age_minutes:.0f}m\n"
            )
        
        return "".join(summary_lines)
    
    def get_decision_for_review(self, decision_id: str) -> Optional[str]:
        """
        Get a specific decision formatted for review.
        
        Args:
            decision_id: ID of the decision to retrieve
            
        Returns:
            Formatted decision for review, or None if not found
        """
        decisions = self.decision_queue.get_pending_decisions()
        
        for decision in decisions:
            if decision.id == decision_id:
                return decision.format_for_review()
        
        return None
    
    def mark_decision_processed(self, decision_id: str, action: str, notes: str = "") -> bool:
        """
        Mark a decision as processed by the main agent.
        
        Args:
            decision_id: ID of the decision
            action: Action taken (TRADED, PASSED, IGNORED)
            notes: Additional notes
            
        Returns:
            True if successfully marked as processed
        """
        return self.decision_queue.mark_processed(decision_id, action, notes)
    
    def update_market_prices(self, prices: Dict[str, float]):
        """Update cached market prices."""
        self.market_prices.update(prices)
        logger.debug(f"Updated market prices for {len(prices)} markets")
    
    def cleanup_expired_decisions(self) -> int:
        """Clean up expired decisions and return count removed."""
        return self.decision_queue.clean_expired()
    
    def _should_analyze_event(self, event: Event) -> bool:
        """
        Determine if an event should be analyzed by AI.
        Cost optimization - only analyze promising events.
        """
        # Check minimum urgency score
        if event.urgency_score < self.min_urgency_score:
            return False
        
        # Check if it's from a reliable source
        if event.source_tier == "tier3_general" and event.urgency_score < 7:
            return False
        
        # Check if it has relevant keywords
        if not event.keywords_matched:
            return False
        
        # Don't re-analyze duplicates
        if event.is_duplicate:
            return False
        
        # Check category relevance
        relevant_categories = {"fed", "crypto", "politics", "economy", "markets"}
        if event.category not in relevant_categories:
            return False
        
        return True
    
    def _analysis_suggests_trading(self, analysis: AIAnalysis) -> bool:
        """
        Check if AI analysis suggests a potential trading opportunity.
        """
        # Minimum significance threshold
        if analysis.significance < self.min_significance_for_analysis:
            return False
        
        # Minimum confidence threshold
        if analysis.confidence < 0.4:
            return False
        
        # Must have affected markets
        if not analysis.affected_markets:
            return False
        
        # Neutral sentiment with low significance is probably not actionable
        if analysis.sentiment == "NEUTRAL" and analysis.significance < 6:
            return False
        
        return True
    
    def _should_queue_for_decision(self, trading_rec: TradingRecommendation, 
                                  analysis: AIAnalysis) -> bool:
        """
        Determine if a trading recommendation should be queued for main agent review.
        """
        # Only queue if AI recommends YES or strong MAYBE
        if trading_rec.should_trade == "NO":
            return False
        
        if trading_rec.should_trade == "MAYBE" and trading_rec.confidence < 0.5:
            return False
        
        # Must have reasonable confidence
        if trading_rec.confidence < 0.3:
            return False
        
        # For high-confidence YES recommendations, always queue
        if trading_rec.should_trade == "YES" and trading_rec.confidence >= 0.6:
            return True
        
        # For other cases, check combined analysis quality
        combined_score = (analysis.confidence + trading_rec.confidence) / 2
        if combined_score >= 0.5 and analysis.significance >= 5:
            return True
        
        return False


def create_ai_integration() -> AIIntegrationService:
    """Factory function to create AI integration service with default settings."""
    return AIIntegrationService(
        data_dir="data",
        model="anthropic/claude-haiku-4"
    )