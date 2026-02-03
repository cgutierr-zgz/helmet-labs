#!/usr/bin/env python3
"""
Active Trading Integration Example
=================================

Example of how to integrate the active trading system into the main
monitoring loop for autonomous position management.

This shows how to:
1. Process new signals  
2. Monitor existing positions
3. Execute exits automatically
4. Generate reports

Use this as a template for production integration.
"""
import sys
import os
from datetime import datetime
from typing import Dict, List

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from src.models import Signal, Event, Alert
from src.trading import (
    PaperPortfolio, 
    TradingDecisionEngine, 
    TradingTracker, 
    ReportGenerator,
    ExitStrategy
)
from src.fetchers.polymarket import fetch_market_prices


class ActiveTradingMonitor:
    """
    Complete active trading monitor that integrates with the event-driven system.
    
    This handles:
    - Signal processing and position opening
    - Active position monitoring and exit execution  
    - Portfolio management and reporting
    - Integration with the main scanning loop
    """
    
    def __init__(self, initial_balance: float = 1000.0):
        """Initialize trading monitor."""
        self.tracker = TradingTracker()
        self.decision_engine = TradingDecisionEngine()
        self.reporter = ReportGenerator(self.tracker)
        
        # Get or create portfolio
        self.portfolio = self.tracker.get_or_create_portfolio(initial_balance)
        
        # Tracking
        self.last_scan_time = datetime.now()
        self.total_signals_processed = 0
        self.total_exits_executed = 0
    
    def process_new_signals(self, signals: List[Signal]) -> Dict:
        """
        Process new trading signals and open positions.
        
        Args:
            signals: List of new signals to evaluate
            
        Returns:
            Dict with processing results
        """
        if not signals:
            return {'new_positions': 0, 'signals_processed': 0}
        
        print(f"\n🔄 Processing {len(signals)} new signals...")
        
        new_positions = 0
        
        for signal in signals:
            # Evaluate signal
            decision = self.decision_engine.evaluate_signal(signal, self.portfolio)
            
            # Log decision
            self.tracker.log_decision(decision)
            
            # Execute if recommended
            if decision.should_trade:
                try:
                    self.decision_engine.execute_decision(decision, self.portfolio)
                    new_positions += 1
                    
                    position = self.portfolio.positions[signal.market_id]
                    print(f"   ✅ Opened {signal.direction} position in {signal.market_id[:30]}...")
                    print(f"      ${decision.position_size:.0f} @ ${signal.current_price:.3f}")
                    
                except Exception as e:
                    print(f"   ❌ Failed to open position: {e}")
            else:
                print(f"   ⏭️  Skipped {signal.market_id[:30]}... - {decision.reasoning}")
        
        self.total_signals_processed += len(signals)
        
        # Save portfolio state
        self.tracker.save_portfolio_state(self.portfolio)
        
        return {
            'new_positions': new_positions,
            'signals_processed': len(signals),
            'open_positions': self.portfolio.open_position_count
        }
    
    def monitor_active_positions(self, current_prices: Dict[str, float] = None) -> Dict:
        """
        Monitor open positions and execute exits based on active trading rules.
        
        Args:
            current_prices: Current market prices (optional, will fetch if None)
            
        Returns:
            Dict with monitoring results
        """
        if not self.portfolio.positions:
            return {'positions_monitored': 0, 'positions_closed': 0}
        
        # Fetch current prices if not provided
        if current_prices is None:
            print(f"📊 Fetching current prices for {len(self.portfolio.positions)} positions...")
            current_prices = {}
            # In a real implementation, you'd fetch from Polymarket API
            # For now, simulate with entry prices (no movement)
            for market_id, position in self.portfolio.positions.items():
                current_prices[market_id] = position.entry_price
        
        print(f"🔍 Monitoring {len(self.portfolio.positions)} active positions...")
        
        # Execute active trading scan
        scan_result = self.decision_engine.scan_and_execute_exits(
            self.portfolio, 
            current_prices,
            verbose=True
        )
        
        # Log exit messages
        if scan_result['log_messages']:
            print(f"📤 Exit executions:")
            for message in scan_result['log_messages']:
                print(f"   {message}")
        
        # Log closed trades
        if scan_result['closed_trades']:
            for trade_dict in scan_result['closed_trades']:
                from src.trading.portfolio import TradeRecord
                trade = TradeRecord.from_dict(trade_dict)
                self.tracker.log_trade(trade)
        
        self.total_exits_executed += scan_result['positions_closed']
        
        # Save portfolio state
        self.tracker.save_portfolio_state(self.portfolio)
        
        return {
            'positions_monitored': scan_result['positions_evaluated'],
            'positions_closed': scan_result['positions_closed'],
            'total_pnl_from_exits': scan_result['total_pnl_from_exits']
        }
    
    def generate_status_report(self, current_prices: Dict[str, float] = None) -> str:
        """Generate current trading status report."""
        if current_prices is None:
            # Use entry prices as fallback
            current_prices = {
                market_id: position.entry_price 
                for market_id, position in self.portfolio.positions.items()
            }
        
        return self.reporter.generate_telegram_report(self.portfolio, current_prices)
    
    def run_trading_cycle(
        self, 
        new_signals: List[Signal] = None, 
        current_prices: Dict[str, float] = None
    ) -> Dict:
        """
        Complete trading cycle: process signals + monitor positions.
        
        This is the main method to call in your monitoring loop.
        
        Args:
            new_signals: New signals to process
            current_prices: Current market prices
            
        Returns:
            Dict with cycle results
        """
        cycle_start = datetime.now()
        print(f"\n🚀 Starting trading cycle at {cycle_start.strftime('%H:%M:%S')}")
        
        # Step 1: Process new signals
        signal_results = self.process_new_signals(new_signals or [])
        
        # Step 2: Monitor active positions
        monitor_results = self.monitor_active_positions(current_prices)
        
        # Step 3: Update tracking
        cycle_time = (datetime.now() - cycle_start).total_seconds()
        
        # Combined results
        results = {
            'cycle_timestamp': cycle_start.isoformat(),
            'cycle_duration_seconds': cycle_time,
            'signal_processing': signal_results,
            'position_monitoring': monitor_results,
            'portfolio_summary': self.portfolio.get_pnl_summary(current_prices or {}),
            'total_stats': {
                'total_signals_processed': self.total_signals_processed,
                'total_exits_executed': self.total_exits_executed,
                'current_open_positions': self.portfolio.open_position_count
            }
        }
        
        print(f"✅ Trading cycle complete ({cycle_time:.1f}s)")
        print(f"   Signals: {signal_results['signals_processed']} processed, {signal_results['new_positions']} positions opened")
        print(f"   Monitoring: {monitor_results['positions_monitored']} positions, {monitor_results['positions_closed']} closed")
        print(f"   Portfolio: ${results['portfolio_summary']['total_value']:.2f} ({results['portfolio_summary']['return_pct']:+.1f}%)")
        
        return results


def demo_integration():
    """Demo of how to integrate active trading into main loop."""
    print("🚀 Active Trading Integration Demo")
    print("=" * 50)
    
    # Initialize monitor
    monitor = ActiveTradingMonitor(initial_balance=1000.0)
    
    # Simulate some signals arriving
    demo_signals = [
        Signal(
            market_id="demo_market_1",
            direction="BUY_YES",
            confidence=0.75,
            reasoning="Demo signal for integration test",
            current_price=0.45,
            expected_price=0.60,
            event_id="demo_event_1"
        )
    ]
    
    # Simulate price data (in real implementation, fetch from Polymarket)
    demo_prices = {
        "demo_market_1": 0.52  # Simulate price increase
    }
    
    print("\n📡 Cycle 1: Processing new signals")
    results1 = monitor.run_trading_cycle(new_signals=demo_signals)
    
    print("\n📊 Cycle 2: Monitoring with price updates")
    results2 = monitor.run_trading_cycle(current_prices=demo_prices)
    
    print("\n📱 Final Status Report:")
    print("-" * 50)
    status_report = monitor.generate_status_report(demo_prices)
    print(status_report)
    
    print("\n💡 Integration Notes:")
    print("-" * 50)
    print("1. Call monitor.run_trading_cycle() in your main scan loop")
    print("2. Pass new signals from your event detection system")
    print("3. Fetch current prices from Polymarket API")
    print("4. Monitor runs automatically - no manual intervention needed")
    print("5. Generate reports for Telegram notifications")
    
    return monitor


if __name__ == "__main__":
    try:
        demo_integration()
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)