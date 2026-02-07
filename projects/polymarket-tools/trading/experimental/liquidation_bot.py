#!/usr/bin/env python3
"""
Liquidation Bot - Estimates liquidation clusters and signals cascade opportunities

Strategy:
- Track open interest and funding rates
- Estimate liquidation price clusters
- When price approaches cluster → signal potential cascade
- High leverage + directional OI imbalance = liquidation cascade risk

Data sources: 
- Coinglass API (public endpoints)
- Binance futures API (public market data)
"""

import json
import requests
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

class LiquidationBot:
    def __init__(self, state_file: str = "liquidation_bot_state.json"):
        self.state_file = Path(__file__).parent / state_file
        self.balance = 100.0
        self.position = None
        self.state = self.load_state()
        
        # Thresholds
        self.liquidation_proximity_pct = 2.0  # Signal if price within 2% of cluster
        self.min_liquidation_value = 10_000_000  # $10M minimum cluster size
    
    def load_state(self) -> Dict:
        """Load bot state from file"""
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {
            "last_check_time": None,
            "signals": [],
            "liquidation_history": []
        }
    
    def save_state(self):
        """Save bot state to file"""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def get_btc_price(self) -> Optional[float]:
        """Get current BTC price from Binance"""
        try:
            url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return float(response.json()['price'])
        except Exception as e:
            print(f"[ERROR] Failed to fetch BTC price: {e}")
            return None
    
    def get_funding_rate(self) -> Optional[float]:
        """Get current BTC perpetual funding rate from Binance"""
        try:
            url = "https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&limit=1"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data:
                return float(data[0]['fundingRate'])
            return None
        except Exception as e:
            print(f"[ERROR] Failed to fetch funding rate: {e}")
            return None
    
    def get_open_interest(self) -> Optional[float]:
        """Get current BTC open interest from Binance"""
        try:
            url = "https://fapi.binance.com/fapi/v1/openInterest?symbol=BTCUSDT"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return float(response.json()['openInterest'])
        except Exception as e:
            print(f"[ERROR] Failed to fetch open interest: {e}")
            return None
    
    def estimate_liquidation_clusters(self, current_price: float) -> Dict:
        """
        Estimate where liquidations are likely clustered
        
        Simplified model based on:
        - Typical leverage levels (5x, 10x, 20x, 50x, 100x)
        - Assuming positions opened near recent price levels
        - Price range: ±20% from current
        """
        clusters = {
            'longs': [],  # Long liquidations (price drops)
            'shorts': []  # Short liquidations (price rises)
        }
        
        # Typical leverage levels used by traders
        leverage_levels = [5, 10, 20, 50, 100]
        
        # Estimate entry zones (recent support/resistance approximations)
        # In production, you'd analyze actual order book, volume profile, etc.
        price_ranges = [
            current_price * 0.95,  # 5% below
            current_price * 0.98,  # 2% below
            current_price,          # Current
            current_price * 1.02,   # 2% above
            current_price * 1.05,   # 5% above
        ]
        
        for entry_price in price_ranges:
            for leverage in leverage_levels:
                # Long liquidation price = entry * (1 - 1/leverage)
                long_liq_price = entry_price * (1 - 1/leverage)
                
                # Short liquidation price = entry * (1 + 1/leverage)
                short_liq_price = entry_price * (1 + 1/leverage)
                
                # Assign weight based on leverage popularity (higher leverage = more common)
                weight = leverage * 100000  # Arbitrary scaling
                
                if long_liq_price > current_price * 0.80:  # Within 20% below
                    clusters['longs'].append({
                        'price': long_liq_price,
                        'leverage': leverage,
                        'estimated_value': weight,
                        'entry': entry_price
                    })
                
                if short_liq_price < current_price * 1.20:  # Within 20% above
                    clusters['shorts'].append({
                        'price': short_liq_price,
                        'leverage': leverage,
                        'estimated_value': weight,
                        'entry': entry_price
                    })
        
        # Aggregate clusters by price buckets (1% intervals)
        def bucket_clusters(cluster_list):
            buckets = {}
            for cluster in cluster_list:
                bucket_key = round(cluster['price'], -2)  # Round to nearest 100
                if bucket_key not in buckets:
                    buckets[bucket_key] = 0
                buckets[bucket_key] += cluster['estimated_value']
            return sorted(buckets.items(), key=lambda x: x[1], reverse=True)
        
        return {
            'longs': bucket_clusters(clusters['longs']),
            'shorts': bucket_clusters(clusters['shorts']),
        }
    
    def analyze_liquidation_risk(self, current_price: float, clusters: Dict, funding_rate: float) -> Optional[Dict]:
        """Analyze if price is approaching a liquidation cluster"""
        
        signals = []
        
        # Check long liquidations (downside)
        for price, value in clusters['longs'][:5]:  # Top 5 clusters
            distance_pct = ((current_price - price) / current_price) * 100
            
            if 0 < distance_pct <= self.liquidation_proximity_pct and value >= self.min_liquidation_value:
                signals.append({
                    'direction': 'DOWN',
                    'type': 'LONG_LIQUIDATION_CASCADE',
                    'cluster_price': price,
                    'current_price': current_price,
                    'distance_pct': distance_pct,
                    'estimated_value': value,
                    'funding_rate': funding_rate
                })
        
        # Check short liquidations (upside)
        for price, value in clusters['shorts'][:5]:
            distance_pct = ((price - current_price) / current_price) * 100
            
            if 0 < distance_pct <= self.liquidation_proximity_pct and value >= self.min_liquidation_value:
                signals.append({
                    'direction': 'UP',
                    'type': 'SHORT_LIQUIDATION_CASCADE',
                    'cluster_price': price,
                    'current_price': current_price,
                    'distance_pct': distance_pct,
                    'estimated_value': value,
                    'funding_rate': funding_rate
                })
        
        # Return strongest signal if any
        if signals:
            return max(signals, key=lambda x: x['estimated_value'])
        
        return None
    
    def log_signal(self, signal: Dict):
        """Log liquidation opportunity signal"""
        timestamp = datetime.now().isoformat()
        
        log_entry = {
            'timestamp': timestamp,
            'signal_type': signal['type'],
            'direction': signal['direction'],
            'cluster_price': signal['cluster_price'],
            'current_price': signal['current_price'],
            'distance_pct': signal['distance_pct'],
            'estimated_value': signal['estimated_value'],
            'funding_rate': signal['funding_rate'],
            'balance': self.balance
        }
        
        if 'signals' not in self.state:
            self.state['signals'] = []
        self.state['signals'].append(log_entry)
        
        if len(self.state['signals']) > 50:
            self.state['signals'] = self.state['signals'][-50:]
        
        # Console output
        print(f"\n{'='*70}")
        print(f"[{timestamp}] 💥 LIQUIDATION ALERT - {signal['direction']}")
        print(f"{'='*70}")
        print(f"Type: {signal['type']}")
        print(f"Current Price: ${signal['current_price']:,.2f}")
        print(f"Cluster Price: ${signal['cluster_price']:,.2f}")
        print(f"Distance: {signal['distance_pct']:.2f}%")
        print(f"Est. Liquidation Value: ${signal['estimated_value']:,.0f}")
        print(f"Funding Rate: {signal['funding_rate']*100:.4f}%")
        print(f"Strategy: Price moving {signal['direction']} may trigger cascade")
        print(f"Balance: ${self.balance:.2f}")
        print(f"{'='*70}\n")
    
    def cycle(self):
        """Main bot cycle - check for liquidation opportunities"""
        print(f"[{datetime.now().isoformat()}] Liquidation Bot - Analyzing liquidation clusters...")
        
        # Fetch market data
        current_price = self.get_btc_price()
        funding_rate = self.get_funding_rate()
        open_interest = self.get_open_interest()
        
        if not all([current_price, funding_rate is not None, open_interest]):
            print("[ERROR] Failed to fetch required market data")
            return
        
        print(f"BTC Price: ${current_price:,.2f}")
        print(f"Funding Rate: {funding_rate*100:.4f}%")
        print(f"Open Interest: {open_interest:,.0f} BTC")
        
        # Estimate liquidation clusters
        clusters = self.estimate_liquidation_clusters(current_price)
        
        print(f"\nTop Long Liquidation Clusters (downside):")
        for price, value in clusters['longs'][:3]:
            distance = ((current_price - price) / current_price) * 100
            print(f"  ${price:,.0f} ({distance:+.2f}%) - ${value:,.0f}")
        
        print(f"\nTop Short Liquidation Clusters (upside):")
        for price, value in clusters['shorts'][:3]:
            distance = ((price - current_price) / current_price) * 100
            print(f"  ${price:,.0f} ({distance:+.2f}%) - ${value:,.0f}")
        
        # Analyze risk
        signal = self.analyze_liquidation_risk(current_price, clusters, funding_rate)
        
        if signal:
            self.log_signal(signal)
        else:
            print(f"\nNo liquidation clusters within {self.liquidation_proximity_pct}% threshold")
        
        # Update state
        self.state['last_check_time'] = datetime.now().isoformat()
        self.save_state()
        
        print(f"\nCycle complete. Total signals logged: {len(self.state.get('signals', []))}")


def main():
    """Run bot cycle"""
    bot = LiquidationBot()
    bot.cycle()


if __name__ == "__main__":
    main()
