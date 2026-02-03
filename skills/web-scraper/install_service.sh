#!/bin/bash
set -e

PLIST_NAME="com.helmet.webscraper.plist"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_SRC="$SCRIPT_DIR/$PLIST_NAME"
PLIST_DST="$HOME/Library/LaunchAgents/$PLIST_NAME"

# Crear directorio de logs
mkdir -p "$SCRIPT_DIR/logs"

# Copiar plist
cp "$PLIST_SRC" "$PLIST_DST"

# Cargar servicio
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"

echo "✅ Service installed and started"
echo "   Check status: launchctl list | grep webscraper"
echo "   View logs: tail -f $SCRIPT_DIR/logs/scraper.log"
