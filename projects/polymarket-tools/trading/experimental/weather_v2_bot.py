#!/usr/bin/env python3
"""
Weather Bot v2 — Enhanced Multi-Source Weather Bot

Features:
- Expanded city coverage: NYC, Chicago, Seattle, Atlanta, Dallas, Miami, Denver, Phoenix, Boston, Minneapolis
- Dual weather sources: NOAA (primary) + Open-Meteo (backup/validation)
- Per-city accuracy tracking
- Forecast comparison between sources

Created: 2026-02-08
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
STATE_FILE = SCRIPT_DIR / "state_weather_v2.json"
CONFIG_FILE = SCRIPT_DIR / "config_weather_v2.json"
LOG_FILE = SCRIPT_DIR / "weather_v2_opportunities.log"

# Expanded city list with coordinates
CITIES = {
    # Original cities
    "nyc": {"name": "New York", "slug_name": "nyc", "lat": 40.7128, "lon": -74.0060, "unit": "F"},
    "chicago": {"name": "Chicago", "slug_name": "chicago", "lat": 41.8781, "lon": -87.6298, "unit": "F"},
    "seattle": {"name": "Seattle", "slug_name": "seattle", "lat": 47.6062, "lon": -122.3321, "unit": "F"},
    "atlanta": {"name": "Atlanta", "slug_name": "atlanta", "lat": 33.7490, "lon": -84.3880, "unit": "F"},
    "dallas": {"name": "Dallas", "slug_name": "dallas", "lat": 32.7767, "lon": -96.7970, "unit": "F"},
    "miami": {"name": "Miami", "slug_name": "miami", "lat": 25.7617, "lon": -80.1918, "unit": "F"},
    # New cities
    "denver": {"name": "Denver", "slug_name": "denver", "lat": 39.7392, "lon": -104.9903, "unit": "F"},
    "phoenix": {"name": "Phoenix", "slug_name": "phoenix", "lat": 33.4484, "lon": -112.0740, "unit": "F"},
    "boston": {"name": "Boston", "slug_name": "boston", "lat": 42.3601, "lon": -71.0589, "unit": "F"},
    "minneapolis": {"name": "Minneapolis", "slug_name": "minneapolis", "lat": 44.9778, "lon": -93.2650, "unit": "F"},
}

# API endpoints
GAMMA_API = "https://gamma-api.polymarket.com"
OPEN_METEO_API = "https://api.open-meteo.com/v1/forecast"

# Trading params
DEFAULT_CONFIG = {
    "max_bet": 5.0,
    "min_edge": 0.15,  # 15% edge required
    "confidence_threshold": 0.70,
    "scan_interval_min": 10,
    "use_backup_source": True,  # Use Open-Meteo as backup
    "require_source_agreement": False,  # Require both sources to agree on forecast
}


def load_state() -> dict:
    """Load bot state including accuracy tracking."""
    if STATE_FILE.exists():
        try:
            return json.load(open(STATE_FILE))
        except:
            pass
    return {
        "trades": [],
        "positions": [],
        "balance": 50.0,
        "accuracy_by_city": {city: {"correct": 0, "total": 0, "accuracy": 0.0} for city in CITIES},
        "source_comparison": [],
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
    """Log opportunities to file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{timestamp}] {message}\n")


def fetch_noaa_forecast(city_key: str) -> dict | None:
    """Fetch NOAA forecast for a US city (primary source)."""
    city = CITIES.get(city_key)
    if not city:
        return None
    
    try:
        # Step 1: Get grid point
        points_url = f"https://api.weather.gov/points/{city['lat']},{city['lon']}"
        req = Request(points_url, headers={"User-Agent": "WeatherBotV2/1.0"})
        with urlopen(req, timeout=10) as resp:
            points_data = json.load(resp)
        
        forecast_url = points_data["properties"]["forecast"]
        
        # Step 2: Get forecast
        req = Request(forecast_url, headers={"User-Agent": "WeatherBotV2/1.0"})
        with urlopen(req, timeout=10) as resp:
            forecast_data = json.load(resp)
        
        periods = forecast_data["properties"]["periods"]
        
        # Find today's daytime forecast (high temp)
        for period in periods[:4]:
            if period.get("isDaytime", True):
                return {
                    "city": city_key,
                    "source": "noaa",
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


def fetch_openmeteo_forecast(city_key: str) -> dict | None:
    """Fetch Open-Meteo forecast (backup/validation source)."""
    city = CITIES.get(city_key)
    if not city:
        return None
    
    try:
        # Open-Meteo API parameters
        url = (f"{OPEN_METEO_API}?"
               f"latitude={city['lat']}&longitude={city['lon']}"
               f"&daily=temperature_2m_max,temperature_2m_min"
               f"&temperature_unit=fahrenheit"
               f"&timezone=auto"
               f"&forecast_days=3")
        
        req = Request(url, headers={"User-Agent": "WeatherBotV2/1.0"})
        with urlopen(req, timeout=10) as resp:
            data = json.load(resp)
        
        # Get today's forecast (index 0)
        daily = data.get("daily", {})
        max_temps = daily.get("temperature_2m_max", [])
        
        if max_temps:
            temp_f = int(round(max_temps[0]))
            return {
                "city": city_key,
                "source": "openmeteo",
                "temp": temp_f,
                "unit": "F",
                "short": f"High: {temp_f}°F",
                "timestamp": datetime.now().isoformat(),
            }
        
        return None
        
    except Exception as e:
        print(f"[Open-Meteo] Error fetching {city_key}: {e}")
        return None


def get_forecast_with_fallback(city_key: str, use_backup: bool = True) -> dict | None:
    """Get forecast with NOAA primary and Open-Meteo backup."""
    # Try NOAA first
    noaa = fetch_noaa_forecast(city_key)
    
    if use_backup:
        # Also get Open-Meteo for comparison/backup
        openmeteo = fetch_openmeteo_forecast(city_key)
        
        if noaa and openmeteo:
            # Both sources available - compare
            diff = abs(noaa["temp"] - openmeteo["temp"])
            return {
                **noaa,
                "backup_temp": openmeteo["temp"],
                "backup_source": "openmeteo",
                "temp_diff": diff,
                "sources_agree": diff <= 3,  # Within 3°F
            }
        elif noaa:
            return noaa
        elif openmeteo:
            # NOAA failed, use Open-Meteo as backup
            return openmeteo
    else:
        return noaa
    
    return None


def build_event_slugs(days_ahead: int = 2) -> list[str]:
    """Build event slugs for weather markets across multiple days."""
    from datetime import date
    
    slugs = []
    today = date.today()
    
    for day_offset in range(days_ahead + 1):
        target_date = today + timedelta(days=day_offset)
        month = target_date.strftime("%B").lower()
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
        req = Request(url, headers={"User-Agent": "WeatherBotV2/1.0"})
        with urlopen(req, timeout=15) as resp:
            events = json.load(resp)
        
        if events and len(events) > 0:
            return events[0]
        return None
        
    except Exception as e:
        return None


def find_weather_markets() -> list[dict]:
    """Find active weather/temperature markets on Polymarket."""
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
    """Parse temperature bucket from market question."""
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
                   market_price: float, sources_agree: bool = True) -> float:
    """Calculate edge with confidence boost if sources agree."""
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
    
    # Boost confidence if both sources agree
    if sources_agree:
        forecast_prob = min(forecast_prob + 0.05, 0.95)
    
    return forecast_prob - market_price


def cmd_scan(args):
    """Scan for weather markets and forecasts."""
    print("🌤️ WEATHER BOT V2 — SCAN (Enhanced)")
    print("=" * 60)
    
    config = load_config()
    
    # Get forecasts for all cities
    print("\n📡 Fetching multi-source forecasts...")
    forecasts = {}
    for city_key in CITIES:
        forecast = get_forecast_with_fallback(city_key, config["use_backup_source"])
        if forecast:
            forecasts[city_key] = forecast
            sources = f"NOAA+OpenMeteo ({forecast.get('temp_diff', 0)}°F diff)" if forecast.get("backup_temp") else forecast.get("source", "unknown")
            agree_emoji = "✅" if forecast.get("sources_agree", False) else "⚠️"
            print(f"  {agree_emoji} {city_key.upper()}: {forecast['temp']}°F — {forecast.get('short', 'N/A')} [{sources}]")
    
    if not forecasts:
        print("❌ No forecasts available")
        return []
    
    # Get weather events
    print(f"\n🔍 Searching Polymarket weather events for {len(CITIES)} cities...")
    weather_events = find_weather_markets()
    print(f"  Found {len(weather_events)} events")
    
    if not weather_events:
        print("❌ No weather markets found")
        return []
    
    # Analyze opportunities
    print("\n📊 ANALYZING OPPORTUNITIES:")
    opportunities = []
    
    for event_data in weather_events:
        city_key = event_data["city_key"]
        event = event_data["event"]
        target_date = event_data["target_date"]
        
        if city_key not in forecasts:
            continue
        
        forecast = forecasts[city_key]
        forecast_temp = forecast["temp"]
        sources_agree = forecast.get("sources_agree", False)
        
        markets = event.get("markets", [])
        
        print(f"\n🏙️ {city_key.upper()} — {target_date} (Forecast: {forecast_temp}°F)")
        
        for m in markets:
            question = m.get("question", "")
            bucket_low, bucket_high = parse_temp_bucket(question)
            
            if bucket_low is None and bucket_high is None:
                continue
            
            prices = json.loads(m.get("outcomePrices", "[]"))
            yes_price = float(prices[0]) if prices else 0.5
            
            edge = calculate_edge(forecast_temp, bucket_low, bucket_high, yes_price, sources_agree)
            
            bucket_str = f"{bucket_low}-{bucket_high}°F" if bucket_low and bucket_high else \
                         f"≤{bucket_high}°F" if bucket_high else f"≥{bucket_low}°F"
            
            status = "🎯" if abs(edge) >= config["min_edge"] else "  "
            side = "YES" if edge > 0 else "NO"
            
            print(f"  {status} {bucket_str:12} | Price: {yes_price*100:4.0f}% | Edge: {edge*100:+5.1f}% → {side}")
            
            if abs(edge) >= config["min_edge"]:
                opp = {
                    "market_id": m.get("id"),
                    "question": question,
                    "city": city_key,
                    "target_date": str(target_date),
                    "bucket": bucket_str,
                    "bucket_low": bucket_low,
                    "bucket_high": bucket_high,
                    "forecast_temp": forecast_temp,
                    "sources_agree": sources_agree,
                    "yes_price": yes_price,
                    "edge": edge,
                    "side": side,
                    "event_slug": event_data["slug"],
                }
                opportunities.append(opp)
                
                # Log opportunity
                log_msg = f"OPP: {city_key.upper()} {bucket_str} @ {yes_price*100:.0f}% | Edge: {edge*100:+.1f}% | {side}"
                log_opportunity(log_msg)
    
    print(f"\n✅ Found {len(opportunities)} opportunities with ≥{config['min_edge']*100:.0f}% edge")
    
    return opportunities


def cmd_cycle(args):
    """Run a trading cycle."""
    state = load_state()
    config = load_config()
    
    print("🌤️ WEATHER BOT V2 — CYCLE")
    
    # Check for existing positions to avoid duplicates
    existing_positions = {(p.get("city"), p.get("target_date")) for p in state.get("positions", [])}
    
    opportunities = cmd_scan(args)
    
    if not opportunities:
        print("\n💤 No trades this cycle")
        return
    
    # Filter opportunities
    opportunities = [o for o in opportunities if (o["city"], o["target_date"]) not in existing_positions]
    
    # Apply source agreement filter if required
    if config.get("require_source_agreement"):
        opportunities = [o for o in opportunities if o.get("sources_agree", False)]
        if not opportunities:
            print("\n⚠️ No opportunities with source agreement")
            return
    
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
            "sources_agree": best.get("sources_agree", False),
            "status": "open",
        }
        
        state["trades"].append(trade)
        state["positions"].append(trade)
        state["balance"] -= config["max_bet"]
        trades_made += 1
        
        sources_note = "✅ Sources agree" if best.get("sources_agree") else ""
        print(f"\n🎰 PAPER TRADE: {best['side']} {best['city'].upper()} {best['bucket']}")
        print(f"   Date: {best['target_date']} | Forecast: {best['forecast_temp']}°F {sources_note}")
        print(f"   @ {trade_price*100:.0f}% | ${config['max_bet']:.2f}")
        print(f"   Edge: {best['edge']*100:+.1f}%")
        
        log_opportunity(f"TRADE: {best['side']} {best['city'].upper()} {best['bucket']} @ {trade_price*100:.0f}%")
    
    save_state(state)
    
    if trades_made > 0:
        print(f"\n✅ Made {trades_made} trades this cycle")
        print("NOTABLE")


def update_accuracy(state: dict, city: str, was_correct: bool):
    """Update per-city accuracy tracking."""
    if "accuracy_by_city" not in state:
        state["accuracy_by_city"] = {c: {"correct": 0, "total": 0, "accuracy": 0.0} for c in CITIES}
    
    if city not in state["accuracy_by_city"]:
        state["accuracy_by_city"][city] = {"correct": 0, "total": 0, "accuracy": 0.0}
    
    acc = state["accuracy_by_city"][city]
    acc["total"] += 1
    if was_correct:
        acc["correct"] += 1
    acc["accuracy"] = acc["correct"] / acc["total"] if acc["total"] > 0 else 0.0


def cmd_settle(args):
    """Check and settle resolved positions with accuracy tracking."""
    state = load_state()
    positions = state.get("positions", [])
    
    if not positions:
        print("🌤️ No open positions to settle")
        return
    
    print("🌤️ WEATHER BOT V2 — SETTLE CHECK")
    print(f"Checking {len(positions)} open positions...\n")
    
    settled = []
    still_open = []
    
    for pos in positions:
        market_id = pos.get("market_id")
        if not market_id:
            still_open.append(pos)
            continue
        
        try:
            url = f"{GAMMA_API}/markets/{market_id}"
            req = Request(url, headers={"User-Agent": "WeatherBotV2/1.0"})
            with urlopen(req, timeout=15) as resp:
                market = json.load(resp)
            
            if market.get("closed"):
                prices = json.loads(market.get("outcomePrices", "[]"))
                final_yes = float(prices[0]) if prices else 0.5
                
                # Determine if we won
                if pos["side"] == "YES":
                    won = final_yes > 0.99
                else:
                    won = final_yes < 0.01
                
                payout = pos["size"] / pos["price"] if won else 0
                pnl = payout - pos["size"]
                
                pos["status"] = "closed"
                pos["result"] = "WIN" if won else "LOSS"
                pos["pnl"] = pnl
                pos["final_price"] = final_yes
                
                # Update accuracy tracking
                update_accuracy(state, pos["city"], won)
                
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
        for t in state["trades"]:
            if t.get("market_id") == s.get("market_id"):
                t.update(s)
        state["balance"] += s.get("pnl", 0) + s["size"]
    
    save_state(state)
    
    if settled:
        total_pnl = sum(s.get("pnl", 0) for s in settled)
        print(f"\n💰 Settled {len(settled)} positions | P&L: ${total_pnl:+.2f}")
        print("NOTABLE")


def cmd_report(args):
    """Show current status with per-city accuracy."""
    state = load_state()
    
    closed = [t for t in state.get("trades", []) if t.get("status") == "closed"]
    wins = len([t for t in closed if t.get("result") == "WIN"])
    losses = len([t for t in closed if t.get("result") == "LOSS"])
    
    pnl = sum(t.get("pnl", 0) for t in closed)
    wr = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0
    
    print("🌤️ WEATHER BOT V2 REPORT")
    print(f"Record: {wins}W-{losses}L ({wr:.0f}% WR) | P&L: ${pnl:+.2f}")
    print(f"Balance: ${state.get('balance', 50):.2f}")
    print(f"Open positions: {len(state.get('positions', []))}")
    
    # Per-city accuracy
    accuracy = state.get("accuracy_by_city", {})
    if accuracy:
        print("\n📍 Accuracy by City:")
        # Sort by total trades descending
        sorted_cities = sorted(accuracy.items(), key=lambda x: x[1]["total"], reverse=True)
        for city, acc in sorted_cities[:10]:
            if acc["total"] > 0:
                print(f"  {city.upper():12} {acc['correct']}/{acc['total']} ({acc['accuracy']*100:.0f}%)")
    
    if state.get("positions"):
        print("\n📍 Open Positions:")
        for p in state["positions"][:5]:
            sources = "✅" if p.get("sources_agree") else ""
            print(f"  • {p['side']} {p['city'].upper()} {p['bucket']} @ {p['price']*100:.0f}% {sources}")


def main():
    parser = argparse.ArgumentParser(description="Weather Bot v2 — Enhanced Multi-Source")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    subparsers.add_parser("scan", help="Scan markets and forecasts").set_defaults(func=cmd_scan)
    subparsers.add_parser("cycle", help="Run trading cycle").set_defaults(func=cmd_cycle)
    subparsers.add_parser("settle", help="Check and settle resolved positions").set_defaults(func=cmd_settle)
    subparsers.add_parser("report", help="Show status with accuracy tracking").set_defaults(func=cmd_report)
    
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
