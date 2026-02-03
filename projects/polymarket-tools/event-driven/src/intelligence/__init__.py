"""
Intelligence module for event-driven Polymarket trading.
Provides event analysis, market mapping, and AI-powered analysis capabilities.
"""
from .mapper import MarketMapper, MarketMatch, get_affected_markets
from .ai_analyzer import AIEventAnalyzer, AIAnalysis, TradingRecommendation
from .decision_queue import DecisionQueue, PendingDecision
from .ai_integration import AIIntegrationService, create_ai_integration

__all__ = [
    'MarketMapper', 'MarketMatch', 'get_affected_markets',
    'AIEventAnalyzer', 'AIAnalysis', 'TradingRecommendation', 
    'DecisionQueue', 'PendingDecision',
    'AIIntegrationService', 'create_ai_integration'
]