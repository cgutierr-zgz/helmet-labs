"""
Backtesting framework for the event-driven Polymarket trading system.

This package provides tools to simulate the trading system with historical data
and evaluate performance metrics.
"""
from .data_loader import load_historical_events, load_market_prices, generate_mock_data
from .simulator import BacktestSimulator, TradingResult
from .metrics import BacktestMetrics, calculate_metrics
from .runner import run_backtest

__all__ = [
    'load_historical_events',
    'load_market_prices', 
    'generate_mock_data',
    'BacktestSimulator',
    'TradingResult',
    'BacktestMetrics',
    'calculate_metrics',
    'run_backtest'
]