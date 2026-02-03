"""
Autonomous Trading Decision Engine
=================================

Makes intelligent trading decisions based on signals and portfolio state.
Implements risk management rules and position sizing.
"""
import sys
import os
from dataclasses import dataclass
from typing import Optional, Dict
from datetime import datetime
import math

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.models import Signal
from .portfolio import PaperPortfolio, TradeRecord


@dataclass
class TradingDecision:
    """Result of a trading decision evaluation."""
    should_trade: bool
    position_size: float
    reasoning: str
    risk_score: float
    expected_return: float
    signal: Signal
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            'should_trade': self.should_trade,
            'position_size': self.position_size,
            'reasoning': self.reasoning,
            'risk_score': self.risk_score,
            'expected_return': self.expected_return,
            'signal': self.signal.to_dict(),
            'timestamp': datetime.now().isoformat()
        }


class TradingDecisionEngine:
    """
    Autonomous trading decision engine that evaluates signals and decides
    whether to execute trades based on confidence, risk, and portfolio constraints.
    
    Trading Rules:
    - Minimum confidence: 60%
    - Minimum expected return: 3%
    - Maximum position size: 10% of portfolio
    - Maximum open positions: 5
    - No duplicate positions in same market
    """
    
    def __init__(
        self,
        min_confidence: float = 0.6,
        min_expected_return: float = 0.03,
        max_position_pct: float = 0.10,
        max_open_positions: int = 5
    ):
        """Initialize trading engine with risk parameters."""
        self.min_confidence = min_confidence
        self.min_expected_return = min_expected_return
        self.max_position_pct = max_position_pct
        self.max_open_positions = max_open_positions
    
    def should_trade(self, signal: Signal, portfolio: PaperPortfolio) -> bool:
        """
        Determine if a signal should trigger a trade.
        
        Args:
            signal: Trading signal to evaluate
            portfolio: Current portfolio state
        
        Returns:
            Boolean decision whether to trade
        """
        # Check confidence threshold
        if signal.confidence < self.min_confidence:
            return False
        
        # Check expected return threshold
        if signal.expected_return < self.min_expected_return:
            return False
        
        # Check if we already have position in this market
        if portfolio.has_position_in_market(signal.market_id):
            return False
        
        # Check open position limit
        if portfolio.open_position_count >= self.max_open_positions:
            return False
        
        # Check if we have sufficient balance
        min_investment = portfolio.get_total_value({}) * 0.01  # Minimum 1% investment
        if portfolio.balance < min_investment:
            return False
        
        return True
    
    def calculate_position_size(self, signal: Signal, portfolio: PaperPortfolio) -> float:
        """
        Calculate position size based on signal strength and risk management.
        
        Uses Kelly Criterion adjusted for confidence and expected return.
        
        Args:
            signal: Trading signal
            portfolio: Current portfolio state
        
        Returns:
            Position size in USD
        """
        total_value = portfolio.get_total_value({})
        
        # Base position size (percentage of portfolio)
        base_size_pct = self.max_position_pct
        
        # Adjust based on confidence (higher confidence = larger position)
        confidence_multiplier = (signal.confidence - self.min_confidence) / (1.0 - self.min_confidence)
        confidence_adjusted_pct = base_size_pct * (0.3 + 0.7 * confidence_multiplier)
        
        # Adjust based on expected return (higher return = larger position, up to a point)
        return_multiplier = min(signal.expected_return / self.min_expected_return, 3.0)
        return_adjusted_pct = confidence_adjusted_pct * (0.5 + 0.5 * (return_multiplier - 1.0) / 2.0)
        
        # Calculate dollar amount
        position_size = total_value * return_adjusted_pct
        
        # Ensure we don't exceed available balance
        position_size = min(position_size, portfolio.balance)
        
        # Minimum position size check
        min_position = total_value * 0.01  # At least 1% of portfolio
        position_size = max(position_size, min_position)
        
        return round(position_size, 2)
    
    def calculate_risk_score(self, signal: Signal, portfolio: PaperPortfolio) -> float:
        """
        Calculate risk score for a trade (0-1, where 1 is highest risk).
        
        Factors:
        - Signal confidence (lower = higher risk)
        - Expected return magnitude (extreme returns = higher risk)
        - Current portfolio concentration
        - Market price (extreme prices = higher risk)
        
        Args:
            signal: Trading signal
            portfolio: Current portfolio state
        
        Returns:
            Risk score between 0 and 1
        """
        # Confidence risk (inverse relationship)
        confidence_risk = (1.0 - signal.confidence) * 0.3
        
        # Price risk (extreme prices are riskier)
        price_risk = 0.0
        if signal.current_price < 0.1 or signal.current_price > 0.9:
            price_risk = 0.2
        elif signal.current_price < 0.2 or signal.current_price > 0.8:
            price_risk = 0.1
        
        # Expected return risk (very high returns are suspicious)
        return_risk = 0.0
        if abs(signal.expected_return) > 0.5:  # More than 50% expected return
            return_risk = 0.3
        elif abs(signal.expected_return) > 0.2:  # More than 20% expected return
            return_risk = 0.1
        
        # Portfolio concentration risk
        concentration_risk = 0.0
        if portfolio.open_position_count >= 4:
            concentration_risk = 0.2
        elif portfolio.open_position_count >= 3:
            concentration_risk = 0.1
        
        # Combine risk factors
        total_risk = confidence_risk + price_risk + return_risk + concentration_risk
        return min(total_risk, 1.0)
    
    def evaluate_signal(self, signal: Signal, portfolio: PaperPortfolio) -> TradingDecision:
        """
        Comprehensive evaluation of a trading signal.
        
        Args:
            signal: Trading signal to evaluate
            portfolio: Current portfolio state
        
        Returns:
            TradingDecision with complete analysis
        """
        should_trade = self.should_trade(signal, portfolio)
        position_size = 0.0
        reasoning_parts = []
        
        # Detailed reasoning
        if signal.confidence < self.min_confidence:
            reasoning_parts.append(f"Low confidence ({signal.confidence:.1%} < {self.min_confidence:.0%})")
        else:
            reasoning_parts.append(f"Good confidence ({signal.confidence:.1%})")
        
        if signal.expected_return < self.min_expected_return:
            reasoning_parts.append(f"Low expected return ({signal.expected_return:.1%} < {self.min_expected_return:.0%})")
        else:
            reasoning_parts.append(f"Good expected return ({signal.expected_return:.1%})")
        
        if portfolio.has_position_in_market(signal.market_id):
            reasoning_parts.append("Already have position in this market")
        
        if portfolio.open_position_count >= self.max_open_positions:
            reasoning_parts.append(f"Max positions reached ({portfolio.open_position_count}/{self.max_open_positions})")
        
        min_investment = portfolio.get_total_value({}) * 0.01
        if portfolio.balance < min_investment:
            reasoning_parts.append("Insufficient balance for minimum investment")
        
        # Calculate position size if we should trade
        if should_trade:
            position_size = self.calculate_position_size(signal, portfolio)
            reasoning_parts.append(f"Position size: ${position_size:.0f}")
        
        risk_score = self.calculate_risk_score(signal, portfolio)
        
        # Final reasoning
        if should_trade:
            reasoning = f"✅ EXECUTE: {', '.join(reasoning_parts)}"
        else:
            reasoning = f"❌ SKIP: {', '.join(reasoning_parts)}"
        
        return TradingDecision(
            should_trade=should_trade,
            position_size=position_size,
            reasoning=reasoning,
            risk_score=risk_score,
            expected_return=signal.expected_return,
            signal=signal
        )
    
    def execute_decision(
        self, 
        decision: TradingDecision, 
        portfolio: PaperPortfolio
    ) -> Optional[TradeRecord]:
        """
        Execute a trading decision by opening a position.
        
        Args:
            decision: Trading decision to execute
            portfolio: Portfolio to modify
        
        Returns:
            None (position opened) or exception if failed
        
        Raises:
            ValueError: If decision cannot be executed
        """
        if not decision.should_trade:
            raise ValueError("Cannot execute decision marked as 'should not trade'")
        
        signal = decision.signal
        
        try:
            position = portfolio.open_position(
                market_id=signal.market_id,
                direction=signal.direction,
                amount=decision.position_size,
                price=signal.current_price,
                signal_id=signal.event_id,  # Use event_id as signal_id
                confidence=signal.confidence
            )
            
            return None  # Position opened successfully
            
        except Exception as e:
            raise ValueError(f"Failed to execute trade: {str(e)}")
    
    def analyze_signal_batch(
        self, 
        signals: list[Signal], 
        portfolio: PaperPortfolio
    ) -> list[TradingDecision]:
        """
        Analyze a batch of signals and return decisions for all.
        
        Args:
            signals: List of signals to analyze
            portfolio: Current portfolio state
        
        Returns:
            List of TradingDecision objects
        """
        decisions = []
        
        # Sort signals by confidence and expected return for prioritization
        sorted_signals = sorted(
            signals,
            key=lambda s: (s.confidence * abs(s.expected_return)),
            reverse=True
        )
        
        # Simulate portfolio changes to account for multiple trades
        simulated_portfolio = PaperPortfolio.from_dict(portfolio.to_dict())
        
        for signal in sorted_signals:
            decision = self.evaluate_signal(signal, simulated_portfolio)
            decisions.append(decision)
            
            # If we would execute this trade, simulate the impact on portfolio
            if decision.should_trade:
                try:
                    self.execute_decision(decision, simulated_portfolio)
                except ValueError:
                    # If we can't execute, mark as shouldn't trade
                    decision.should_trade = False
                    decision.reasoning += " (simulation failed)"
        
        return decisions
    
    def get_portfolio_health_score(self, portfolio: PaperPortfolio, current_prices: Dict[str, float]) -> float:
        """
        Calculate overall portfolio health score (0-1).
        
        Factors:
        - Total return
        - Win rate
        - Position concentration
        - Available balance
        
        Args:
            portfolio: Portfolio to analyze
            current_prices: Current market prices
        
        Returns:
            Health score between 0 and 1
        """
        summary = portfolio.get_pnl_summary(current_prices)
        
        # Return performance score (normalized to 0-1)
        return_score = max(0, min(1, (summary['return_pct'] + 50) / 100))  # -50% to +50% maps to 0-1
        
        # Win rate score
        win_rate_score = summary['win_rate'] / 100 if summary['total_trades'] > 0 else 0.5
        
        # Balance diversification score
        total_value = summary['total_value']
        balance_ratio = summary['balance'] / total_value if total_value > 0 else 1
        balance_score = min(1, balance_ratio * 2)  # Prefer some cash available
        
        # Position concentration score
        position_score = max(0, 1 - (summary['open_positions'] / 5))  # Penalty for too many positions
        
        # Weighted average
        health_score = (
            return_score * 0.4 +
            win_rate_score * 0.3 +
            balance_score * 0.2 +
            position_score * 0.1
        )
        
        return round(health_score, 3)