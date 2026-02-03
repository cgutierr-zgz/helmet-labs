#!/usr/bin/env python3
"""
Polymarket-Kalshi Arbitrage Monitor
Runs continuously and logs opportunities to file.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

import time
import json
from datetime import datetime
from fetch_current_polymarket import fetch_polymarket_data_struct
from fetch_current_kalshi import fetch_kalshi_data_struct

LOG_FILE = os.path.join(os.path.dirname(__file__), 'arb_log.jsonl')
SCAN_INTERVAL = 30  # seconds between scans
MIN_PROFIT_THRESHOLD = 0.01  # $0.01 minimum profit to log

def scan_for_arbitrage():
    """Scan both markets and return any arbitrage opportunities."""
    poly, poly_err = fetch_polymarket_data_struct()
    kalshi, kalshi_err = fetch_kalshi_data_struct()
    
    if poly_err or kalshi_err:
        return None, f"API Error: poly={poly_err}, kalshi={kalshi_err}"
    
    if not poly or not kalshi:
        return None, "No data from APIs"
    
    poly_strike = poly['price_to_beat']
    poly_up = poly['prices'].get('Up', 0)
    poly_down = poly['prices'].get('Down', 0)
    
    opportunities = []
    best_profit = -1
    best_opp = None
    
    for m in kalshi.get('markets', []):
        ks = m['strike']
        yes = m['yes_ask'] / 100.0
        no = m['no_ask'] / 100.0
        
        # Strategy 1: Poly Down + Kalshi Yes (when poly_strike > kalshi_strike)
        if poly_strike > ks:
            cost = poly_down + yes
            profit = 1.0 - cost
            if profit > MIN_PROFIT_THRESHOLD:
                opp = {
                    'strategy': 'Poly Down + Kalshi Yes',
                    'poly_strike': poly_strike,
                    'kalshi_strike': ks,
                    'poly_cost': poly_down,
                    'kalshi_cost': yes,
                    'total_cost': cost,
                    'profit': profit,
                    'profit_pct': profit * 100
                }
                opportunities.append(opp)
                if profit > best_profit:
                    best_profit = profit
                    best_opp = opp
        
        # Strategy 2: Poly Up + Kalshi No (when poly_strike < kalshi_strike)
        if poly_strike < ks:
            cost = poly_up + no
            profit = 1.0 - cost
            if profit > MIN_PROFIT_THRESHOLD:
                opp = {
                    'strategy': 'Poly Up + Kalshi No',
                    'poly_strike': poly_strike,
                    'kalshi_strike': ks,
                    'poly_cost': poly_up,
                    'kalshi_cost': no,
                    'total_cost': cost,
                    'profit': profit,
                    'profit_pct': profit * 100
                }
                opportunities.append(opp)
                if profit > best_profit:
                    best_profit = profit
                    best_opp = opp
    
    # Also track "closest to profitable" for logging
    closest_cost = 999
    for m in kalshi.get('markets', []):
        ks = m['strike']
        yes = m['yes_ask'] / 100.0
        no = m['no_ask'] / 100.0
        
        if poly_strike > ks:
            cost = poly_down + yes
        else:
            cost = poly_up + no
        
        if cost < closest_cost:
            closest_cost = cost
    
    return {
        'timestamp': datetime.now().isoformat(),
        'poly_strike': poly_strike,
        'poly_up': poly_up,
        'poly_down': poly_down,
        'kalshi_markets': len(kalshi.get('markets', [])),
        'opportunities': len(opportunities),
        'best_opportunity': best_opp,
        'closest_cost': closest_cost,
        'gap_to_profit': max(0, closest_cost - 1.0)
    }, None

def main():
    print(f"🔍 Arbitrage Monitor started at {datetime.now().isoformat()}")
    print(f"📝 Logging to: {LOG_FILE}")
    print(f"⏱️  Scanning every {SCAN_INTERVAL}s")
    print(f"💰 Min profit threshold: ${MIN_PROFIT_THRESHOLD}")
    print("-" * 50)
    
    scan_count = 0
    opportunity_count = 0
    
    while True:
        try:
            result, error = scan_for_arbitrage()
            scan_count += 1
            
            if error:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ {error}")
            elif result:
                # Log to file
                with open(LOG_FILE, 'a') as f:
                    f.write(json.dumps(result) + '\n')
                
                if result['opportunities'] > 0:
                    opportunity_count += result['opportunities']
                    best = result['best_opportunity']
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚨 ARBITRAGE FOUND!")
                    print(f"   {best['strategy']}")
                    print(f"   Poly ${best['poly_strike']:.0f} vs Kalshi ${best['kalshi_strike']:.0f}")
                    print(f"   Cost: ${best['total_cost']:.3f} -> Profit: ${best['profit']:.3f} ({best['profit_pct']:.1f}%)")
                else:
                    gap = result['gap_to_profit']
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] No arb. Gap: ${gap:.3f} | Scans: {scan_count} | Opps found: {opportunity_count}")
            
            time.sleep(SCAN_INTERVAL)
            
        except KeyboardInterrupt:
            print(f"\n\n📊 Final stats: {scan_count} scans, {opportunity_count} opportunities found")
            break
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ Error: {e}")
            time.sleep(SCAN_INTERVAL)

if __name__ == '__main__':
    main()
