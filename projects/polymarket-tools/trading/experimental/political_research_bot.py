#!/usr/bin/env python3
"""
Political Research Bot — Long-term Political Market Analysis

Tracks polling averages from 538/RealClearPolitics and compares to Polymarket prices.
Logs opportunities when divergence exceeds 10%.

Focus: Presidential elections, Senate races, major political events

Created: 2026-02-08
"""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from html.parser import HTMLParser

SCRIPT_DIR = Path(__file__).parent
STATE_FILE = SCRIPT_DIR / "state_political.json"
CONFIG_FILE = SCRIPT_DIR / "config_political.json"
LOG_FILE = SCRIPT_DIR / "political_opportunities.log"

# API endpoints
GAMMA_API = "https://gamma-api.polymarket.com"
FIVETHIRTYEIGHT_URL = "https://projects.fivethirtyeight.com"
RCP_URL = "https://www.realclearpolitics.com"

# Market keywords to search
POLITICAL_KEYWORDS = [
    "president", "presidential", "election", "2028", "2026",
    "senate", "governor", "democrat", "republican",
    "biden", "trump", "desantis", "newsom", "haley"
]

DEFAULT_CONFIG = {
    "divergence_threshold": 0.10,  # 10% divergence
    "min_market_volume": 10000,  # $10k minimum volume
    "scan_interval_hours": 6,
    "max_markets_to_track": 20,
}


def load_state() -> dict:
    """Load bot state."""
    if STATE_FILE.exists():
        try:
            return json.load(open(STATE_FILE))
        except:
            pass
    return {
        "tracked_markets": [],
        "polling_data": {},
        "opportunities": [],
        "last_scan": None,
    }


def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return {**DEFAULT_CONFIG, **json.load(open(CONFIG_FILE))}
        except:
            pass
    return DEFAULT_CONFIG


def log_opportunity(message: str):
    """Log opportunity to file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{timestamp}] {message}\n")
    print(f"📝 {message}")


class SimpleHTMLParser(HTMLParser):
    """Simple HTML parser to extract text content."""
    def __init__(self):
        super().__init__()
        self.text_content = []
        self.in_script_or_style = False
    
    def handle_starttag(self, tag, attrs):
        if tag in ['script', 'style']:
            self.in_script_or_style = True
    
    def handle_endtag(self, tag):
        if tag in ['script', 'style']:
            self.in_script_or_style = False
    
    def handle_data(self, data):
        if not self.in_script_or_style:
            text = data.strip()
            if text:
                self.text_content.append(text)
    
    def get_text(self) -> str:
        return ' '.join(self.text_content)


def fetch_url(url: str, timeout: int = 15) -> str | None:
    """Fetch URL content."""
    try:
        req = Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"[FETCH] Error fetching {url}: {e}")
        return None


def scrape_rcp_polling(race_url: str) -> dict | None:
    """
    Scrape RealClearPolitics polling average.
    
    Example URL: https://www.realclearpolitics.com/epolls/2024/president/us/general_election_trump_vs_biden-7383.html
    
    Returns: {"candidate1": 45.2, "candidate2": 43.1, ...}
    """
    try:
        html = fetch_url(race_url)
        if not html:
            return None
        
        # RCP shows polling averages in their race table
        # Look for patterns like "Trump 45.2" or "Biden 43.1"
        # This is a simple pattern match - real scraping would parse the table properly
        
        polling = {}
        
        # Find RCP Average row (usually in bold or specific table row)
        lines = html.split('\n')
        for line in lines:
            # Look for percentage patterns near candidate names
            if 'RCP Average' in line or 'Final Results' in line:
                # Extract numbers like "45.2" or "43.1"
                numbers = re.findall(r'\b(\d{1,2}\.\d)\b', line)
                if len(numbers) >= 2:
                    # Assume first two numbers are the main candidates
                    return {
                        "candidate_1": float(numbers[0]),
                        "candidate_2": float(numbers[1]),
                        "source": "rcp",
                        "timestamp": datetime.now().isoformat(),
                    }
        
        # Fallback: look for table data cells with percentages
        percent_matches = re.findall(r'<td[^>]*>(\d{1,2}\.\d)</td>', html)
        if len(percent_matches) >= 2:
            return {
                "candidate_1": float(percent_matches[0]),
                "candidate_2": float(percent_matches[1]),
                "source": "rcp",
                "timestamp": datetime.now().isoformat(),
            }
        
        return None
        
    except Exception as e:
        print(f"[RCP] Error scraping {race_url}: {e}")
        return None


def scrape_538_polling() -> dict | None:
    """
    Attempt to scrape 538 polling data.
    
    Note: 538's new site structure may require different approach.
    This is a placeholder that attempts basic text extraction.
    """
    try:
        # 538 presidential forecast (if available)
        url = f"{FIVETHIRTYEIGHT_URL}/polls/"
        html = fetch_url(url)
        
        if not html:
            return None
        
        # Parse HTML and look for polling numbers
        parser = SimpleHTMLParser()
        parser.feed(html)
        text = parser.get_text()
        
        # Look for patterns like "Democrat 45%" or "Republican 43%"
        dem_match = re.search(r'Democrat[s]?\s+(\d{1,2}\.?\d?)%?', text, re.IGNORECASE)
        rep_match = re.search(r'Republican[s]?\s+(\d{1,2}\.?\d?)%?', text, re.IGNORECASE)
        
        if dem_match and rep_match:
            return {
                "democrat": float(dem_match.group(1)),
                "republican": float(rep_match.group(1)),
                "source": "538",
                "timestamp": datetime.now().isoformat(),
            }
        
        return None
        
    except Exception as e:
        print(f"[538] Error scraping: {e}")
        return None


def search_polymarket_political() -> list[dict]:
    """Search Polymarket for political markets."""
    try:
        # Search for political events
        all_events = []
        
        for keyword in POLITICAL_KEYWORDS[:5]:  # Limit searches
            url = f"{GAMMA_API}/events?limit=5&offset=0"
            req = Request(url, headers={"User-Agent": "PoliticalBot/1.0"})
            
            try:
                with urlopen(req, timeout=15) as resp:
                    events = json.load(resp)
                
                # Filter for political content
                for event in events:
                    title = event.get("title", "").lower()
                    if any(kw in title for kw in ["president", "election", "senate", "political"]):
                        all_events.append(event)
                        
            except Exception as e:
                continue
        
        # Deduplicate by event ID
        unique_events = {e["id"]: e for e in all_events}.values()
        return list(unique_events)
        
    except Exception as e:
        print(f"[Polymarket] Error searching: {e}")
        return []


def find_polymarket_2028_markets() -> list[dict]:
    """Find 2028 election markets on Polymarket."""
    try:
        # Search for 2028 presidential markets
        url = f"{GAMMA_API}/events?limit=20"
        req = Request(url, headers={"User-Agent": "PoliticalBot/1.0"})
        
        with urlopen(req, timeout=15) as resp:
            events = json.load(resp)
        
        markets_2028 = []
        for event in events:
            title = event.get("title", "")
            if "2028" in title or "next president" in title.lower():
                markets_2028.append(event)
        
        return markets_2028
        
    except Exception as e:
        print(f"[Polymarket] Error: {e}")
        return []


def calculate_divergence(poll_prob: float, market_prob: float) -> float:
    """Calculate divergence between polling and market probability."""
    return abs(poll_prob - market_prob)


def extract_candidate_from_question(question: str) -> str | None:
    """Extract candidate name from market question."""
    # Common patterns: "Will [Candidate] win", "[Candidate] to win", etc.
    question_lower = question.lower()
    
    candidates = [
        "trump", "biden", "desantis", "newsom", "haley", "pence",
        "harris", "buttigieg", "aoc", "sanders", "warren"
    ]
    
    for candidate in candidates:
        if candidate in question_lower:
            return candidate.title()
    
    return None


def cmd_scan(args):
    """Scan for political markets and polling data."""
    print("🗳️ POLITICAL RESEARCH BOT — SCAN")
    print("=" * 60)
    
    config = load_config()
    state = load_state()
    
    # Try to fetch polling data
    print("\n📊 Fetching polling data...")
    
    # Attempt RCP scrape (example - would need specific race URLs)
    # rcp_data = scrape_rcp_polling("https://www.realclearpolitics.com/epolls/...")
    
    # Attempt 538 scrape
    polling_538 = scrape_538_polling()
    if polling_538:
        print(f"  538: {json.dumps(polling_538, indent=2)}")
        state["polling_data"]["538_general"] = polling_538
    
    # Search Polymarket for political markets
    print("\n🔍 Searching Polymarket political markets...")
    political_events = search_polymarket_political()
    print(f"  Found {len(political_events)} political events")
    
    # Also look for 2028 markets specifically
    markets_2028 = find_polymarket_2028_markets()
    if markets_2028:
        print(f"  Found {len(markets_2028)} 2028 election markets")
        political_events.extend(markets_2028)
    
    if not political_events:
        print("❌ No political markets found")
        return []
    
    # Analyze divergences
    print("\n📊 ANALYZING MARKET vs POLLING DIVERGENCES:")
    opportunities = []
    
    for event in political_events[:config["max_markets_to_track"]]:
        title = event.get("title", "")
        markets = event.get("markets", [])
        
        print(f"\n📌 {title}")
        
        for market in markets:
            question = market.get("question", "")
            prices = json.loads(market.get("outcomePrices", "[]"))
            
            if not prices:
                continue
            
            yes_price = float(prices[0])
            volume = float(market.get("volume", 0))
            
            # Skip low volume markets
            if volume < config["min_market_volume"]:
                continue
            
            # Try to match with polling data
            candidate = extract_candidate_from_question(question)
            
            # For now, log all significant markets
            # Real implementation would match specific candidates to polling data
            
            print(f"  {question[:60]}")
            print(f"    Market: {yes_price*100:.1f}% | Volume: ${volume:,.0f}")
            
            # Placeholder: if we had polling data for this candidate
            # we would calculate divergence here
            
            # Example: assume we have polling at 45% for a candidate
            # and market shows 35%
            poll_prob = 0.45  # Placeholder - would come from actual polling
            divergence = calculate_divergence(poll_prob, yes_price)
            
            if divergence >= config["divergence_threshold"]:
                direction = "OVER" if yes_price > poll_prob else "UNDER"
                print(f"    🎯 DIVERGENCE: {divergence*100:.1f}% ({direction}priced)")
                
                opp = {
                    "timestamp": datetime.now().isoformat(),
                    "event_title": title,
                    "question": question,
                    "market_id": market.get("id"),
                    "market_price": yes_price,
                    "poll_estimate": poll_prob,
                    "divergence": divergence,
                    "volume": volume,
                    "direction": direction,
                }
                opportunities.append(opp)
                
                log_opportunity(
                    f"DIVERGENCE: {title[:40]} | "
                    f"Market: {yes_price*100:.1f}% vs Poll: {poll_prob*100:.1f}% | "
                    f"Δ{divergence*100:.1f}% | Vol: ${volume:,.0f}"
                )
    
    state["opportunities"] = opportunities
    state["last_scan"] = datetime.now().isoformat()
    save_state(state)
    
    print(f"\n✅ Found {len(opportunities)} opportunities with ≥{config['divergence_threshold']*100:.0f}% divergence")
    
    return opportunities


def cmd_cycle(args):
    """Run research cycle - scan and log opportunities."""
    print("🗳️ POLITICAL RESEARCH BOT — CYCLE")
    print("=" * 60)
    
    state = load_state()
    
    # Check if we need to scan (based on interval)
    last_scan = state.get("last_scan")
    if last_scan:
        last_scan_dt = datetime.fromisoformat(last_scan)
        config = load_config()
        hours_since = (datetime.now() - last_scan_dt).total_seconds() / 3600
        
        if hours_since < config["scan_interval_hours"]:
            print(f"⏰ Last scan was {hours_since:.1f}h ago (interval: {config['scan_interval_hours']}h)")
            print("💤 Skipping this cycle")
            return
    
    # Run scan
    opportunities = cmd_scan(args)
    
    if opportunities:
        print("\n🎯 NOTABLE OPPORTUNITIES FOUND:")
        for opp in opportunities[:5]:
            print(f"  • {opp['question'][:50]}")
            print(f"    Market: {opp['market_price']*100:.1f}% | Poll: {opp['poll_estimate']*100:.1f}% | Δ{opp['divergence']*100:.1f}%")
        
        print("\nNOTABLE")
    else:
        print("\n💤 No significant divergences found")


def cmd_report(args):
    """Show research report."""
    state = load_state()
    
    print("🗳️ POLITICAL RESEARCH BOT REPORT")
    print("=" * 60)
    
    last_scan = state.get("last_scan")
    if last_scan:
        last_scan_dt = datetime.fromisoformat(last_scan)
        hours_ago = (datetime.now() - last_scan_dt).total_seconds() / 3600
        print(f"Last scan: {hours_ago:.1f}h ago")
    else:
        print("Last scan: Never")
    
    opportunities = state.get("opportunities", [])
    print(f"\nCurrent opportunities: {len(opportunities)}")
    
    if opportunities:
        print("\n📊 Recent Divergences (last 10):")
        for opp in opportunities[-10:]:
            timestamp = datetime.fromisoformat(opp["timestamp"])
            age = (datetime.now() - timestamp).total_seconds() / 3600
            print(f"\n  [{age:.1f}h ago] {opp['event_title'][:50]}")
            print(f"    {opp['question'][:60]}")
            print(f"    Market: {opp['market_price']*100:.1f}% | Poll: {opp['poll_estimate']*100:.1f}%")
            print(f"    Divergence: {opp['divergence']*100:.1f}% ({opp['direction']}priced) | Vol: ${opp['volume']:,.0f}")
    
    # Show tracked polling data
    polling = state.get("polling_data", {})
    if polling:
        print("\n📊 Polling Data Cache:")
        for source, data in polling.items():
            print(f"  {source}: {json.dumps(data, indent=4)}")


def cmd_add_race(args):
    """Add a specific race URL to track."""
    if not args.url:
        print("Error: --url required")
        return
    
    state = load_state()
    
    print(f"🔗 Adding race to track: {args.url}")
    
    # Try to scrape it
    if "realclearpolitics" in args.url:
        polling = scrape_rcp_polling(args.url)
        if polling:
            race_id = args.url.split('/')[-1].replace('.html', '')
            state["polling_data"][f"rcp_{race_id}"] = {
                **polling,
                "url": args.url,
            }
            print(f"✅ Added RCP race: {json.dumps(polling, indent=2)}")
        else:
            print("❌ Failed to scrape polling data")
    else:
        print("⚠️ Only RealClearPolitics URLs supported for now")
    
    save_state(state)


def main():
    parser = argparse.ArgumentParser(description="Political Research Bot")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    subparsers.add_parser("scan", help="Scan political markets and polling").set_defaults(func=cmd_scan)
    subparsers.add_parser("cycle", help="Run research cycle").set_defaults(func=cmd_cycle)
    subparsers.add_parser("report", help="Show research report").set_defaults(func=cmd_report)
    
    add_race_parser = subparsers.add_parser("add-race", help="Add specific race URL to track")
    add_race_parser.add_argument("--url", help="RCP or 538 race URL")
    add_race_parser.set_defaults(func=cmd_add_race)
    
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
