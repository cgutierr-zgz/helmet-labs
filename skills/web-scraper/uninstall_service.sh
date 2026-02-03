#!/bin/bash
PLIST_DST="$HOME/Library/LaunchAgents/com.helmet.webscraper.plist"
launchctl unload "$PLIST_DST" 2>/dev/null || true
rm -f "$PLIST_DST"
echo "✅ Service uninstalled"
