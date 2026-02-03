#!/usr/bin/env python3
"""
Standalone script to run backtests.
"""
import asyncio
import argparse
import json
import sys
import os
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from src.backtesting.data_loader import load_historical_events, load_market_prices, generate_mock_data, save_mock_data
from src.backtesting.simulator import BacktestSimulator, MockPipelineSimulator
from src.backtesting.metrics import calculate_metrics, analyze_by_market, analyze_by_direction, analyze_by_confidence


async def run_backtest(days: int = 30, 
                      use_mock_data: bool = True,
                      mock_pipeline: bool = True,
                      holding_period: int = 24,
                      data_dir: str = "data/historical",
                      output_file: str = None,
                      detailed: bool = False) -> None:
    """
    Run a complete backtest.
    
    Args:
        days: Number of days to backtest
        use_mock_data: Whether to generate/use mock data
        mock_pipeline: Whether to use simplified mock pipeline
        holding_period: Position holding period in hours
        data_dir: Directory containing historical data
        output_file: Optional file to save detailed results
        detailed: Whether to show detailed analysis
    """
    
    print(f"🧪 POLYMARKET BACKTESTING FRAMEWORK")
    print(f"{'='*60}")
    print(f"Configuration:")
    print(f"  📅 Period: {days} days")
    print(f"  🎲 Mock data: {use_mock_data}")
    print(f"  🏭 Mock pipeline: {mock_pipeline}")
    print(f"  ⏰ Holding period: {holding_period}h")
    print(f"  📁 Data directory: {data_dir}")
    print()
    
    # Load or generate data
    if use_mock_data:
        print("🎲 Generating mock data...")
        events, market_prices = generate_mock_data(days=days)
        
        # Save to files for inspection
        save_mock_data(events, market_prices, data_dir)
    else:
        print("📂 Loading historical data...")
        events = load_historical_events(f"{data_dir}/events.json")
        market_prices = load_market_prices(f"{data_dir}/prices.json")
        
        if not events:
            print("❌ No historical events found. Try --mock-data")
            return
        
        if not market_prices:
            print("❌ No historical prices found. Try --mock-data")
            return
    
    print(f"📊 Loaded {len(events)} events and {len(market_prices)} markets")
    
    # Initialize simulator
    if mock_pipeline:
        print("🏭 Using mock pipeline for faster testing...")
        simulator = MockPipelineSimulator(holding_period_hours=holding_period)
    else:
        print("🔧 Using full trading pipeline...")
        simulator = BacktestSimulator(holding_period_hours=holding_period)
    
    # Run backtest
    print("\n🚀 Starting backtest...")
    results = await simulator.run_backtest(events, market_prices)
    
    if not results:
        print("❌ No trades executed. Check data and signal generation.")
        return
    
    # Calculate metrics
    print("\n📈 Calculating performance metrics...")
    metrics = calculate_metrics(results)
    
    # Print main results
    metrics.print_summary()
    
    # Detailed analysis
    if detailed:
        print("\n" + "="*50)
        print("         DETAILED ANALYSIS")
        print("="*50)
        
        # Market analysis
        market_analysis = analyze_by_market(results)
        if market_analysis:
            print("\n📊 Performance by Market:")
            for market_id, stats in market_analysis.items():
                print(f"  {market_id[:20]}...")
                print(f"    Trades: {stats['trades']}, Win rate: {stats['win_rate']:.1%}, "
                      f"Avg return: {stats['avg_return']:+.1%}")
        
        # Direction analysis
        direction_analysis = analyze_by_direction(results)
        if direction_analysis:
            print("\n🎯 Performance by Direction:")
            for direction, stats in direction_analysis.items():
                print(f"  {direction}: {stats['trades']} trades, "
                      f"Win rate: {stats['win_rate']:.1%}, Avg return: {stats['avg_return']:+.1%}")
        
        # Confidence analysis
        confidence_analysis = analyze_by_confidence(results)
        if confidence_analysis:
            print("\n🎯 Performance by Confidence:")
            for conf_range, stats in confidence_analysis.items():
                print(f"  {conf_range}: {stats['trades']} trades, "
                      f"Win rate: {stats['win_rate']:.1%}, Avg return: {stats['avg_return']:+.1%}")
    
    # Save detailed results if requested
    if output_file:
        output_data = {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'days': days,
                'use_mock_data': use_mock_data,
                'mock_pipeline': mock_pipeline,
                'holding_period': holding_period
            },
            'metrics': metrics.to_dict(),
            'trades': [result.to_dict() for result in results]
        }
        
        if detailed:
            output_data['analysis'] = {
                'by_market': market_analysis,
                'by_direction': direction_analysis,
                'by_confidence': confidence_analysis
            }
        
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        print(f"\n💾 Detailed results saved to: {output_file}")
    
    # Performance assessment
    print("\n" + "="*50)
    print("         PERFORMANCE ASSESSMENT")
    print("="*50)
    
    if metrics.win_rate >= 0.6:
        print("✅ GOOD: Win rate above 60%")
    elif metrics.win_rate >= 0.5:
        print("⚠️  MODERATE: Win rate above 50%")
    else:
        print("❌ POOR: Win rate below 50%")
    
    if metrics.total_return > 0.1:
        print("✅ GOOD: Strong positive returns")
    elif metrics.total_return > 0:
        print("⚠️  MODERATE: Positive returns")
    else:
        print("❌ POOR: Negative returns")
    
    if metrics.sharpe_ratio > 1.0:
        print("✅ GOOD: Sharpe ratio above 1.0")
    elif metrics.sharpe_ratio > 0.5:
        print("⚠️  MODERATE: Sharpe ratio above 0.5")
    else:
        print("❌ POOR: Low risk-adjusted returns")
    
    print()


def main():
    """Command-line interface."""
    parser = argparse.ArgumentParser(description="Run Polymarket trading backtest")
    
    parser.add_argument("--days", type=int, default=30,
                       help="Number of days to backtest (default: 30)")
    
    parser.add_argument("--real-data", action="store_true",
                       help="Use real historical data instead of mock data")
    
    parser.add_argument("--full-pipeline", action="store_true", 
                       help="Use full trading pipeline instead of mock pipeline")
    
    parser.add_argument("--holding-period", type=int, default=24,
                       help="Position holding period in hours (default: 24)")
    
    parser.add_argument("--data-dir", type=str, default="data/historical",
                       help="Directory containing historical data (default: data/historical)")
    
    parser.add_argument("--output", type=str,
                       help="File to save detailed results (JSON format)")
    
    parser.add_argument("--detailed", action="store_true",
                       help="Show detailed analysis by market, direction, etc.")
    
    parser.add_argument("--generate-data", action="store_true",
                       help="Just generate mock data and exit")
    
    args = parser.parse_args()
    
    # Just generate data if requested
    if args.generate_data:
        print("🎲 Generating mock data...")
        events, prices = generate_mock_data(days=args.days)
        save_mock_data(events, prices, args.data_dir)
        print("✅ Mock data generated and saved")
        return
    
    # Run backtest
    asyncio.run(run_backtest(
        days=args.days,
        use_mock_data=not args.real_data,
        mock_pipeline=not args.full_pipeline,
        holding_period=args.holding_period,
        data_dir=args.data_dir,
        output_file=args.output,
        detailed=args.detailed
    ))


if __name__ == "__main__":
    main()