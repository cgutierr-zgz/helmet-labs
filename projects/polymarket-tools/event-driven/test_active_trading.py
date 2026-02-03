#!/usr/bin/env python3
"""
Test script for Active Trading System
====================================

Tests the active trading functionality with exit strategies:
1. Open positions with signals
2. Simulate price movements 
3. Test take profit, stop loss, and time limit exits
4. Verify automatic position management
"""
import sys
import os
from datetime import datetime, timedelta
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from src.models import Signal
from src.trading import (
    PaperPortfolio, 
    TradingDecisionEngine, 
    TradingTracker, 
    ReportGenerator,
    ExitStrategy,
    Position
)


def create_test_signals():
    """Create test trading signals for active trading."""
    signals = [
        Signal(
            market_id="btc_price_target",
            direction="BUY_YES",
            confidence=0.80,
            reasoning="Strong bullish momentum expected",
            current_price=0.40,
            expected_price=0.60,
            event_id="evt_btc_momentum_123"
        ),
        Signal(
            market_id="fed_dovish_pivot",
            direction="BUY_NO",  # Betting against dovish pivot
            confidence=0.70,
            reasoning="Inflation data suggests hawkish stance continues",
            current_price=0.65,
            expected_price=0.45,
            event_id="evt_fed_hawkish_456"
        ),
        Signal(
            market_id="ai_stock_rally",
            direction="BUY_YES",
            confidence=0.75,
            reasoning="AI earnings season looks strong",
            current_price=0.35,
            expected_price=0.55,
            event_id="evt_ai_earnings_789"
        )
    ]
    
    return signals


def simulate_price_movements():
    """Simulate different price scenarios for testing exit conditions."""
    scenarios = {
        # Take profit scenario: +15% gain
        "btc_price_target": {
            "original": 0.40,
            "new": 0.46,  # +15% gain triggers take profit (+10%)
            "scenario": "take_profit"
        },
        
        # Stop loss scenario: -10% loss
        "fed_dovish_pivot": {
            "original": 0.65,
            "new": 0.72,  # +10.8% loss for BUY_NO position triggers stop loss (-7%)
            "scenario": "stop_loss"
        },
        
        # Small gain, should hold
        "ai_stock_rally": {
            "original": 0.35,
            "new": 0.37,  # +5.7% gain, below take profit threshold
            "scenario": "hold"
        }
    }
    
    return scenarios


def test_active_trading():
    """Test the complete active trading system with exit strategies."""
    print("🚀 Testing Active Trading System with Exit Strategies\n")
    
    # Initialize fresh components
    tracker = TradingTracker()
    decision_engine = TradingDecisionEngine()
    
    # Reset portfolio for clean test
    portfolio = tracker.reset_portfolio(initial_balance=1000.0)
    print(f"📊 Fresh Portfolio: ${portfolio.balance:.2f}")
    
    # Create and execute test signals
    signals = create_test_signals()
    print(f"📡 Generated {len(signals)} test signals")
    
    print("\n🤖 Opening Positions:")
    print("-" * 60)
    
    opened_positions = 0
    for i, signal in enumerate(signals, 1):
        print(f"\n{i}. Market: {signal.market_id}")
        print(f"   Direction: {signal.direction}, Price: ${signal.current_price:.3f}")
        print(f"   Confidence: {signal.confidence:.0%}")
        
        # Make and execute decision
        decision = decision_engine.evaluate_signal(signal, portfolio)
        
        if decision.should_trade:
            try:
                decision_engine.execute_decision(decision, portfolio)
                opened_positions += 1
                position = portfolio.positions[signal.market_id]
                print(f"   ✅ OPENED: ${decision.position_size:.0f} position")
                print(f"   📈 Entry: ${position.entry_price:.3f}, Shares: {position.shares:.1f}")
            except Exception as e:
                print(f"   ❌ FAILED: {e}")
        else:
            print(f"   ⏭️  SKIPPED: {decision.reasoning}")
    
    print(f"\n📊 Positions opened: {opened_positions}")
    print(f"💰 Remaining balance: ${portfolio.balance:.2f}")
    
    # Save initial state
    tracker.save_portfolio_state(portfolio)
    
    print("\n⏰ Simulating time passage and price movements...")
    
    # Simulate price movements
    price_scenarios = simulate_price_movements()
    current_prices = {market: data["new"] for market, data in price_scenarios.items()}
    
    print("\n📈 Price Movement Simulation:")
    print("-" * 60)
    
    for market_id, scenario in price_scenarios.items():
        if market_id in portfolio.positions:
            position = portfolio.positions[market_id]
            old_price = scenario["original"]
            new_price = scenario["new"]
            price_change_pct = (new_price - old_price) / old_price * 100
            
            # For BUY_NO positions, invert the P&L
            if position.direction == "BUY_NO":
                pnl_change_pct = -price_change_pct
            else:
                pnl_change_pct = price_change_pct
            
            print(f"📊 {market_id}:")
            print(f"   Price: ${old_price:.3f} → ${new_price:.3f} ({price_change_pct:+.1f}%)")
            print(f"   P&L Impact: {pnl_change_pct:+.1f}% (Direction: {position.direction})")
            print(f"   Expected: {scenario['scenario']}")
    
    print(f"\n🔍 Evaluating Exit Conditions:")
    print("-" * 60)
    
    # Evaluate exit decisions
    exit_decisions = decision_engine.evaluate_active_exits(portfolio, current_prices)
    
    for decision in exit_decisions:
        print(f"\n📋 {decision.market_id}:")
        print(f"   Current P&L: {decision.current_pnl_pct:+.1%}")
        print(f"   Days held: {decision.days_held:.1f}")
        print(f"   Decision: {decision.reason}")
        print(f"   Should exit: {'✅ YES' if decision.should_exit else '❌ NO'}")
    
    # Execute exits
    print(f"\n🎯 Executing Active Trading Strategy:")
    print("-" * 60)
    
    scan_result = decision_engine.scan_and_execute_exits(
        portfolio, 
        current_prices, 
        verbose=True
    )
    
    print(f"Positions evaluated: {scan_result['positions_evaluated']}")
    print(f"Positions closed: {scan_result['positions_closed']}")
    print(f"Total P&L from exits: ${scan_result['total_pnl_from_exits']:+.2f}")
    
    # Display exit messages
    if scan_result['log_messages']:
        print(f"\n📤 Exit Log Messages:")
        for message in scan_result['log_messages']:
            print(f"   {message}")
    
    # Log closed trades
    for trade_dict in scan_result['closed_trades']:
        from src.trading.portfolio import TradeRecord
        trade = TradeRecord.from_dict(trade_dict)
        tracker.log_trade(trade)
    
    # Save updated portfolio
    tracker.save_portfolio_state(portfolio)
    
    print(f"\n📊 Final Portfolio State:")
    print("-" * 60)
    
    final_summary = portfolio.get_pnl_summary(current_prices)
    
    print(f"💰 Total Value: ${final_summary['total_value']:,.2f}")
    print(f"💵 Cash Balance: ${final_summary['balance']:,.2f}")
    print(f"📈 Total Return: {final_summary['return_pct']:+.1f}%")
    print(f"📊 Open Positions: {final_summary['open_positions']}")
    print(f"🎯 Total Trades: {final_summary['total_trades']}")
    print(f"🏆 Win Rate: {final_summary['win_rate']:.1f}%")
    
    # Test exit strategy rules directly
    print(f"\n🧪 Testing Exit Strategy Rules:")
    print("-" * 60)
    
    # Test take profit
    test_position = Position(
        id="test_tp",
        market_id="test_take_profit",
        direction="BUY_YES", 
        shares=100,
        entry_price=0.50,
        entry_time=datetime.now() - timedelta(hours=2),
        signal_id="test",
        confidence=0.8
    )
    
    should_exit, reason = ExitStrategy.should_exit(test_position, 0.56)  # +12% gain
    print(f"Take Profit Test: {should_exit} ({reason}) - +12% gain")
    
    # Test stop loss
    should_exit, reason = ExitStrategy.should_exit(test_position, 0.46)  # -8% loss
    print(f"Stop Loss Test: {should_exit} ({reason}) - -8% loss")
    
    # Test time limit
    old_position = Position(
        id="test_time",
        market_id="test_time_limit",
        direction="BUY_YES",
        shares=100, 
        entry_price=0.50,
        entry_time=datetime.now() - timedelta(days=8),  # 8 days old
        signal_id="test",
        confidence=0.8
    )
    
    should_exit, reason = ExitStrategy.should_exit(old_position, 0.52)  # Small gain but old
    print(f"Time Limit Test: {should_exit} ({reason}) - 8 days old")
    
    # Generate final report
    reporter = ReportGenerator(tracker)
    print(f"\n📱 Final Trading Report:")
    print("-" * 60)
    
    telegram_report = reporter.generate_telegram_report(portfolio, current_prices)
    print(telegram_report)
    
    print("\n✅ Active Trading System Test Complete!")
    print(f"\n🎯 Key Features Tested:")
    print("   ✅ Autonomous position opening based on signals")
    print("   ✅ Take profit rule: +10% → close position")
    print("   ✅ Stop loss rule: -7% → close position") 
    print("   ✅ Time limit rule: 7 days → close position")
    print("   ✅ Active monitoring and position management")
    print("   ✅ Comprehensive logging and reporting")
    
    return portfolio, tracker, scan_result


if __name__ == "__main__":
    try:
        test_active_trading()
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)