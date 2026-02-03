#!/usr/bin/env python3
"""
Test script for the Paper Trading System
========================================

Tests the complete paper trading pipeline:
1. Create signals
2. Make trading decisions
3. Execute trades
4. Track portfolio
5. Generate reports
"""
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from src.models import Signal
from src.trading import (
    PaperPortfolio, 
    TradingDecisionEngine, 
    TradingTracker, 
    ReportGenerator
)


def create_test_signals():
    """Create test trading signals."""
    signals = [
        Signal(
            market_id="btc_100k_by_2024",
            direction="BUY_YES",
            confidence=0.75,
            reasoning="Strong technical breakout with institutional adoption",
            current_price=0.45,
            expected_price=0.60,
            event_id="evt_btc_breakout_123"
        ),
        Signal(
            market_id="fed_rate_cut_march",
            direction="BUY_NO",
            confidence=0.65,
            reasoning="Inflation data suggests Fed will hold rates steady",
            current_price=0.70,
            expected_price=0.55,
            event_id="evt_fed_data_456"
        ),
        Signal(
            market_id="ai_regulation_2024",
            direction="BUY_YES",
            confidence=0.50,  # Below threshold
            reasoning="Regulatory momentum building but uncertain timing",
            current_price=0.30,
            expected_price=0.40,
            event_id="evt_ai_regulation_789"
        ),
        Signal(
            market_id="trump_wins_2024",
            direction="BUY_YES",
            confidence=0.80,
            reasoning="Strong polling data and momentum",
            current_price=0.55,
            expected_price=0.75,
            event_id="evt_election_poll_101"
        )
    ]
    
    return signals


def test_trading_system():
    """Test the complete trading system."""
    print("🚀 Testing Paper Trading System\n")
    
    # Initialize components
    tracker = TradingTracker()
    decision_engine = TradingDecisionEngine()
    
    # Get or create portfolio
    portfolio = tracker.get_or_create_portfolio(initial_balance=1000.0)
    print(f"📊 Initial Portfolio: ${portfolio.balance:.2f}")
    
    # Create test signals
    signals = create_test_signals()
    print(f"📡 Generated {len(signals)} test signals")
    
    # Process each signal
    executed_trades = 0
    
    print("\n🤖 Processing Signals:")
    print("-" * 50)
    
    for i, signal in enumerate(signals, 1):
        print(f"\n{i}. Market: {signal.market_id}")
        print(f"   Direction: {signal.direction}")
        print(f"   Confidence: {signal.confidence:.0%}")
        print(f"   Expected Return: {signal.expected_return:.1%}")
        
        # Make trading decision
        decision = decision_engine.evaluate_signal(signal, portfolio)
        
        print(f"   Decision: {decision.reasoning}")
        
        # Log the decision
        tracker.log_decision(decision)
        
        # Execute if recommended
        if decision.should_trade:
            try:
                decision_engine.execute_decision(decision, portfolio)
                executed_trades += 1
                print(f"   ✅ EXECUTED: ${decision.position_size:.0f} position opened")
            except Exception as e:
                print(f"   ❌ FAILED: {e}")
        else:
            print(f"   ⏭️  SKIPPED")
    
    # Save portfolio state
    tracker.save_portfolio_state(portfolio)
    
    # Simulate some time passing and close one position for testing
    print(f"\n⏰ Simulating position exit...")
    
    if portfolio.positions:
        # Close the first position with a simulated price change
        first_market_id = list(portfolio.positions.keys())[0]
        first_position = portfolio.positions[first_market_id]
        
        # Simulate a price movement
        exit_price = first_position.entry_price * 1.10  # 10% gain
        trade = portfolio.close_position(first_market_id, exit_price, "test_close")
        
        if trade:
            tracker.log_trade(trade)
            print(f"✅ Closed position: ${trade.pnl:+.2f} P&L")
    
    # Update portfolio state
    tracker.save_portfolio_state(portfolio)
    
    print(f"\n📊 Trading Summary:")
    print("-" * 50)
    print(f"Signals processed: {len(signals)}")
    print(f"Trades executed: {executed_trades}")
    print(f"Open positions: {portfolio.open_position_count}")
    
    # Generate reports
    reporter = ReportGenerator(tracker)
    
    print("\n📱 Telegram Report:")
    print("-" * 50)
    telegram_report = reporter.generate_telegram_report(portfolio)
    print(telegram_report)
    
    print("\n🏥 Portfolio Health:")
    print("-" * 50)
    health_report = reporter.generate_portfolio_health_report(portfolio)
    print(health_report)
    
    print("\n📈 Trade Analysis:")
    print("-" * 50)
    trade_analysis = reporter.generate_trade_analysis(limit=5)
    print(trade_analysis)
    
    # Test daily summary
    daily_summary = tracker.calculate_daily_metrics()
    print(f"\n📅 Daily Summary:")
    print("-" * 50)
    for key, value in daily_summary.items():
        if key != 'calculated_at':
            print(f"{key}: {value}")
    
    print("\n✅ Paper Trading System Test Complete!")
    
    return portfolio, tracker


if __name__ == "__main__":
    try:
        test_trading_system()
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)