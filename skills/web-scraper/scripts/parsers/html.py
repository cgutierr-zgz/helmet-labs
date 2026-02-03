"""
HTML Parser.

Generic parser for HTML pages using CSS selectors from sources.json.
"""

from typing import Optional
from .base import BaseParser, ParsedItem


class HTMLParser(BaseParser):
    """
    Parser for HTML pages.
    
    Uses BeautifulSoup with CSS selectors defined in source config.
    Each source can define:
    - selector: CSS selector for item containers
    - title_selector: Selector for title within item (optional)
    - link_selector: Selector for link within item (optional)  
    - date_selector: Selector for date within item (optional)
    
    If selector returns <a> elements, extracts href and text directly.
    """
    
    def parse(self, content: str, source_config: dict) -> list[ParsedItem]:
        """Parse HTML content into list of items."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            raise RuntimeError("BeautifulSoup is required for HTML parsing: pip install beautifulsoup4")
        
        items = []
        soup = BeautifulSoup(content, 'html.parser')
        
        # Get main selector for items
        selector = source_config.get('selector')
        if not selector:
            return []
        
        # Find all matching elements
        elements = soup.select(selector)
        
        for el in elements:
            parsed_item = self._parse_element(el, source_config, soup)
            if parsed_item:
                items.append(parsed_item)
        
        return items
    
    def _parse_element(self, el, source_config: dict, soup) -> Optional[ParsedItem]:
        """Parse a single HTML element into ParsedItem."""
        title = None
        link = None
        content_text = None
        date = None
        
        # If the element itself is a link
        if el.name == 'a':
            title = el.get_text(strip=True)
            link = el.get('href')
        else:
            # Try to find title
            title_sel = source_config.get('title_selector')
            if title_sel:
                title_el = el.select_one(title_sel)
                if title_el:
                    title = title_el.get_text(strip=True)
            
            if not title:
                # Try common title patterns
                for tag in ['h1', 'h2', 'h3', 'h4', '.title', '.headline', 'a']:
                    title_el = el.select_one(tag)
                    if title_el:
                        title = title_el.get_text(strip=True)
                        break
            
            # Try to find link
            link_sel = source_config.get('link_selector')
            if link_sel:
                link_el = el.select_one(link_sel)
                if link_el:
                    link = link_el.get('href') or link_el.get_text(strip=True)
            
            if not link:
                # Try finding any link in the element
                link_el = el.select_one('a[href]')
                if link_el:
                    link = link_el.get('href')
                    if not title:
                        title = link_el.get_text(strip=True)
        
        # Try to find date
        date_sel = source_config.get('date_selector')
        if date_sel:
            date_el = el.select_one(date_sel)
            if date_el:
                date = date_el.get_text(strip=True)
        
        if not date:
            # Try common date patterns
            date_el = el.select_one('time, .date, .timestamp, [datetime]')
            if date_el:
                date = date_el.get('datetime') or date_el.get_text(strip=True)
        
        # Get content/description
        content_sel = source_config.get('content_selector')
        if content_sel:
            content_el = el.select_one(content_sel)
            if content_el:
                content_text = content_el.get_text(strip=True)
        
        if not content_text:
            # Use element text as fallback
            content_text = el.get_text(separator=' ', strip=True)
            # Truncate if too long
            if len(content_text) > 500:
                content_text = content_text[:500] + "..."
        
        # Must have at least title or link
        if not title and not link:
            return None
        
        # Resolve relative URLs
        link = self._resolve_url(link, source_config.get('url', ''))
        
        # Generate guid
        guid = ParsedItem.generate_guid(link or "", title or "")
        
        return ParsedItem(
            title=self.clean_text(title) or "Untitled",
            link=link or "",
            content=self.clean_text(content_text),
            published_at=self.parse_date(date),
            guid=guid,
        )
    
    def _resolve_url(self, url: Optional[str], base_url: str) -> Optional[str]:
        """Resolve relative URL to absolute."""
        if not url:
            return None
        
        if url.startswith(('http://', 'https://')):
            return url
        
        if url.startswith('//'):
            return 'https:' + url
        
        # Relative URL - need base
        if base_url:
            from urllib.parse import urljoin
            return urljoin(base_url, url)
        
        return url
