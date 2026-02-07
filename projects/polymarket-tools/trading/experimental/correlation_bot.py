#!/usr/bin/env python3
"""
Correlation Bot - Tracks BTC/ETH/SOL correlation and signals mean reversion opportunities

Strategy:
- Track rolling correlation between BTC, ETH, SOL
- When correlation breaks (one asset diverges significantly) → signal mean reversion
- Bet on the divergent asset reverting to its normal correlation pattern

Data source: Binance public API
"""

import json
import requests
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import statistics

class CorrelationBot:
    def __init__(self, state_file: str = "correlation_bot_state.json"):
        self.state_file = Path(__file__).parent / state_file
        self.balance = 100.0
        self.position = None
        
        # Parameters (define before loading state)
        self.pairs = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
        self.window_size = 20  # Rolling window for correlation
        self.divergence_threshold = 0.3  # Correlation break threshold
        
        self.state = self.load_state()
        
    def load_state(self) -> Dict:
        """Load bot state from file"""
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {
            "last_check_time": None,
            "signals": [],
            "price_history": {pair: [] for pair in self.pairs}
        }
    
    def save_state(self):
        """Save bot state to file"""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def fetch_recent_prices(self, symbol: str, interval: str = '5m', limit: int = 50) -> List[float]:
        """
        Fetch recent price data from Binance
        
        Args:
            symbol: Trading pair (e.g., BTCUSDT)
            interval: Candle interval (1m, 5m, 15m, 1h, etc.)
            limit: Number of candles to fetch
        """
        try:
            url = f"https://api.binance.com/api/v3/klines"
            params = {
                'symbol': symbol,
                'interval': interval,
                'limit': limit
            }
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            klines = response.json()
            # Extract closing prices (index 4)
            prices = [float(k[4]) for k in klines]
            return prices
            
        except Exception as e:
            print(f"[ERROR] Failed to fetch prices for {symbol}: {e}")
            return []
    
    def calculate_returns(self, prices: List[float]) -> List[float]:
        """Calculate percentage returns from price series"""
        if len(prices) < 2:
            return []
        
        returns = []
        for i in range(1, len(prices)):
            ret = (prices[i] - prices[i-1]) / prices[i-1]
            returns.append(ret)
        
        return returns
    
    def calculate_correlation(self, returns1: List[float], returns2: List[float]) -> Optional[float]:
        """
        Calculate Pearson correlation coefficient between two return series
        
        Returns value between -1 and 1:
        - 1 = perfect positive correlation
        - 0 = no correlation
        - -1 = perfect negative correlation
        """
        if len(returns1) != len(returns2) or len(returns1) < 2:
            return None
        
        n = len(returns1)
        
        mean1 = statistics.mean(returns1)
        mean2 = statistics.mean(returns2)
        
        # Calculate covariance
        covariance = sum((returns1[i] - mean1) * (returns2[i] - mean2) for i in range(n)) / n
        
        # Calculate standard deviations
        std1 = statistics.stdev(returns1)
        std2 = statistics.stdev(returns2)
        
        if std1 == 0 or std2 == 0:
            return None
        
        correlation = covariance / (std1 * std2)
        return correlation
    
    def detect_correlation_break(self, correlations: Dict[str, float], historical_avg: Dict[str, float]) -> Optional[Dict]:
        """
        Detect if current correlation significantly differs from historical average
        
        Returns signal if divergence detected
        """
        signals = []
        
        for pair_name, current_corr in correlations.items():
            if pair_name not in historical_avg:
                continue
            
            avg_corr = historical_avg[pair_name]
            divergence = abs(current_corr - avg_corr)
            
            if divergence >= self.divergence_threshold:
                # Determine which asset is diverging
                if 'BTC-ETH' in pair_name:
                    assets = ['BTC', 'ETH']
                elif 'BTC-SOL' in pair_name:
                    assets = ['BTC', 'SOL']
                elif 'ETH-SOL' in pair_name:
                    assets = ['ETH', 'SOL']
                else:
                    continue
                
                signals.append({
                    'pair': pair_name,
                    'current_correlation': current_corr,
                    'historical_avg': avg_corr,
                    'divergence': divergence,
                    'assets': assets,
                    'signal_type': 'MEAN_REVERSION'
                })
        
        # Return strongest divergence signal
        if signals:
            return max(signals, key=lambda x: x['divergence'])
        
        return None
    
    def log_signal(self, signal: Dict, prices: Dict[str, float]):
        """Log mean reversion opportunity signal"""
        timestamp = datetime.now().isoformat()
        
        log_entry = {
            'timestamp': timestamp,
            'signal_type': signal['signal_type'],
            'pair': signal['pair'],
            'assets': signal['assets'],
            'current_correlation': signal['current_correlation'],
            'historical_avg': signal['historical_avg'],
            'divergence': signal['divergence'],
            'prices': prices,
            'balance': self.balance
        }
        
        if 'signals' not in self.state:
            self.state['signals'] = []
        self.state['signals'].append(log_entry)
        
        if len(self.state['signals']) > 50:
            self.state['signals'] = self.state['signals'][-50:]
        
        # Console output
        print(f"\n{'='*70}")
        print(f"[{timestamp}] 🔄 CORRELATION BREAK - MEAN REVERSION OPPORTUNITY")
        print(f"{'='*70}")
        print(f"Pair: {signal['pair']}")
        print(f"Assets: {' vs '.join(signal['assets'])}")
        print(f"Current Correlation: {signal['current_correlation']:.3f}")
        print(f"Historical Average: {signal['historical_avg']:.3f}")
        print(f"Divergence: {signal['divergence']:.3f} ({'STRONG' if signal['divergence'] > 0.5 else 'MODERATE'})")
        print(f"\nCurrent Prices:")
        for symbol, price in prices.items():
            print(f"  {symbol}: ${price:,.2f}")
        print(f"\nStrategy: Correlation broke - expect mean reversion")
        print(f"Balance: ${self.balance:.2f}")
        print(f"{'='*70}\n")
    
    def cycle(self):
        """Main bot cycle - check for correlation breaks"""
        print(f"[{datetime.now().isoformat()}] Correlation Bot - Analyzing asset correlations...")
        
        # Fetch recent prices for all pairs
        price_data = {}
        current_prices = {}
        
        for symbol in self.pairs:
            prices = self.fetch_recent_prices(symbol, interval='5m', limit=self.window_size + 1)
            if not prices:
                print(f"[ERROR] Failed to fetch prices for {symbol}")
                return
            
            price_data[symbol] = prices
            current_prices[symbol] = prices[-1]
            print(f"{symbol}: ${prices[-1]:,.2f}")
        
        # Calculate returns
        returns = {symbol: self.calculate_returns(prices) 
                  for symbol, prices in price_data.items()}
        
        # Calculate current correlations
        correlations = {
            'BTC-ETH': self.calculate_correlation(returns['BTCUSDT'], returns['ETHUSDT']),
            'BTC-SOL': self.calculate_correlation(returns['BTCUSDT'], returns['SOLUSDT']),
            'ETH-SOL': self.calculate_correlation(returns['ETHUSDT'], returns['SOLUSDT'])
        }
        
        print(f"\nCurrent Correlations (window={self.window_size}):")
        for pair, corr in correlations.items():
            if corr is not None:
                print(f"  {pair}: {corr:.3f}")
        
        # Calculate historical average correlations (from state)
        if 'correlation_history' not in self.state:
            self.state['correlation_history'] = {pair: [] for pair in correlations.keys()}
        
        # Update history
        for pair, corr in correlations.items():
            if corr is not None:
                self.state['correlation_history'][pair].append(corr)
                # Keep last 100 observations
                if len(self.state['correlation_history'][pair]) > 100:
                    self.state['correlation_history'][pair] = self.state['correlation_history'][pair][-100:]
        
        # Calculate historical averages
        historical_avg = {}
        for pair, history in self.state['correlation_history'].items():
            if len(history) >= 10:  # Need at least 10 observations
                historical_avg[pair] = statistics.mean(history)
        
        if historical_avg:
            print(f"\nHistorical Average Correlations:")
            for pair, avg in historical_avg.items():
                print(f"  {pair}: {avg:.3f}")
        
        # Detect correlation breaks
        if historical_avg:
            signal = self.detect_correlation_break(correlations, historical_avg)
            
            if signal:
                self.log_signal(signal, current_prices)
            else:
                print(f"\nNo significant correlation breaks detected (threshold={self.divergence_threshold})")
        else:
            print(f"\nBuilding correlation history... ({len(self.state['correlation_history']['BTC-ETH'])} observations)")
        
        # Update state
        self.state['last_check_time'] = datetime.now().isoformat()
        self.state['price_history'] = {symbol: prices[-10:] for symbol, prices in price_data.items()}
        self.save_state()
        
        print(f"\nCycle complete. Total signals logged: {len(self.state.get('signals', []))}")


def main():
    """Run bot cycle"""
    bot = CorrelationBot()
    bot.cycle()


if __name__ == "__main__":
    main()
