"""
Autonomous Paper Trading System for Polymarket
============================================

This package implements an autonomous paper trading system that:
- Receives signals from the event-driven system
- Makes autonomous trading decisions based on confidence and risk metrics
- Tracks a virtual portfolio without real money
- Records P&L as if trades were real

Key Components:
- PaperPortfolio: Manages virtual portfolio and positions
- TradingDecisionEngine: Makes autonomous trading decisions
- TradingTracker: Persists trades and portfolio state
- ReportGenerator: Creates performance reports

Trading Rules:
- Maximum 10% of portfolio per trade
- Minimum confidence: 60%
- Minimum expected return: 3%
- Maximum 5 open positions simultaneously
- Auto-close positions after 24h or when market closes
"""

from .portfolio import PaperPortfolio, Position, TradeRecord
from .decision_engine import TradingDecisionEngine, TradingDecision
from .tracker import TradingTracker
from .reporter import ReportGenerator

__all__ = [
    'PaperPortfolio',
    'Position', 
    'TradeRecord',
    'TradingDecisionEngine',
    'TradingDecision',
    'TradingTracker',
    'ReportGenerator'
]

__version__ = '1.0.0'