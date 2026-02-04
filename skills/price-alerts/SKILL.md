---
name: price-alerts
description: Real-time price alerts via WebSocket streams. Monitors crypto prices (Binance) and triggers alerts when thresholds are crossed. Used for automated trading position management.
version: 1.0.0
---

# Price Alerts

Real-time price monitoring via WebSocket streams. When price crosses configured thresholds, triggers OpenClaw wake events.

## Quick Start

```bash
# Start the monitor daemon
python3 scripts/monitor.py start

# Add an alert
python3 scripts/monitor.py add --symbol BTCUSDT --above 80000 --message "BTC hit $80k - exit short positions"
python3 scripts/monitor.py add --symbol BTCUSDT --below 70000 --message "BTC hit $70k - take profits on dip bet"

# List active alerts
python3 scripts/monitor.py list

# Remove alert
python3 scripts/monitor.py remove <alert_id>
```

## How It Works

1. **WebSocket Connection**: Connects to Binance stream (`wss://stream.binance.com:9443`)
2. **Price Monitoring**: Subscribes to real-time price updates for configured symbols
3. **Threshold Detection**: When price crosses above/below threshold, triggers alert
4. **OpenClaw Wake**: Sends wake event to OpenClaw with alert message

## Configuration

Alerts stored in `state/alerts.json`:

```json
{
  "alerts": [
    {
      "id": "btc-80k-exit",
      "symbol": "BTCUSDT",
      "condition": "above",
      "threshold": 80000,
      "message": "BTC > $80k - consider exiting positions",
      "triggered": false,
      "created": "2026-02-04T15:00:00Z"
    }
  ]
}
```

## Daemon Management

The monitor runs as a launchd service:

```bash
# Install service
python3 scripts/monitor.py install

# Check status
python3 scripts/monitor.py status

# View logs
tail -f ~/Library/Logs/price-alerts.log
```

## Supported Exchanges

- **Binance** (default): `wss://stream.binance.com:9443/ws/{symbol}@trade`

## Alert Types

| Type | Trigger |
|------|---------|
| `above` | Price >= threshold |
| `below` | Price <= threshold |
| `cross` | Price crosses threshold in either direction |

## Integration with Trading

Use with trading scans:
1. Open position on Polymarket
2. Set price alert for exit condition
3. When triggered, evaluate and act

Example flow:
```
1. Buy "BTC dip to $70k" YES at $0.60
2. Set alert: BTCUSDT above 80000 → "Exit BTC dip position"
3. Set alert: BTCUSDT below 70000 → "BTC hit target, take profits"
4. Monitor triggers wake → I evaluate and act
```
