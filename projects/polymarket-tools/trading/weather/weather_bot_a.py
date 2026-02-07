#!/usr/bin/env python3
"""
Weather Bot A — NOAA Forecast → Polymarket Weather Markets

Fetches weather forecasts from NOAA and trades Polymarket temperature markets
when forecast confidence exceeds market odds.

Cities: NYC, Chicago, Seattle, Atlanta, Dallas, Miami, London, Seoul
Markets: Daily high temperature bucket predictions

Created: 2026-02-06
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError
import re

SCRIPT_DIR = Path(__file__).parent
STATE_FILE = SCRIPT_DIR / "state_weather.json"
CONFIG_FILE = SCRIPT_DIR / "config_weather.json"

# City coordinates for NOAA API (US cities only - NOAA is US-focused)
# slug_name must match Polymarket event slugs
CITIES = {
    "nyc": {"name": "New York", "slug_name": "nyc", "lat": 40.7128, "lon": -74.0060, "unit": "F"},
    "chicago": {"name": "Chicago", "slug_name": "chicago", "lat": 41.8781, "lon": -87.6298, "unit": "F"},
    "seattle": {"name": "Seattle", "slug_name": "seattle", "lat": 47.6062, "lon": -122.3321, "unit": "F"},
    "atlanta": {"name": "Atlanta", "slug_name": "atlanta", "lat": 33.7490, "lon": -84.3880, "unit": "F"},
    "dallas": {"name": "Dallas", "slug_name": "dallas", "lat": 32.7767, "lon": -96.7970, "unit": "F"},
    "miami": {"name": "Miami", "slug_name": "miami", "lat": 25.7617, "lon": -80.1918, "unit": "F"},
}

# Polymarket API
GAMMA_API = "https://gamma-api.polymarket.com"

# Trading params
DEFAULT_CONFIG = {
    "max_bet": 5.0,
    "min_edge": 0.15,  # 15% edge required
    "confidence_threshold": 0.70,  # 70% forecast confidence
    "scan_interval_min": 10,
}


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.load(open(STATE_FILE))
        except:
            pass
    return {"trades": [], "positions": [], "balance": 50.0}


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


def fetch_noaa_forecast(city_key: str) -> dict | None:
    """Fetch NOAA forecast for a US city."""
    city = CITIES.get(city_key)
    if not city:
        return None
    
    try:
        # Step 1: Get grid point
        points_url = f"https://api.weather.gov/points/{city['lat']},{city['lon']}"
        req = Request(points_url, headers={"User-Agent": "WeatherBot/1.0"})
        with urlopen(req, timeout=10) as resp:
            points_data = json.load(resp)
        
        forecast_url = points_data["properties"]["forecast"]
        
        # Step 2: Get forecast
        req = Request(forecast_url, headers={"User-Agent": "WeatherBot/1.0"})
        with urlopen(req, timeout=10) as resp:
            forecast_data = json.load(resp)
        
        periods = forecast_data["properties"]["periods"]
        
        # Find today's daytime forecast (high temp)
        for period in periods[:4]:
            if period.get("isDaytime", True):
                return {
                    "city": city_key,
                    "name": period["name"],
                    "temp": period["temperature"],
                    "unit": period["temperatureUnit"],
                    "short": period["shortForecast"],
                    "detailed": period["detailedForecast"],
                    "timestamp": datetime.now().isoformat(),
                }
        
        return None
        
    except Exception as e:
        print(f"[NOAA] Error fetching {city_key}: {e}")
        return None


def build_event_slugs(days_ahead: int = 2) -> list[str]:
    """Build event slugs for weather markets across multiple days."""
    from datetime import date
    
    slugs = []
    today = date.today()
    
    for day_offset in range(days_ahead + 1):
        target_date = today + timedelta(days=day_offset)
        month = target_date.strftime("%B").lower()  # e.g., "february"
        day = target_date.day
        year = target_date.year
        
        for city_key, city_data in CITIES.items():
            slug = f"highest-temperature-in-{city_data['slug_name']}-on-{month}-{day}-{year}"
            slugs.append((slug, city_key, target_date))
    
    return slugs


def fetch_weather_event(slug: str) -> dict | None:
    """Fetch a weather event by slug from Gamma API."""
    try:
        url = f"{GAMMA_API}/events?slug={slug}"
        req = Request(url, headers={"User-Agent": "WeatherBot/1.0"})
        with urlopen(req, timeout=15) as resp:
            events = json.load(resp)
        
        if events and len(events) > 0:
            return events[0]
        return None
        
    except Exception as e:
        return None


def find_weather_markets() -> list[dict]:
    """Find active weather/temperature markets on Polymarket by searching event slugs."""
    events = []
    
    slugs = build_event_slugs(days_ahead=2)
    
    for slug, city_key, target_date in slugs:
        event = fetch_weather_event(slug)
        if event:
            events.append({
                "event": event,
                "city_key": city_key,
                "target_date": target_date,
                "slug": slug,
            })
    
    return events


def parse_temp_bucket(question: str) -> tuple[int | None, int | None]:
    """Parse temperature bucket from market question.
    
    Returns: (low_temp, high_temp) — None means unbounded
    Examples:
        "between 26-27°F" → (26, 27)
        "15°F or below" → (None, 15)
        "26°F or higher" → (26, None)
    """
    q = question.lower()
    
    # Range: "between XX-YY°F" or "XX-YY°F"
    range_match = re.search(r"(?:between\s+)?(\d+)-(\d+)\s*°[fc]", q)
    if range_match:
        return int(range_match.group(1)), int(range_match.group(2))
    
    # Below: "XX°F or below"
    below_match = re.search(r"(\d+)\s*°[fc]\s+or\s+below", q)
    if below_match:
        return None, int(below_match.group(1))
    
    # Above: "XX°F or higher" or "XX°F or above"
    above_match = re.search(r"(\d+)\s*°[fc]\s+or\s+(?:higher|above)", q)
    if above_match:
        return int(above_match.group(1)), None
    
    return None, None


def calculate_edge(forecast_temp: int, bucket_low: int | None, bucket_high: int | None, 
                   market_price: float) -> float:
    """Calculate edge: (forecast_prob - market_price).
    
    Simple model: if forecast temp is in bucket, we estimate ~80% confidence.
    Adjacent buckets get ~15%, further buckets ~5%.
    """
    if bucket_low is None:
        # "X or below" market
        if forecast_temp <= bucket_high:
            forecast_prob = 0.80
        elif forecast_temp <= bucket_high + 2:
            forecast_prob = 0.40
        else:
            forecast_prob = 0.10
    elif bucket_high is None:
        # "X or above" market
        if forecast_temp >= bucket_low:
            forecast_prob = 0.80
        elif forecast_temp >= bucket_low - 2:
            forecast_prob = 0.40
        else:
            forecast_prob = 0.10
    else:
        # Range bucket
        if bucket_low <= forecast_temp <= bucket_high:
            forecast_prob = 0.75
        elif abs(forecast_temp - bucket_low) <= 2 or abs(forecast_temp - bucket_high) <= 2:
            forecast_prob = 0.30
        else:
            forecast_prob = 0.05
    
    return forecast_prob - market_price


def cmd_scan(args):
    """Scan for weather markets and forecasts."""
    print("🌤️ WEATHER BOT A — SCAN")
    print("=" * 50)
    
    # Get forecasts for US cities
    print("\n📡 Fetching NOAA forecasts...")
    forecasts = {}
    for city_key in CITIES:
        forecast = fetch_noaa_forecast(city_key)
        if forecast:
            forecasts[city_key] = forecast
            print(f"  {city_key.upper()}: {forecast['temp']}°{forecast['unit']} — {forecast['short']}")
    
    if not forecasts:
        print("❌ No forecasts available")
        return []
    
    # Get weather events
    print("\n🔍 Searching Polymarket weather events...")
    weather_events = find_weather_markets()
    print(f"  Found {len(weather_events)} events")
    
    if not weather_events:
        print("❌ No weather markets found")
        return []
    
    # Analyze opportunities
    print("\n📊 ANALYZING OPPORTUNITIES:")
    config = load_config()
    opportunities = []
    
    for event_data in weather_events:
        city_key = event_data["city_key"]
        event = event_data["event"]
        target_date = event_data["target_date"]
        
        if city_key not in forecasts:
            continue
        
        forecast = forecasts[city_key]
        forecast_temp = forecast["temp"]
        
        # Each event has multiple sub-markets (temperature buckets)
        markets = event.get("markets", [])
        
        print(f"\n🏙️ {city_key.upper()} — {target_date} (Forecast: {forecast_temp}°F)")
        
        for m in markets:
            question = m.get("question", "")
            bucket_low, bucket_high = parse_temp_bucket(question)
            
            if bucket_low is None and bucket_high is None:
                continue
            
            prices = json.loads(m.get("outcomePrices", "[]"))
            yes_price = float(prices[0]) if prices else 0.5
            
            edge = calculate_edge(forecast_temp, bucket_low, bucket_high, yes_price)
            
            bucket_str = f"{bucket_low}-{bucket_high}°F" if bucket_low and bucket_high else \
                         f"≤{bucket_high}°F" if bucket_high else f"≥{bucket_low}°F"
            
            status = "🎯" if abs(edge) >= config["min_edge"] else "  "
            side = "YES" if edge > 0 else "NO"
            
            print(f"  {status} {bucket_str:12} | Price: {yes_price*100:4.0f}% | Edge: {edge*100:+5.1f}% → {side}")
            
            if abs(edge) >= config["min_edge"]:
                opportunities.append({
                    "market_id": m.get("id"),
                    "question": question,
                    "city": city_key,
                    "target_date": str(target_date),
                    "bucket": bucket_str,
                    "bucket_low": bucket_low,
                    "bucket_high": bucket_high,
                    "forecast_temp": forecast_temp,
                    "yes_price": yes_price,
                    "edge": edge,
                    "side": side,
                    "event_slug": event_data["slug"],
                })
    
    print(f"\n✅ Found {len(opportunities)} opportunities with ≥{config['min_edge']*100:.0f}% edge")
    
    return opportunities


def cmd_cycle(args):
    """Run a trading cycle."""
    state = load_state()
    config = load_config()
    
    print("🌤️ WEATHER BOT A — CYCLE")
    
    # Check for existing positions to avoid duplicates
    existing_positions = {(p.get("city"), p.get("target_date")) for p in state.get("positions", [])}
    
    opportunities = cmd_scan(args)
    
    if not opportunities:
        print("\n💤 No trades this cycle")
        return
    
    # Filter out opportunities where we already have a position
    opportunities = [o for o in opportunities if (o["city"], o["target_date"]) not in existing_positions]
    
    if not opportunities:
        print("\n💤 Already have positions for all opportunities")
        return
    
    # Group by (city, date) and take the best opportunity for each
    best_per_city = {}
    for opp in opportunities:
        key = (opp["city"], opp["target_date"])
        if key not in best_per_city or abs(opp["edge"]) > abs(best_per_city[key]["edge"]):
            best_per_city[key] = opp
    
    # Take up to 3 trades per cycle, prioritized by edge
    sorted_opps = sorted(best_per_city.values(), key=lambda x: abs(x["edge"]), reverse=True)
    max_trades_per_cycle = 3
    trades_made = 0
    
    for best in sorted_opps[:max_trades_per_cycle]:
        if state["balance"] < config["max_bet"]:
            print(f"\n⚠️ Insufficient balance (${state['balance']:.2f})")
            break
            
        trade_price = best["yes_price"] if best["side"] == "YES" else (1 - best["yes_price"])
        
        trade = {
            "timestamp": datetime.now().isoformat(),
            "market_id": best.get("market_id"),
            "city": best["city"],
            "target_date": best["target_date"],
            "bucket": best["bucket"],
            "bucket_low": best["bucket_low"],
            "bucket_high": best["bucket_high"],
            "side": best["side"],
            "price": trade_price,
            "size": config["max_bet"],
            "edge": best["edge"],
            "forecast_temp": best["forecast_temp"],
            "status": "open",
        }
        
        state["trades"].append(trade)
        state["positions"].append(trade)
        state["balance"] -= config["max_bet"]
        trades_made += 1
        
        print(f"\n🎰 PAPER TRADE: {best['side']} {best['city'].upper()} {best['bucket']}")
        print(f"   Date: {best['target_date']} | Forecast: {best['forecast_temp']}°F")
        print(f"   @ {trade_price*100:.0f}% | ${config['max_bet']:.2f}")
        print(f"   Edge: {best['edge']*100:+.1f}%")
    
    save_state(state)
    
    if trades_made > 0:
        print(f"\n✅ Made {trades_made} trades this cycle")
        print("NOTABLE")


def cmd_settle(args):
    """Check and settle resolved positions."""
    state = load_state()
    positions = state.get("positions", [])
    
    if not positions:
        print("🌤️ No open positions to settle")
        return
    
    print("🌤️ WEATHER BOT A — SETTLE CHECK")
    print(f"Checking {len(positions)} open positions...\n")
    
    settled = []
    still_open = []
    
    for pos in positions:
        market_id = pos.get("market_id")
        if not market_id:
            still_open.append(pos)
            continue
        
        # Fetch market status
        try:
            url = f"{GAMMA_API}/markets/{market_id}"
            req = Request(url, headers={"User-Agent": "WeatherBot/1.0"})
            with urlopen(req, timeout=15) as resp:
                market = json.load(resp)
            
            if market.get("closed"):
                # Market resolved
                prices = json.loads(market.get("outcomePrices", "[]"))
                final_yes = float(prices[0]) if prices else 0.5
                
                # Determine if we won
                if pos["side"] == "YES":
                    won = final_yes > 0.99  # YES resolved to ~$1
                else:
                    won = final_yes < 0.01  # NO resolved (YES went to ~$0)
                
                payout = pos["size"] / pos["price"] if won else 0
                pnl = payout - pos["size"]
                
                pos["status"] = "closed"
                pos["result"] = "WIN" if won else "LOSS"
                pos["pnl"] = pnl
                pos["final_price"] = final_yes
                
                result_emoji = "✅" if won else "❌"
                print(f"{result_emoji} {pos['city'].upper()} {pos['bucket']}: {'WIN' if won else 'LOSS'} (${pnl:+.2f})")
                settled.append(pos)
            else:
                still_open.append(pos)
                print(f"⏳ {pos['city'].upper()} {pos['bucket']}: Still open")
                
        except Exception as e:
            print(f"⚠️ Error checking {pos['city']} {pos['bucket']}: {e}")
            still_open.append(pos)
    
    # Update state
    state["positions"] = still_open
    for s in settled:
        # Update the trade record
        for t in state["trades"]:
            if t.get("market_id") == s.get("market_id"):
                t.update(s)
        state["balance"] += s.get("pnl", 0) + s["size"]  # Return stake + profit/loss
    
    save_state(state)
    
    if settled:
        total_pnl = sum(s.get("pnl", 0) for s in settled)
        print(f"\n💰 Settled {len(settled)} positions | P&L: ${total_pnl:+.2f}")
        print("NOTABLE")


def cmd_report(args):
    """Show current status."""
    state = load_state()
    
    closed = [t for t in state.get("trades", []) if t.get("status") == "closed"]
    wins = len([t for t in closed if t.get("result") == "WIN"])
    losses = len([t for t in closed if t.get("result") == "LOSS"])
    
    pnl = sum(t.get("pnl", 0) for t in closed)
    wr = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0
    
    print("🌤️ WEATHER BOT A REPORT")
    print(f"Record: {wins}W-{losses}L ({wr:.0f}% WR) | P&L: ${pnl:+.2f}")
    print(f"Balance: ${state.get('balance', 50):.2f}")
    print(f"Open positions: {len(state.get('positions', []))}")
    
    if state.get("positions"):
        print("\n📍 Open:")
        for p in state["positions"][:5]:
            print(f"  • {p['side']} {p['city'].upper()} {p['bucket']} @ {p['price']*100:.0f}%")


def main():
    parser = argparse.ArgumentParser(description="Weather Bot A — NOAA + Polymarket")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    subparsers.add_parser("scan", help="Scan markets and forecasts").set_defaults(func=cmd_scan)
    subparsers.add_parser("cycle", help="Run trading cycle").set_defaults(func=cmd_cycle)
    subparsers.add_parser("settle", help="Check and settle resolved positions").set_defaults(func=cmd_settle)
    subparsers.add_parser("report", help="Show status").set_defaults(func=cmd_report)
    
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
