"""
Intelligence module for event-driven Polymarket trading.
Provides event analysis and market mapping capabilities.
"""
from .mapper import MarketMapper, MarketMatch, get_affected_markets

__all__ = ['MarketMapper', 'MarketMatch', 'get_affected_markets']