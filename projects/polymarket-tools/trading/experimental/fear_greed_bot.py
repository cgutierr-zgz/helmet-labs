#!/usr/bin/env python3
"""
Fear & Greed Bot - Contrarian trading based on market sentiment

Strategy: Be greedy when others are fearful, fearful when others are greedy
- Index <20 (Extreme Fear) → Market oversold → Bet BULLISH
- Index >80 (Extreme Greed) → Market overbought → Bet BEARISH
"""

import requests
import json
from datetime import datetime
from pathlib import Path

STATE_FILE = Path(__file__).parent / "state_fear_greed.json"
STARTING_BALANCE = 100.0

# Fear & Greed Index API
FEAR_GREED_URL = "https://api.alternative.me/fng/"

# Thresholds
EXTREME_FEAR = 20
EXTREME_GREED = 80


class FearGreedBot:
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
            "last_check": None,
            "last_index": None
        }
    
    def save_state(self):
        """Save current state to disk"""
        with open(STATE_FILE, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def get_fear_greed_index(self):
        """Fetch current Fear & Greed Index"""
        try:
            params = {"limit": 1}
            response = requests.get(FEAR_GREED_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("data"):
                item = data["data"][0]
                return {
                    "value": int(item["value"]),
                    "classification": item["value_classification"],
                    "timestamp": int(item["timestamp"]),
                    "time_until_update": item.get("time_until_update")
                }
            return None
        except Exception as e:
            print(f"❌ Error fetching Fear & Greed Index: {e}")
            return None
    
    def get_sentiment_emoji(self, value):
        """Get emoji based on index value"""
        if value <= 20:
            return "😱"  # Extreme Fear
        elif value <= 40:
            return "😰"  # Fear
        elif value <= 60:
            return "😐"  # Neutral
        elif value <= 80:
            return "😊"  # Greed
        else:
            return "🤑"  # Extreme Greed
    
    def analyze_signal(self, index_data):
        """Analyze Fear & Greed Index and generate trading signal"""
        if not index_data:
            return None
        
        value = index_data["value"]
        classification = index_data["classification"]
        emoji = self.get_sentiment_emoji(value)
        
        signal = {
            "timestamp": datetime.now().isoformat(),
            "index_value": value,
            "classification": classification,
            "action": None,
            "reasoning": ""
        }
        
        if value < EXTREME_FEAR:
            signal["action"] = "LONG"
            signal["reasoning"] = (
                f"{emoji} EXTREME FEAR DETECTED (Index: {value}/100)\n"
                f"Market sentiment: {classification}\n"
                f"Contrarian signal: Everyone is panicking → Oversold conditions\n"
                f"→ Bet BULLISH on Polymarket BTC/ETH markets\n"
                f"\"Be greedy when others are fearful\" - Warren Buffett"
            )
        
        elif value > EXTREME_GREED:
            signal["action"] = "SHORT"
            signal["reasoning"] = (
                f"{emoji} EXTREME GREED DETECTED (Index: {value}/100)\n"
                f"Market sentiment: {classification}\n"
                f"Contrarian signal: Everyone is euphoric → Overbought conditions\n"
                f"→ Bet BEARISH on Polymarket BTC/ETH markets\n"
                f"\"Be fearful when others are greedy\" - Warren Buffett"
            )
        
        else:
            signal["reasoning"] = (
                f"{emoji} Neutral sentiment (Index: {value}/100)\n"
                f"Market sentiment: {classification}\n"
                f"No extreme detected, waiting for better entry"
            )
        
        return signal
    
    def log_signal(self, signal):
        """Log trading signal with clear reasoning"""
        print("\n" + "="*60)
        print(f"⏰ {signal['timestamp']}")
        print(f"📊 Fear & Greed Index: {signal['index_value']}/100")
        print(f"🏷️  Classification: {signal['classification']}")
        print("-"*60)
        print(signal['reasoning'])
        
        if signal['action']:
            print(f"\n🎯 SIGNAL: {signal['action']}")
            print(f"💵 Would allocate: $15 (15% of ${self.state['balance']:.2f})")
            print(f"📝 Paper trade only - NOT executing")
        
        print("="*60 + "\n")
    
    def cycle(self):
        """Main cycle - check Fear & Greed Index and generate signals"""
        print(f"\n🤖 Fear & Greed Bot - Cycle started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"💰 Current balance: ${self.state['balance']:.2f}")
        
        print(f"\n🔍 Fetching Fear & Greed Index...")
        index_data = self.get_fear_greed_index()
        
        if index_data:
            signal = self.analyze_signal(index_data)
            self.log_signal(signal)
            
            # Save signal to trades history
            if signal['action']:
                self.state['trades'].append(signal)
            
            # Update last index
            self.state['last_index'] = index_data['value']
        
        # Update last check time
        self.state['last_check'] = datetime.now().isoformat()
        self.save_state()
        
        print(f"✅ Cycle complete. Fear & Greed Index updates daily.\n")


def main():
    """Run a single cycle"""
    bot = FearGreedBot()
    bot.cycle()


if __name__ == "__main__":
    main()
