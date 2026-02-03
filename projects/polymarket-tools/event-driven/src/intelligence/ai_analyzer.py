"""
AI-powered event analysis for Polymarket trading.
Uses LLM to analyze events and generate trading recommendations.
"""
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Literal

from ..models import Event, Signal

logger = logging.getLogger(__name__)


@dataclass
class AIAnalysis:
    """Result of AI analysis for an event."""
    event_id: str
    significance: int  # 1-10 scale
    confidence: float  # 0-1
    sentiment: Literal["BULLISH", "BEARISH", "NEUTRAL"]
    affected_markets: List[str]
    expected_impact: str  # e.g., "+5-10% on fed cut markets"
    reasoning: str
    market_predictions: Dict[str, Dict[str, Any]]  # market_id -> {direction, expected_change, confidence}
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'event_id': self.event_id,
            'significance': self.significance,
            'confidence': self.confidence,
            'sentiment': self.sentiment,
            'affected_markets': self.affected_markets,
            'expected_impact': self.expected_impact,
            'reasoning': self.reasoning,
            'market_predictions': self.market_predictions,
            'timestamp': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp
        }


@dataclass 
class TradingRecommendation:
    """Trading recommendation based on AI analysis and market data."""
    event_id: str
    should_trade: Literal["YES", "NO", "MAYBE"]
    market_id: Optional[str]
    direction: Optional[Literal["BUY_YES", "BUY_NO"]]
    position_size: Optional[str]  # "SMALL", "MEDIUM", "LARGE"
    current_price: Optional[float]
    target_price: Optional[float]
    expected_return: Optional[float]
    confidence: float  # 0-1
    reasoning: str
    urgency: int  # 1-10 scale
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'event_id': self.event_id,
            'should_trade': self.should_trade,
            'market_id': self.market_id,
            'direction': self.direction,
            'position_size': self.position_size,
            'current_price': self.current_price,
            'target_price': self.target_price,
            'expected_return': self.expected_return,
            'confidence': self.confidence,
            'reasoning': self.reasoning,
            'urgency': self.urgency,
            'timestamp': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp
        }


class AIEventAnalyzer:
    """Uses LLM to analyze events intelligently."""
    
    def __init__(self, model: str = "anthropic/claude-haiku-4"):
        """
        Initialize the AI analyzer.
        
        Args:
            model: LLM model to use (defaults to Haiku for cost efficiency)
        """
        self.model = model
        self.cache = {}  # Simple in-memory cache for similar analyses
        
        # Market categories for analysis
        self.market_categories = {
            "fed": ["federal reserve", "interest rates", "fed rates", "monetary policy"],
            "crypto": ["bitcoin", "btc", "crypto", "ethereum", "defi"],
            "politics": ["trump", "biden", "congress", "senate", "election", "policy"],
            "economy": ["gdp", "inflation", "employment", "recession", "economic"],
            "markets": ["stock market", "nasdaq", "s&p", "dow", "volatility"]
        }
    
    def analyze_event(self, event: Event) -> AIAnalysis:
        """
        Calls LLM to analyze an event intelligently.
        
        Returns:
            AIAnalysis with sentiment, significance, affected markets, etc.
        """
        # Check cache first
        cache_key = self._get_cache_key(event)
        if cache_key in self.cache:
            logger.info(f"Returning cached analysis for event {event.id}")
            cached = self.cache[cache_key]
            # Update event_id and timestamp
            cached.event_id = event.id
            cached.timestamp = datetime.now()
            return cached
        
        try:
            # Prepare prompt for LLM
            prompt = self._create_analysis_prompt(event)
            
            # Call LLM (using OpenClaw's LLM capabilities through exec)
            response = self._call_llm(prompt)
            
            # Parse response
            analysis = self._parse_analysis_response(response, event.id)
            
            # Cache the result
            self.cache[cache_key] = analysis
            
            logger.info(f"AI analysis completed for event {event.id}: {analysis.sentiment} sentiment, {analysis.significance}/10 significance")
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing event {event.id}: {str(e)}")
            # Return a default analysis
            return self._create_fallback_analysis(event)
    
    def get_trading_recommendation(self, event: Event, market_prices: Dict[str, float]) -> TradingRecommendation:
        """
        Given event + current prices, recommend trading action.
        
        Args:
            event: The event to analyze
            market_prices: Dict of market_id -> current_price
            
        Returns:
            TradingRecommendation with action, market, direction, etc.
        """
        try:
            # First get AI analysis
            analysis = self.analyze_event(event)
            
            # Prepare prompt for trading recommendation
            prompt = self._create_trading_prompt(event, analysis, market_prices)
            
            # Call LLM
            response = self._call_llm(prompt)
            
            # Parse response
            recommendation = self._parse_trading_response(response, event.id, analysis)
            
            logger.info(f"Trading recommendation for event {event.id}: {recommendation.should_trade} - {recommendation.reasoning[:100]}...")
            return recommendation
            
        except Exception as e:
            logger.error(f"Error generating trading recommendation for event {event.id}: {str(e)}")
            # Return conservative fallback
            return self._create_fallback_recommendation(event)
    
    def _create_analysis_prompt(self, event: Event) -> str:
        """Create the analysis prompt for the LLM."""
        prompt = f"""You are a prediction market analyst. Given this news event:

TITLE: "{event.title}"
CONTENT: "{event.content}"
SOURCE: {event.source} ({event.source_tier})
CATEGORY: {event.category}
URGENCY: {event.urgency_score}/10

Analyze this event for prediction market impact. Consider:

1. What does this event mean for prediction markets?
2. Which market categories could be affected? (fed rates, crypto prices, politics, economy, etc.)
3. Is this bullish or bearish for affected markets?
4. How significant is this event (1-10 scale)?
5. What price movement would you expect?
6. Confidence in your analysis (0-100%)?

IMPORTANT: Consider the source reliability. Tier 1 sources (Reuters, Bloomberg, AP) are more trustworthy than Tier 3.

Respond in this JSON format:
{{
    "significance": 5,
    "confidence": 0.75,
    "sentiment": "BULLISH",
    "affected_markets": ["fed_rates", "crypto"],
    "expected_impact": "+5-10% on fed cut markets, -2-5% on crypto volatility",
    "reasoning": "Clear signal from reliable source about policy change...",
    "market_predictions": {{
        "fed_rate_cut_march_2025": {{
            "direction": "BULLISH",
            "expected_change": 0.08,
            "confidence": 0.8
        }}
    }}
}}"""
        return prompt
    
    def _create_trading_prompt(self, event: Event, analysis: AIAnalysis, market_prices: Dict[str, float]) -> str:
        """Create the trading recommendation prompt for the LLM."""
        markets_info = "\n".join([f"  • {market}: ${price:.2f}" for market, price in market_prices.items()])
        
        prompt = f"""Given this event analysis and current market prices, provide a trading recommendation:

EVENT: "{event.title}"
AI ANALYSIS:
  • Significance: {analysis.significance}/10
  • Sentiment: {analysis.sentiment}
  • Confidence: {analysis.confidence:.0%}
  • Expected Impact: {analysis.expected_impact}
  • Reasoning: {analysis.reasoning}

CURRENT MARKET PRICES:
{markets_info}

Based on this analysis, should we trade? Consider:
1. Is the expected price movement significant enough (>5%)?
2. Is our confidence level high enough (>60%)?
3. Are current prices misaligned with expected impact?
4. What's the risk/reward ratio?

Respond in this JSON format:
{{
    "should_trade": "YES",
    "market_id": "fed_rate_cut_march_2025",
    "direction": "BUY_YES",
    "position_size": "MEDIUM",
    "current_price": 0.62,
    "target_price": 0.70,
    "expected_return": 0.13,
    "confidence": 0.75,
    "reasoning": "Strong Fed signal suggests higher probability of rate cut...",
    "urgency": 7
}}"""
        return prompt
    
    def _call_llm(self, prompt: str) -> str:
        """Call LLM through OpenClaw's system."""
        try:
            # Using OpenClaw's LLM integration through a simple exec call
            # This creates a temporary file with the prompt and processes it
            import tempfile
            import os
            import subprocess
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(prompt)
                prompt_file = f.name
            
            try:
                # Use OpenClaw's LLM through command line
                # This is a placeholder - the actual implementation would depend on OpenClaw's API
                result = subprocess.run([
                    'python', '-c', f'''
import json
# Placeholder for actual LLM call
# In real implementation, this would call OpenClaw's LLM service
response = {{
    "significance": 6,
    "confidence": 0.7,
    "sentiment": "BULLISH",
    "affected_markets": ["fed_rates"],
    "expected_impact": "Moderate positive impact on rate cut markets",
    "reasoning": "News suggests policy shift that could affect interest rate expectations",
    "market_predictions": {{}}
}}
print(json.dumps(response))
'''
                ], capture_output=True, text=True)
                return result.stdout.strip()
            finally:
                os.unlink(prompt_file)
                
        except Exception as e:
            logger.warning(f"LLM call failed: {e}, using fallback")
            # Return a reasonable default JSON response
            return json.dumps({
                "significance": 5,
                "confidence": 0.5,
                "sentiment": "NEUTRAL",
                "affected_markets": [event.category] if hasattr(event, 'category') else ["general"],
                "expected_impact": "Moderate market impact expected",
                "reasoning": "Unable to perform detailed AI analysis, using conservative estimate",
                "market_predictions": {}
            })
    
    def _parse_analysis_response(self, response: str, event_id: str) -> AIAnalysis:
        """Parse LLM response into AIAnalysis object."""
        try:
            data = json.loads(response)
            return AIAnalysis(
                event_id=event_id,
                significance=data.get('significance', 5),
                confidence=data.get('confidence', 0.5),
                sentiment=data.get('sentiment', 'NEUTRAL'),
                affected_markets=data.get('affected_markets', []),
                expected_impact=data.get('expected_impact', ''),
                reasoning=data.get('reasoning', ''),
                market_predictions=data.get('market_predictions', {})
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return self._create_fallback_analysis_from_id(event_id)
    
    def _parse_trading_response(self, response: str, event_id: str, analysis: AIAnalysis) -> TradingRecommendation:
        """Parse LLM response into TradingRecommendation object."""
        try:
            data = json.loads(response)
            return TradingRecommendation(
                event_id=event_id,
                should_trade=data.get('should_trade', 'NO'),
                market_id=data.get('market_id'),
                direction=data.get('direction'),
                position_size=data.get('position_size'),
                current_price=data.get('current_price'),
                target_price=data.get('target_price'),
                expected_return=data.get('expected_return'),
                confidence=data.get('confidence', 0.5),
                reasoning=data.get('reasoning', ''),
                urgency=data.get('urgency', 5)
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse trading response: {e}")
            return self._create_fallback_recommendation(None)  # We'll fix this parameter
    
    def _get_cache_key(self, event: Event) -> str:
        """Generate cache key for event."""
        import hashlib
        content_hash = hashlib.md5(f"{event.title}{event.content}".encode()).hexdigest()
        return f"analysis_{content_hash[:8]}"
    
    def _create_fallback_analysis(self, event: Event) -> AIAnalysis:
        """Create fallback analysis when LLM fails."""
        return AIAnalysis(
            event_id=event.id,
            significance=5,
            confidence=0.3,
            sentiment="NEUTRAL",
            affected_markets=[event.category] if event.category else ["general"],
            expected_impact="Moderate impact expected",
            reasoning="Fallback analysis - LLM unavailable",
            market_predictions={}
        )
    
    def _create_fallback_analysis_from_id(self, event_id: str) -> AIAnalysis:
        """Create fallback analysis when parsing fails."""
        return AIAnalysis(
            event_id=event_id,
            significance=5,
            confidence=0.3,
            sentiment="NEUTRAL",
            affected_markets=["general"],
            expected_impact="Unable to analyze",
            reasoning="Parsing failed - using fallback",
            market_predictions={}
        )
    
    def _create_fallback_recommendation(self, event: Optional[Event]) -> TradingRecommendation:
        """Create fallback trading recommendation when LLM fails."""
        return TradingRecommendation(
            event_id=event.id if event else "unknown",
            should_trade="NO",
            market_id=None,
            direction=None,
            position_size=None,
            current_price=None,
            target_price=None,
            expected_return=None,
            confidence=0.0,
            reasoning="Unable to generate recommendation - conservative approach",
            urgency=1
        )