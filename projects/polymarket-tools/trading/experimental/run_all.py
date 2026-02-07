#!/usr/bin/env python3
"""
Test runner for all experimental trading bots
"""

import subprocess
import sys
from pathlib import Path

def run_bot(bot_name: str):
    """Run a single bot and display output"""
    print(f"\n{'='*80}")
    print(f"Running {bot_name}...")
    print(f"{'='*80}\n")
    
    bot_path = Path(__file__).parent / bot_name
    
    try:
        result = subprocess.run(
            [sys.executable, str(bot_path)],
            capture_output=False,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            print(f"\n[WARNING] {bot_name} exited with code {result.returncode}")
        
    except subprocess.TimeoutExpired:
        print(f"\n[ERROR] {bot_name} timed out after 60 seconds")
    except Exception as e:
        print(f"\n[ERROR] Failed to run {bot_name}: {e}")

def main():
    """Run all experimental bots sequentially"""
    bots = [
        'whale_tracker_bot.py',
        'liquidation_bot.py',
        'correlation_bot.py'
    ]
    
    print("Experimental Trading Bots - Test Runner")
    print(f"Testing {len(bots)} bots...\n")
    
    for bot in bots:
        run_bot(bot)
    
    print(f"\n{'='*80}")
    print("All bots completed!")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    main()
