#!/usr/bin/env python3
"""
Monitor a webpage for changes and alert when content updates.
"""
import argparse
import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path

# Import scrape functions
sys.path.insert(0, str(Path(__file__).parent))
from scrape import fetch_http, fetch_browser, extract_by_selector

def get_content_hash(content: list) -> str:
    """Get hash of content for comparison."""
    return hashlib.md5(json.dumps(sorted(content)).encode()).hexdigest()

def find_changes(old: list, new: list) -> dict:
    """Find what changed between old and new content."""
    old_set = set(old)
    new_set = set(new)
    
    return {
        'added': list(new_set - old_set),
        'removed': list(old_set - new_set),
        'unchanged': len(old_set & new_set)
    }

def main():
    parser = argparse.ArgumentParser(description='Monitor webpage for changes')
    parser.add_argument('url', help='URL to monitor')
    parser.add_argument('-s', '--selector', default='body', help='CSS selector to watch')
    parser.add_argument('-i', '--interval', type=int, default=60, help='Check interval (seconds)')
    parser.add_argument('-b', '--browser', action='store_true', help='Use browser')
    parser.add_argument('-o', '--output', help='Log changes to file')
    parser.add_argument('--diff', action='store_true', help='Show what changed')
    parser.add_argument('--alert', action='store_true', help='Print alert on change')
    parser.add_argument('--once', action='store_true', help='Check once and exit')
    parser.add_argument('--wait', type=int, default=2, help='Wait seconds for JS')
    
    args = parser.parse_args()
    
    print(f"🔍 Monitoring: {args.url}")
    print(f"📍 Selector: {args.selector}")
    print(f"⏱️  Interval: {args.interval}s")
    print("-" * 50)
    
    last_content = None
    last_hash = None
    check_count = 0
    
    while True:
        try:
            check_count += 1
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Fetch content
            if args.browser:
                html = fetch_browser(args.url, args.wait)
            else:
                html = fetch_http(args.url)
            
            content = extract_by_selector(html, args.selector)
            content_hash = get_content_hash(content)
            
            # First check - establish baseline
            if last_hash is None:
                print(f"[{timestamp}] ✅ Baseline: {len(content)} items")
                last_content = content
                last_hash = content_hash
                
                if args.once:
                    print(json.dumps(content, indent=2, ensure_ascii=False))
                    break
                    
                time.sleep(args.interval)
                continue
            
            # Check for changes
            if content_hash != last_hash:
                changes = find_changes(last_content, content)
                
                # Alert
                if args.alert:
                    print(f"\n[{timestamp}] 🚨 CHANGE DETECTED!")
                    print(f"   Added: {len(changes['added'])} | Removed: {len(changes['removed'])}")
                
                # Show diff
                if args.diff and changes['added']:
                    print("   New items:")
                    for item in changes['added'][:5]:
                        print(f"   + {item[:100]}")
                    if len(changes['added']) > 5:
                        print(f"   ... and {len(changes['added'])-5} more")
                
                # Log to file
                if args.output:
                    log_entry = {
                        'timestamp': timestamp,
                        'url': args.url,
                        'added': changes['added'],
                        'removed': changes['removed']
                    }
                    with open(args.output, 'a') as f:
                        f.write(json.dumps(log_entry) + '\n')
                
                last_content = content
                last_hash = content_hash
            else:
                print(f"[{timestamp}] ✓ No change (check #{check_count})")
            
            if args.once:
                break
                
            time.sleep(args.interval)
            
        except KeyboardInterrupt:
            print("\n\n👋 Monitoring stopped")
            break
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ Error: {e}")
            time.sleep(args.interval)

if __name__ == '__main__':
    main()
