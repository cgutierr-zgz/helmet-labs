#!/usr/bin/env python3
"""
Funding Rate Bot - Contrarian trading based on perpetual funding rates

Strategy: Extreme funding rates often precede reversals
- High positive funding (>0.05%) → Longs overextended → Bet SHORT/DOWN
- High negative funding → Shorts overextended → Bet LONG/UP
"""

import requests
import json
import time
from datetime import datetime
from pathlib import Path

STATE_FILE = Path(__file__).parent / "state_funding_rate.json"
STARTING_BALANCE = 100.0

# Binance API endpoints
BINANCE_FUNDING_URL = "https://fapi.binance.com/fapi/v1/premiumIndex"

# Thresholds
EXTREME_POSITIVE_FUNDING = 0.0005  # 0.05%
EXTREME_NEGATIVE_FUNDING = -0.0005  # -0.05%


class FundingRateBot:
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
    
    def get_funding_rate(self, symbol):
        """Get current funding rate for a symbol from Binance"""
        try:
            params = {"symbol": symbol}
            response = requests.get(BINANCE_FUNDING_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            return {
                "symbol": data["symbol"],
                "funding_rate": float(data["lastFundingRate"]),
                "next_funding_time": data["nextFundingTime"],
                "mark_price": float(data["markPrice"])
            }
        except Exception as e:
            print(f"❌ Error fetching funding rate for {symbol}: {e}")
            return None
    
    def analyze_signal(self, symbol, funding_data):
        """Analyze funding rate and generate trading signal"""
        if not funding_data:
            return None
        
        funding_rate = funding_data["funding_rate"]
        mark_price = funding_data["mark_price"]
        
        # Convert funding rate to percentage for display
        funding_pct = funding_rate * 100
        
        signal = {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "funding_rate": funding_rate,
            "funding_pct": funding_pct,
            "mark_price": mark_price,
            "action": None,
            "reasoning": ""
        }
        
        if funding_rate > EXTREME_POSITIVE_FUNDING:
            signal["action"] = "SHORT"
            signal["reasoning"] = (
                f"🔴 EXTREME POSITIVE FUNDING ({funding_pct:.3f}%)\n"
                f"Longs are paying shorts heavily → Market is overextended to the upside\n"
                f"→ Bet DOWN/SHORT on Polymarket {symbol.replace('USDT', '')} markets"
            )
        
        elif funding_rate < EXTREME_NEGATIVE_FUNDING:
            signal["action"] = "LONG"
            signal["reasoning"] = (
                f"🟢 EXTREME NEGATIVE FUNDING ({funding_pct:.3f}%)\n"
                f"Shorts are paying longs heavily → Market is overextended to the downside\n"
                f"→ Bet UP/LONG on Polymarket {symbol.replace('USDT', '')} markets"
            )
        
        else:
            signal["reasoning"] = (
                f"ℹ️  Neutral funding rate ({funding_pct:.3f}%)\n"
                f"Within normal range, no extreme positioning detected"
            )
        
        return signal
    
    def log_signal(self, signal):
        """Log trading signal with clear reasoning"""
        print("\n" + "="*60)
        print(f"⏰ {signal['timestamp']}")
        print(f"📊 {signal['symbol']} @ ${signal['mark_price']:,.2f}")
        print(f"💰 Funding Rate: {signal['funding_pct']:.3f}%")
        print("-"*60)
        print(signal['reasoning'])
        
        if signal['action']:
            print(f"\n🎯 SIGNAL: {signal['action']}")
            print(f"💵 Would allocate: $10 (10% of ${self.state['balance']:.2f})")
            print(f"📝 Paper trade only - NOT executing")
        
        print("="*60 + "\n")
    
    def cycle(self):
        """Main cycle - check funding rates and generate signals"""
        print(f"\n🤖 Funding Rate Bot - Cycle started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"💰 Current balance: ${self.state['balance']:.2f}")
        
        # Check BTC and ETH funding rates
        symbols = ["BTCUSDT", "ETHUSDT"]
        
        for symbol in symbols:
            print(f"\n🔍 Checking {symbol}...")
            funding_data = self.get_funding_rate(symbol)
            
            if funding_data:
                signal = self.analyze_signal(symbol, funding_data)
                self.log_signal(signal)
                
                # Save signal to trades history
                if signal['action']:
                    self.state['trades'].append(signal)
        
        # Update last check time
        self.state['last_check'] = datetime.now().isoformat()
        self.save_state()
        
        print(f"✅ Cycle complete. Next check in 1 hour (funding updates every 8h)\n")


def main():
    """Run a single cycle"""
    bot = FundingRateBot()
    bot.cycle()


if __name__ == "__main__":
    main()
