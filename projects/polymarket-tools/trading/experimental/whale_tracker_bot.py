#!/usr/bin/env python3
"""
Whale Tracker Bot - Detects large BTC transactions and signals market sentiment

Strategy:
- Large exchange inflows (>500 BTC) = selling pressure → BEARISH
- Large exchange outflows (>500 BTC) = accumulation → BULLISH

Data source: Blockchair.com API (public, no auth required)
"""

import json
import requests
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

class WhaleTrackerBot:
    def __init__(self, state_file: str = "whale_tracker_state.json"):
        self.state_file = Path(__file__).parent / state_file
        self.balance = 100.0
        self.position = None  # "long", "short", or None
        self.threshold_btc = 500  # Minimum BTC for whale detection
        self.state = self.load_state()
        
        # Known exchange addresses (sample - expand this list)
        self.exchange_addresses = {
            # Binance cold wallets
            "34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo": "Binance",
            "bc1qm34lsc65zpw79lxes69zkqmk6ee3ewf0j77s3h": "Binance",
            # Coinbase
            "3D2oetdNuZUqQHPJmcMDDHYoqkyNVsFk9r": "Coinbase",
            # Kraken
            "3HRxHcqFhP8WqXZGgGr5LmLgLTd9kdUkRV": "Kraken",
            # Add more known addresses as identified
        }
    
    def load_state(self) -> Dict:
        """Load bot state from file"""
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {
            "last_check_time": None,
            "signals": [],
            "tracked_txs": []
        }
    
    def save_state(self):
        """Save bot state to file"""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def fetch_recent_large_transactions(self) -> List[Dict]:
        """
        Fetch recent large BTC transactions using blockchain.com API
        Public API, no authentication required
        """
        try:
            # Use blockchain.com unconfirmed transactions endpoint
            # This shows recent mempool transactions
            url = "https://blockchain.info/unconfirmed-transactions?format=json"
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            txs = data.get('txs', [])
            
            large_txs = []
            
            for tx in txs:
                tx_hash = tx.get('hash')
                
                # Skip if already tracked
                if tx_hash in self.state.get('tracked_txs', []):
                    continue
                
                # Calculate total output in BTC
                outputs = tx.get('out', [])
                total_output_satoshi = sum(out.get('value', 0) for out in outputs)
                total_output_btc = total_output_satoshi / 1e8
                
                if total_output_btc >= self.threshold_btc:
                    large_txs.append({
                        'hash': tx_hash,
                        'btc_amount': total_output_btc,
                        'time': tx.get('time'),
                        'outputs': outputs,
                        'size': tx.get('size'),
                        'fee': tx.get('fee', 0) / 1e8
                    })
                    
                    # Mark as tracked
                    if 'tracked_txs' not in self.state:
                        self.state['tracked_txs'] = []
                    self.state['tracked_txs'].append(tx_hash)
            
            # Keep only last 100 tracked tx hashes to prevent state bloat
            if len(self.state.get('tracked_txs', [])) > 100:
                self.state['tracked_txs'] = self.state['tracked_txs'][-100:]
            
            return large_txs
            
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to fetch transactions from blockchain.info: {e}")
            print("[INFO] API might be rate-limited. Try again in a few minutes.")
            return []
        except Exception as e:
            print(f"[ERROR] Unexpected error: {e}")
            return []
    
    def analyze_transaction(self, tx: Dict) -> Optional[Dict]:
        """
        Analyze if transaction is exchange-related and determine direction
        
        Returns signal dict or None
        """
        # This is simplified - in production, you'd need more sophisticated
        # address classification (on-chain clustering, known exchange wallets, etc.)
        
        # For now, we'll look for patterns in outputs
        outputs = tx.get('outputs', [])
        
        # Heuristic: Multiple small outputs = likely exchange withdrawal (bullish)
        # Single large output = likely exchange deposit (bearish)
        
        if len(outputs) > 5:
            # Many outputs suggests exchange withdrawal/distribution
            signal_type = "BULLISH"
            reason = f"Whale withdrawal detected: {tx['btc_amount']:.2f} BTC likely leaving exchange"
        elif len(outputs) <= 2:
            # Few outputs suggests consolidation/deposit
            signal_type = "BEARISH"
            reason = f"Whale deposit detected: {tx['btc_amount']:.2f} BTC likely moving to exchange"
        else:
            # Ambiguous
            return None
        
        return {
            'type': signal_type,
            'amount_btc': tx['btc_amount'],
            'reason': reason,
            'tx_hash': tx['hash'],
            'timestamp': tx['time']
        }
    
    def log_signal(self, signal: Dict):
        """Log trading signal"""
        timestamp = datetime.now().isoformat()
        
        log_entry = {
            'timestamp': timestamp,
            'signal_type': signal['type'],
            'amount_btc': signal['amount_btc'],
            'reason': signal['reason'],
            'tx_hash': signal['tx_hash'],
            'tx_time': signal['timestamp'],
            'balance': self.balance
        }
        
        # Append to state
        if 'signals' not in self.state:
            self.state['signals'] = []
        self.state['signals'].append(log_entry)
        
        # Keep only last 50 signals
        if len(self.state['signals']) > 50:
            self.state['signals'] = self.state['signals'][-50:]
        
        # Console output
        print(f"\n{'='*70}")
        print(f"[{timestamp}] 🐋 WHALE ALERT - {signal['type']}")
        print(f"{'='*70}")
        print(f"Amount: {signal['amount_btc']:.2f} BTC")
        print(f"Signal: {signal['reason']}")
        print(f"TX: {signal['tx_hash'][:16]}...")
        print(f"Balance: ${self.balance:.2f}")
        print(f"{'='*70}\n")
    
    def cycle(self):
        """Main bot cycle - check for whale movements and log signals"""
        print(f"[{datetime.now().isoformat()}] Whale Tracker Bot - Checking for large transactions...")
        
        # Fetch recent large transactions
        large_txs = self.fetch_recent_large_transactions()
        
        if not large_txs:
            print(f"No new whale transactions detected (>{self.threshold_btc} BTC)")
            self.state['last_check_time'] = datetime.now().isoformat()
            self.save_state()
            return
        
        print(f"Found {len(large_txs)} large transaction(s)!")
        
        # Analyze each transaction
        for tx in large_txs:
            signal = self.analyze_transaction(tx)
            if signal:
                self.log_signal(signal)
        
        # Update state
        self.state['last_check_time'] = datetime.now().isoformat()
        self.save_state()
        
        print(f"Cycle complete. Total signals logged: {len(self.state.get('signals', []))}")


def main():
    """Run bot cycle"""
    bot = WhaleTrackerBot()
    bot.cycle()


if __name__ == "__main__":
    main()
