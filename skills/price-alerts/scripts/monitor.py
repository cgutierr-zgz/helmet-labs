#!/usr/bin/env python3
"""
Price Alerts Monitor - Real-time price monitoring via WebSocket.
Triggers OpenClaw wake events when thresholds are crossed.
"""

import argparse
import asyncio
import json
import os
import signal
import sys
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional
import uuid

# Try to import websockets, install if missing
try:
    import websockets
except ImportError:
    print("Installing websockets...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets", "-q"])
    import websockets

SCRIPT_DIR = Path(__file__).parent.parent
STATE_FILE = SCRIPT_DIR / "state" / "alerts.json"
LOG_FILE = Path.home() / "Library" / "Logs" / "price-alerts.log"
PID_FILE = Path.home() / ".openclaw" / "price-alerts.pid"
BINANCE_WS = "wss://stream.binance.com:9443/ws"


def log(msg: str):
    """Log message to file and stdout."""
    timestamp = datetime.now().isoformat()
    line = f"[{timestamp}] {msg}"
    print(line)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except:
        pass


def load_alerts() -> dict:
    """Load alerts from state file."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except:
            pass
    return {"alerts": []}


def save_alerts(data: dict):
    """Save alerts to state file."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def wake_openclaw(message: str):
    """Send wake event to OpenClaw."""
    try:
        # Use openclaw CLI to send wake
        result = subprocess.run(
            ["openclaw", "cron", "wake", "--mode", "now", "--text", message],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            log(f"OpenClaw wake sent: {message}")
        else:
            log(f"OpenClaw wake failed: {result.stderr}")
    except Exception as e:
        log(f"Wake error: {e}")


async def monitor_prices():
    """Main monitoring loop with WebSocket."""
    data = load_alerts()
    alerts = data.get("alerts", [])
    
    if not alerts:
        log("No alerts configured. Exiting.")
        return
    
    # Get unique symbols
    symbols = list(set(a["symbol"].lower() for a in alerts if not a.get("triggered")))
    
    if not symbols:
        log("All alerts already triggered. Exiting.")
        return
    
    # Build stream URL
    streams = "/".join(f"{s}@trade" for s in symbols)
    url = f"{BINANCE_WS}/{streams}"
    
    log(f"Connecting to Binance WebSocket for: {symbols}")
    
    try:
        async with websockets.connect(url) as ws:
            log("Connected to Binance WebSocket")
            
            async for message in ws:
                try:
                    trade = json.loads(message)
                    symbol = trade.get("s", "").upper()
                    price = float(trade.get("p", 0))
                    
                    # Check alerts
                    data = load_alerts()  # Reload in case of changes
                    changed = False
                    
                    for alert in data.get("alerts", []):
                        if alert.get("triggered"):
                            continue
                        if alert["symbol"].upper() != symbol:
                            continue
                        
                        threshold = alert["threshold"]
                        condition = alert.get("condition", "above")
                        
                        triggered = False
                        if condition == "above" and price >= threshold:
                            triggered = True
                        elif condition == "below" and price <= threshold:
                            triggered = True
                        elif condition == "cross":
                            # Check if crossed in either direction
                            last_price = alert.get("last_price")
                            if last_price:
                                if (last_price < threshold <= price) or (last_price > threshold >= price):
                                    triggered = True
                            alert["last_price"] = price
                        
                        if triggered:
                            alert["triggered"] = True
                            alert["triggered_at"] = datetime.now().isoformat()
                            alert["triggered_price"] = price
                            changed = True
                            
                            msg = f"🚨 PRICE ALERT: {alert['message']} (Price: ${price:,.2f})"
                            log(msg)
                            wake_openclaw(msg)
                    
                    if changed:
                        save_alerts(data)
                        
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    log(f"Error processing message: {e}")
                    
    except Exception as e:
        log(f"WebSocket error: {e}")
        # Retry after delay
        await asyncio.sleep(5)
        await monitor_prices()


def cmd_add(args):
    """Add a new alert."""
    data = load_alerts()
    
    alert = {
        "id": args.id or str(uuid.uuid4())[:8],
        "symbol": args.symbol.upper(),
        "condition": "above" if args.above else "below" if args.below else "cross",
        "threshold": args.above or args.below or args.cross,
        "message": args.message,
        "triggered": False,
        "created": datetime.now().isoformat(),
    }
    
    data["alerts"].append(alert)
    save_alerts(data)
    
    print(f"✅ Alert added: {alert['id']}")
    print(f"   {alert['symbol']} {alert['condition']} ${alert['threshold']:,.0f}")
    print(f"   Message: {alert['message']}")


def cmd_list(args):
    """List all alerts."""
    data = load_alerts()
    alerts = data.get("alerts", [])
    
    if not alerts:
        print("No alerts configured.")
        return
    
    print(f"📋 {len(alerts)} alerts:\n")
    for a in alerts:
        status = "✅ TRIGGERED" if a.get("triggered") else "⏳ Active"
        print(f"• [{a['id']}] {a['symbol']} {a.get('condition', 'above')} ${a['threshold']:,.0f}")
        print(f"  {status} | {a['message']}")
        if a.get("triggered_at"):
            print(f"  Triggered at {a['triggered_at']} (${a.get('triggered_price', 0):,.2f})")
        print()


def cmd_remove(args):
    """Remove an alert."""
    data = load_alerts()
    alerts = data.get("alerts", [])
    
    new_alerts = [a for a in alerts if a["id"] != args.alert_id]
    
    if len(new_alerts) == len(alerts):
        print(f"❌ Alert '{args.alert_id}' not found")
        return
    
    data["alerts"] = new_alerts
    save_alerts(data)
    print(f"✅ Alert '{args.alert_id}' removed")


def cmd_start(args):
    """Start the monitor daemon."""
    log("Starting price alerts monitor...")
    
    # Write PID
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))
    
    # Handle signals
    def handle_signal(sig, frame):
        log("Shutting down...")
        if PID_FILE.exists():
            PID_FILE.unlink()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    # Run monitor
    asyncio.run(monitor_prices())


def cmd_status(args):
    """Check monitor status."""
    if PID_FILE.exists():
        with open(PID_FILE) as f:
            pid = f.read().strip()
        # Check if process is running
        try:
            os.kill(int(pid), 0)
            print(f"✅ Monitor running (PID: {pid})")
        except:
            print("❌ Monitor not running (stale PID file)")
            PID_FILE.unlink()
    else:
        print("❌ Monitor not running")


def cmd_clear(args):
    """Clear triggered alerts."""
    data = load_alerts()
    for alert in data.get("alerts", []):
        if alert.get("triggered"):
            alert["triggered"] = False
            alert.pop("triggered_at", None)
            alert.pop("triggered_price", None)
    save_alerts(data)
    print("✅ Cleared all triggered alerts")


def main():
    parser = argparse.ArgumentParser(description="Price Alerts Monitor")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # start
    sub = subparsers.add_parser("start", help="Start the monitor")
    sub.set_defaults(func=cmd_start)
    
    # status
    sub = subparsers.add_parser("status", help="Check monitor status")
    sub.set_defaults(func=cmd_status)
    
    # add
    sub = subparsers.add_parser("add", help="Add alert")
    sub.add_argument("--symbol", "-s", default="BTCUSDT", help="Trading pair")
    sub.add_argument("--above", type=float, help="Alert when price >= threshold")
    sub.add_argument("--below", type=float, help="Alert when price <= threshold")
    sub.add_argument("--cross", type=float, help="Alert when price crosses threshold")
    sub.add_argument("--message", "-m", required=True, help="Alert message")
    sub.add_argument("--id", help="Custom alert ID")
    sub.set_defaults(func=cmd_add)
    
    # list
    sub = subparsers.add_parser("list", help="List alerts")
    sub.set_defaults(func=cmd_list)
    
    # remove
    sub = subparsers.add_parser("remove", help="Remove alert")
    sub.add_argument("alert_id", help="Alert ID to remove")
    sub.set_defaults(func=cmd_remove)
    
    # clear
    sub = subparsers.add_parser("clear", help="Clear triggered alerts")
    sub.set_defaults(func=cmd_clear)
    
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
