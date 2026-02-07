#!/usr/bin/env python3
"""
Volume Spike Bot - Momentum/reversal trading based on volume anomalies

Strategy: Abnormal volume = Something is happening
- High volume (>3x avg) + price up → Real momentum → Bet continuation (LONG)
- High volume (>3x avg) + price flat/down → Distribution → Bet reversal (SHORT)
"""

import requests
import json
from datetime import datetime
from pathlib import Path

STATE_FILE = Path(__file__).parent / "state_volume_spike.json"
STARTING_BALANCE = 100.0

# Binance API endpoints
BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"

# Thresholds
VOLUME_SPIKE_MULTIPLIER = 3.0  # 3x average volume
PRICE_UP_THRESHOLD = 0.01  # 1% price increase


class VolumeSpikeBot:
    def __init__(self):
        self.state = self.load_state()
    
    def load_state(self):
        """Load bot state or initialize if doesn't exist"""
        if STATE_FILE.exists():
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        return {
            "balance": STARTING_BALANCE,
            "positions": [],
            "trades": [],
            "last_check": None
        }
    
    def save_state(self):
        """Save current state to disk"""
        with open(STATE_FILE, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def get_volume_data(self, symbol, interval="15m", limit=96):
        """
        Get volume data from Binance
        - interval: 15m (current candle)
        - limit: 96 = 24 hours of 15m candles
        """
        try:
            params = {
                "symbol": symbol,
                "interval": interval,
                "limit": limit
            }
            response = requests.get(BINANCE_KLINES_URL, params=params, timeout=10)
            response.raise_for_status()
            klines = response.json()
            
            # Parse klines: [open_time, open, high, low, close, volume, ...]
            candles = []
            for k in klines:
                candles.append({
                    "timestamp": k[0],
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5])
                })
            
            return candles
        except Exception as e:
            print(f"❌ Error fetching volume data for {symbol}: {e}")
            return None
    
    def analyze_signal(self, symbol, candles):
        """Analyze volume spike and price action"""
        if not candles or len(candles) < 2:
            return None
        
        # Current (most recent) candle
        current = candles[-1]
        
        # Calculate 24h average volume (excluding current candle)
        historical_volumes = [c["volume"] for c in candles[:-1]]
        avg_volume = sum(historical_volumes) / len(historical_volumes)
        
        # Volume spike ratio
        volume_ratio = current["volume"] / avg_volume if avg_volume > 0 else 0
        
        # Price change in current candle
        price_change_pct = ((current["close"] - current["open"]) / current["open"]) * 100
        
        signal = {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "current_volume": current["volume"],
            "avg_volume": avg_volume,
            "volume_ratio": volume_ratio,
            "current_price": current["close"],
            "price_change_pct": price_change_pct,
            "action": None,
            "reasoning": ""
        }
        
        # Detect volume spike
        if volume_ratio > VOLUME_SPIKE_MULTIPLIER:
            if price_change_pct > PRICE_UP_THRESHOLD:
                # High volume + price up = Momentum
                signal["action"] = "LONG"
                signal["reasoning"] = (
                    f"🚀 VOLUME SPIKE + BULLISH MOMENTUM\n"
                    f"Volume: {volume_ratio:.2f}x average ({current['volume']:,.0f} vs {avg_volume:,.0f})\n"
                    f"Price: +{price_change_pct:.2f}% (${current['close']:,.2f})\n"
                    f"Analysis: HIGH VOLUME ON UPSIDE = Real momentum, not fake pump\n"
                    f"→ Bet CONTINUATION (LONG) on Polymarket {symbol.replace('USDT', '')} markets"
                )
            
            elif price_change_pct < -PRICE_UP_THRESHOLD:
                # High volume + price down = Panic/distribution
                signal["action"] = "SHORT"
                signal["reasoning"] = (
                    f"📉 VOLUME SPIKE + BEARISH PRESSURE\n"
                    f"Volume: {volume_ratio:.2f}x average ({current['volume']:,.0f} vs {avg_volume:,.0f})\n"
                    f"Price: {price_change_pct:.2f}% (${current['close']:,.2f})\n"
                    f"Analysis: HIGH VOLUME ON DOWNSIDE = Distribution/panic selling\n"
                    f"→ Bet REVERSAL/SHORT on Polymarket {symbol.replace('USDT', '')} markets"
                )
            
            else:
                # High volume + flat price = Distribution (bearish)
                signal["action"] = "SHORT"
                signal["reasoning"] = (
                    f"⚠️ VOLUME SPIKE + FLAT PRICE (Distribution)\n"
                    f"Volume: {volume_ratio:.2f}x average ({current['volume']:,.0f} vs {avg_volume:,.0f})\n"
                    f"Price: {price_change_pct:+.2f}% (${current['close']:,.2f})\n"
                    f"Analysis: HIGH VOLUME but price not moving = Sellers absorbing demand\n"
                    f"→ Bet SHORT on Polymarket {symbol.replace('USDT', '')} markets"
                )
        
        else:
            signal["reasoning"] = (
                f"ℹ️  Normal volume ({volume_ratio:.2f}x average)\n"
                f"Price: {price_change_pct:+.2f}% (${current['close']:,.2f})\n"
                f"No volume anomaly detected, waiting for spike"
            )
        
        return signal
    
    def log_signal(self, signal):
        """Log trading signal with clear reasoning"""
        print("\n" + "="*60)
        print(f"⏰ {signal['timestamp']}")
        print(f"📊 {signal['symbol']} @ ${signal['current_price']:,.2f}")
        print(f"📈 Volume Ratio: {signal['volume_ratio']:.2f}x")
        print(f"💹 Price Change: {signal['price_change_pct']:+.2f}%")
        print("-"*60)
        print(signal['reasoning'])
        
        if signal['action']:
            print(f"\n🎯 SIGNAL: {signal['action']}")
            print(f"💵 Would allocate: $12 (12% of ${self.state['balance']:.2f})")
            print(f"📝 Paper trade only - NOT executing")
        
        print("="*60 + "\n")
    
    def cycle(self):
        """Main cycle - check volume spikes and generate signals"""
        print(f"\n🤖 Volume Spike Bot - Cycle started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"💰 Current balance: ${self.state['balance']:.2f}")
        
        # Check BTC volume (can add ETH later)
        symbol = "BTCUSDT"
        
        print(f"\n🔍 Checking {symbol} volume (15m candles, 24h average)...")
        candles = self.get_volume_data(symbol, interval="15m", limit=96)
        
        if candles:
            signal = self.analyze_signal(symbol, candles)
            self.log_signal(signal)
            
            # Save signal to trades history
            if signal['action']:
                self.state['trades'].append(signal)
        
        # Update last check time
        self.state['last_check'] = datetime.now().isoformat()
        self.save_state()
        
        print(f"✅ Cycle complete. Check every 15-30 minutes for new volume data.\n")


def main():
    """Run a single cycle"""
    bot = VolumeSpikeBot()
    bot.cycle()


if __name__ == "__main__":
    main()
