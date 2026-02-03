"""
Backtesting simulator that runs events through the trading pipeline.
"""
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.models import Event, Signal
from src.intelligence.signals import process_event_to_signals
from src.fetchers.polymarket import MarketPrice


@dataclass
class TradingResult:
    """Result of a simulated trade."""
    signal: Signal
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    return_pct: float
    win: bool
    
    def to_dict(self) -> Dict:
        return {
            'market_id': self.signal.market_id,
            'direction': self.signal.direction,
            'confidence': self.signal.confidence,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'entry_time': self.entry_time.isoformat(),
            'exit_time': self.exit_time.isoformat(),
            'return_pct': self.return_pct,
            'win': self.win,
            'reasoning': self.signal.reasoning
        }


class BacktestSimulator:
    """Simulates the trading system with historical data."""
    
    def __init__(self, holding_period_hours: int = 24):
        """
        Initialize simulator.
        
        Args:
            holding_period_hours: How long to hold positions before exiting
        """
        self.holding_period = timedelta(hours=holding_period_hours)
        self.results: List[TradingResult] = []
        
    async def simulate_signal(self, signal: Signal, market_prices: List[MarketPrice]) -> Optional[TradingResult]:
        """
        Simulate trading a single signal.
        
        Args:
            signal: Generated trading signal
            market_prices: Historical price data for the market
            
        Returns:
            TradingResult or None if simulation fails
        """
        if signal.direction == "HOLD":
            return None  # Skip HOLD signals
        
        # Find entry price at signal time
        entry_price = signal.current_price
        entry_time = signal.timestamp
        
        # Calculate exit time
        exit_time = entry_time + self.holding_period
        
        # Find exit price
        exit_price = self._find_price_at_time(market_prices, exit_time)
        if exit_price is None:
            # Use last available price if exact time not found
            exit_price = market_prices[-1].yes_price
            exit_time = market_prices[-1].last_updated
        
        # Calculate return based on signal direction
        if signal.direction == "BUY_YES":
            # Profit if price goes up
            return_pct = (exit_price - entry_price) / entry_price
        elif signal.direction == "BUY_NO":
            # Profit if price goes down (buy NO tokens)
            # NO price moves inverse to YES price
            entry_no_price = 1.0 - entry_price
            exit_no_price = 1.0 - exit_price
            return_pct = (exit_no_price - entry_no_price) / entry_no_price
        else:
            return None
        
        # Determine if it's a win (positive return)
        win = return_pct > 0
        
        return TradingResult(
            signal=signal,
            entry_price=entry_price,
            exit_price=exit_price,
            entry_time=entry_time,
            exit_time=exit_time,
            return_pct=return_pct,
            win=win
        )
    
    def _find_price_at_time(self, prices: List[MarketPrice], target_time: datetime) -> Optional[float]:
        """Find market price closest to target time."""
        if not prices:
            return None
        
        # Find closest price by time
        closest_price = min(prices, key=lambda p: abs((p.last_updated - target_time).total_seconds()))
        
        # Only return if within reasonable time window (6 hours)
        if abs((closest_price.last_updated - target_time).total_seconds()) <= 6 * 3600:
            return closest_price.yes_price
        
        return None
    
    async def run_backtest(self, events: List[Event], 
                          market_prices: Dict[str, List[MarketPrice]]) -> List[TradingResult]:
        """
        Run complete backtest on historical data.
        
        Args:
            events: Historical events
            market_prices: Historical market prices by market_id
            
        Returns:
            List of trading results
        """
        self.results = []
        
        print(f"🧪 Starting backtest with {len(events)} events...")
        
        processed_events = 0
        signals_generated = 0
        
        for event in events:
            try:
                # Process event through the pipeline to generate signals
                signals = await process_event_to_signals(event)
                
                for signal in signals:
                    if signal.market_id not in market_prices:
                        continue  # Skip if no price data available
                    
                    signals_generated += 1
                    
                    # Simulate trading the signal
                    result = await self.simulate_signal(signal, market_prices[signal.market_id])
                    
                    if result:
                        self.results.append(result)
                        
                        # Progress indicator
                        if len(self.results) % 10 == 0:
                            print(f"📊 Processed {len(self.results)} trades...")
                
                processed_events += 1
                
                # Progress for events
                if processed_events % 20 == 0:
                    print(f"📅 Processed {processed_events}/{len(events)} events...")
                    
            except Exception as e:
                print(f"❌ Error processing event {event.id}: {e}")
                continue
        
        print(f"✅ Backtest complete! Processed {processed_events} events, "
              f"generated {signals_generated} signals, executed {len(self.results)} trades")
        
        return self.results
    
    def get_summary_stats(self) -> Dict:
        """Get summary statistics from backtest results."""
        if not self.results:
            return {
                'total_trades': 0,
                'wins': 0,
                'losses': 0,
                'win_rate': 0.0,
                'avg_return': 0.0,
                'total_return': 0.0,
                'best_trade': 0.0,
                'worst_trade': 0.0
            }
        
        wins = sum(1 for r in self.results if r.win)
        losses = len(self.results) - wins
        win_rate = wins / len(self.results)
        
        returns = [r.return_pct for r in self.results]
        avg_return = sum(returns) / len(returns)
        total_return = sum(returns)  # Simplified cumulative return
        
        return {
            'total_trades': len(self.results),
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'avg_return': avg_return,
            'total_return': total_return,
            'best_trade': max(returns) if returns else 0.0,
            'worst_trade': min(returns) if returns else 0.0
        }


class MockPipelineSimulator(BacktestSimulator):
    """Simplified simulator that uses mock pipeline for faster testing."""
    
    def __init__(self, holding_period_hours: int = 24):
        super().__init__(holding_period_hours)
        
        # Simple mock signal generation based on keywords
        self.market_keywords = {
            "mkt_fed_rate_dec_2024": ["fed", "federal reserve", "interest rates", "powell", "fomc"],
            "mkt_bitcoin_100k_2024": ["bitcoin", "btc", "crypto", "cryptocurrency"],
            "mkt_trump_president_2024": ["trump", "election", "president", "republican"],
            "mkt_nvidia_split_2024": ["nvidia", "nvda", "stock split", "shares"],
            "mkt_recession_q1_2024": ["recession", "gdp", "economy", "unemployment"]
        }
    
    def _generate_mock_signal(self, event: Event, market_id: str, current_price: float) -> Optional[Signal]:
        """Generate a mock signal based on simple keyword matching."""
        
        # Check if event is relevant to this market
        market_keywords = self.market_keywords.get(market_id, [])
        event_text = f"{event.title} {event.content}".lower()
        
        matches = sum(1 for keyword in market_keywords if keyword in event_text)
        
        if matches == 0:
            return None  # Not relevant
        
        # Simple sentiment analysis
        bullish_words = ["surge", "rally", "positive", "growth", "increase", "up", "wins", "success"]
        bearish_words = ["crash", "decline", "negative", "drop", "down", "losses", "failure", "concern"]
        
        bullish_score = sum(1 for word in bullish_words if word in event_text)
        bearish_score = sum(1 for word in bearish_words if word in event_text)
        
        # Determine direction
        if bullish_score > bearish_score:
            direction = "BUY_YES"
            expected_move = 0.05  # 5% up
        elif bearish_score > bullish_score:
            direction = "BUY_NO" 
            expected_move = -0.05  # 5% down
        else:
            direction = "HOLD"
            expected_move = 0.0
        
        if direction == "HOLD":
            return None
        
        # Calculate confidence based on matches and urgency
        confidence = min(0.9, 0.3 + (matches * 0.2) + (event.urgency_score / 20))
        
        return Signal(
            market_id=market_id,
            direction=direction,
            confidence=confidence,
            reasoning=f"Mock signal: {matches} keyword matches, urgency {event.urgency_score}",
            current_price=current_price,
            expected_price=current_price + expected_move,
            event_id=event.id,
            timestamp=event.timestamp
        )
    
    async def run_backtest(self, events: List[Event], 
                          market_prices: Dict[str, List[MarketPrice]]) -> List[TradingResult]:
        """Run backtest with mock signal generation."""
        self.results = []
        
        print(f"🎲 Starting mock backtest with {len(events)} events...")
        
        for event in events:
            for market_id, prices in market_prices.items():
                # Find current price at event time
                current_price_data = self._find_price_at_time(prices, event.timestamp)
                if current_price_data is None:
                    continue
                
                # Generate mock signal
                signal = self._generate_mock_signal(event, market_id, current_price_data)
                if signal is None:
                    continue
                
                # Simulate the trade
                result = await self.simulate_signal(signal, prices)
                if result:
                    self.results.append(result)
        
        print(f"✅ Mock backtest complete! Executed {len(self.results)} trades")
        return self.results