#!/bin/bash
# Quick check for arbitrage opportunities
cd "$(dirname "$0")"

# Check if monitor is running
PID=$(cat monitor.pid 2>/dev/null)
if [ -n "$PID" ] && ps -p "$PID" > /dev/null 2>&1; then
    echo "✅ Monitor running (PID $PID)"
else
    echo "❌ Monitor NOT running"
fi

# Show last few log entries
echo ""
echo "📊 Last scan:"
tail -1 monitor.log 2>/dev/null || echo "No log file"

# Check for any opportunities in last hour
echo ""
echo "🎯 Opportunities (last hour):"
if [ -f arb_log.jsonl ]; then
    HOUR_AGO=$(date -v-1H +%Y-%m-%dT%H:%M 2>/dev/null || date -d '1 hour ago' +%Y-%m-%dT%H:%M)
    grep -c '"opportunities": [1-9]' arb_log.jsonl 2>/dev/null || echo "0 total"
else
    echo "No log file yet"
fi
