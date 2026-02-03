#!/usr/bin/env python3
"""
Web scraper with support for both HTTP and browser-based scraping.
"""
import argparse
import json
import sys
import subprocess
from urllib.request import urlopen, Request
from urllib.error import URLError
from html.parser import HTMLParser

class SimpleHTMLParser(HTMLParser):
    """Simple parser to extract text and elements."""
    def __init__(self):
        super().__init__()
        self.text = []
        self.links = []
        self.images = []
        self.current_data = []
        
    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == 'a' and 'href' in attrs_dict:
            self.links.append(attrs_dict['href'])
        if tag == 'img' and 'src' in attrs_dict:
            self.images.append(attrs_dict['src'])
            
    def handle_data(self, data):
        text = data.strip()
        if text:
            self.text.append(text)

def fetch_http(url: str) -> str:
    """Fetch page via HTTP request."""
    import gzip
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    }
    req = Request(url, headers=headers)
    with urlopen(req, timeout=30) as response:
        data = response.read()
        # Handle gzip encoding
        if response.headers.get('Content-Encoding') == 'gzip':
            data = gzip.decompress(data)
        return data.decode('utf-8', errors='ignore')

def fetch_browser(url: str, wait: int = 2) -> str:
    """Fetch page using browser automation via OpenClaw."""
    # Use playwright if available
    try:
        result = subprocess.run([
            'python3', '-c', f'''
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("{url}", wait_until="networkidle")
        await asyncio.sleep({wait})
        content = await page.content()
        print(content)
        await browser.close()

asyncio.run(main())
'''
        ], capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            return result.stdout
    except Exception:
        pass
    
    # Fallback to HTTP
    print("Warning: Browser not available, falling back to HTTP", file=sys.stderr)
    return fetch_http(url)

def extract_by_selector(html: str, selector: str) -> list:
    """Extract elements matching CSS selector (basic support)."""
    # For complex selectors, we'd need beautifulsoup or lxml
    # This is a simplified version for common cases
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        elements = soup.select(selector)
        return [el.get_text(strip=True) for el in elements if el.get_text(strip=True)]
    except ImportError:
        # Fallback: extract all text
        parser = SimpleHTMLParser()
        parser.feed(html)
        return parser.text

def main():
    parser = argparse.ArgumentParser(description='Scrape web pages')
    parser.add_argument('url', help='URL to scrape')
    parser.add_argument('-s', '--selector', default='body', help='CSS selector')
    parser.add_argument('-b', '--browser', action='store_true', help='Use browser')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument('--links', action='store_true', help='Extract links')
    parser.add_argument('--images', action='store_true', help='Extract images')
    parser.add_argument('--text', action='store_true', help='Text only')
    parser.add_argument('--wait', type=int, default=2, help='Wait seconds for JS')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    args = parser.parse_args()
    
    # Fetch page
    try:
        if args.browser:
            html = fetch_browser(args.url, args.wait)
        else:
            html = fetch_http(args.url)
    except Exception as e:
        print(f"Error fetching {args.url}: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Extract content
    if args.links:
        parser = SimpleHTMLParser()
        parser.feed(html)
        results = parser.links
    elif args.images:
        parser = SimpleHTMLParser()
        parser.feed(html)
        results = parser.images
    elif args.text:
        parser = SimpleHTMLParser()
        parser.feed(html)
        results = parser.text
    else:
        results = extract_by_selector(html, args.selector)
    
    # Output
    if args.json or (args.output and args.output.endswith('.json')):
        output = json.dumps(results, indent=2, ensure_ascii=False)
    else:
        output = '\n'.join(results)
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"Saved {len(results)} items to {args.output}")
    else:
        print(output)

if __name__ == '__main__':
    main()
