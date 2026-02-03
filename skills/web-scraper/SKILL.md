---
name: web-scraper
description: Intelligent web scraping and monitoring. Use for extracting content from websites, monitoring pages for changes, scraping news headlines, tracking prices, or any task requiring automated web data extraction. Supports both one-time scraping and continuous monitoring with change detection.
---

# Web Scraper

Scrape websites and monitor for changes using browser automation or HTTP requests.

## Quick Start

### One-time scrape
```bash
# Scrape headlines from a news site
scripts/scrape.py "https://reuters.com" --selector "h3" --output headlines.json

# Scrape with full browser (for JS-heavy sites)
scripts/scrape.py "https://twitter.com/elonmusk" --browser --selector "[data-testid='tweetText']"
```

### Monitor for changes
```bash
# Monitor a page, alert on new content
scripts/monitor.py "https://reuters.com/markets" --selector ".story-title" --interval 60
```

## Commands

### scrape.py
Extract content from a webpage.

```bash
scripts/scrape.py <url> [options]

Options:
  --selector, -s    CSS selector to extract (default: body)
  --browser, -b     Use full browser (for JS sites)
  --output, -o      Output file (json/txt)
  --links           Extract all links
  --images          Extract all images
  --text            Extract text only (clean)
  --wait            Wait N seconds for JS to load
  --screenshot      Take screenshot
```

Examples:
```bash
# Get all headlines
scripts/scrape.py "https://news.ycombinator.com" -s ".titleline > a" -o hn.json

# Get with browser for JS content
scripts/scrape.py "https://polymarket.com" --browser -s ".market-title" --wait 3
```

### monitor.py
Watch a page for changes and alert.

```bash
scripts/monitor.py <url> [options]

Options:
  --selector, -s    CSS selector to watch
  --interval, -i    Check interval in seconds (default: 60)
  --output, -o      Log changes to file
  --diff            Show what changed
  --alert           Print alert when change detected
```

Examples:
```bash
# Monitor news for new headlines
scripts/monitor.py "https://reuters.com" -s "h3.story-title" -i 30 --alert

# Monitor and log all changes
scripts/monitor.py "https://idealista.com/search" -s ".item-info" -i 60 -o changes.log
```

## Use Cases

1. **News monitoring**: Watch headlines, detect breaking news
2. **Price tracking**: Monitor e-commerce prices
3. **Availability alerts**: Watch for stock/appointments
4. **Content extraction**: Scrape data for analysis
5. **Change detection**: Know when a page updates

## Tips

- Use `--browser` for sites that load content with JavaScript
- Use `--wait` if content takes time to appear
- Start with short intervals, increase if rate-limited
- Combine with other tools (jq, grep) for filtering
