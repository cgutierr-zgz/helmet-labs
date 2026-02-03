"""
RSS Feed Parser.

Handles RSS 2.0 feeds (Fed, FDA, etc.).
"""

import xml.etree.ElementTree as ET
from typing import Optional
from .base import BaseParser, ParsedItem


class RSSParser(BaseParser):
    """
    Parser for RSS 2.0 feeds.
    
    RSS structure:
    <rss>
      <channel>
        <item>
          <title>...</title>
          <link>...</link>
          <description>...</description>
          <pubDate>...</pubDate>
          <guid>...</guid>
          <category>...</category>
        </item>
      </channel>
    </rss>
    """
    
    def parse(self, content: str, source_config: dict) -> list[ParsedItem]:
        """Parse RSS feed content into list of items."""
        items = []
        
        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            # Try to clean common XML issues
            content = self._clean_xml(content)
            try:
                root = ET.fromstring(content)
            except ET.ParseError:
                return []  # Give up if still invalid
        
        # Find all item elements (handle with or without namespace)
        channel = root.find('channel')
        if channel is None:
            # Try finding items directly (some malformed feeds)
            item_elements = root.findall('.//item')
        else:
            item_elements = channel.findall('item')
        
        for item_el in item_elements:
            parsed_item = self._parse_item(item_el, source_config)
            if parsed_item:
                items.append(parsed_item)
        
        return items
    
    def _parse_item(self, item_el: ET.Element, source_config: dict) -> Optional[ParsedItem]:
        """Parse a single <item> element."""
        # Extract core fields
        title = self._get_text(item_el, 'title')
        link = self._get_text(item_el, 'link')
        description = self._get_text(item_el, 'description')
        pub_date = self._get_text(item_el, 'pubDate')
        guid = self._get_text(item_el, 'guid')
        category = self._get_text(item_el, 'category')
        author = self._get_text(item_el, 'author') or self._get_text(item_el, 'dc:creator')
        
        # Must have at least title or link
        if not title and not link:
            return None
        
        # Generate guid if not present
        if not guid:
            guid = ParsedItem.generate_guid(link or "", title or "")
        
        # Clean description (remove CDATA, HTML)
        description = self._clean_description(description)
        
        return ParsedItem(
            title=self.clean_text(title) or "Untitled",
            link=link or "",
            content=self.clean_text(description),
            published_at=self.parse_date(pub_date),
            guid=guid,
            category=self.clean_text(category),
            author=self.clean_text(author),
        )
    
    def _get_text(self, element: ET.Element, tag: str) -> Optional[str]:
        """Get text content of a child element."""
        # Try direct child
        child = element.find(tag)
        if child is not None and child.text:
            return child.text
        
        # Try with common namespaces
        namespaces = {
            'dc': 'http://purl.org/dc/elements/1.1/',
            'content': 'http://purl.org/rss/1.0/modules/content/',
        }
        
        for prefix, ns in namespaces.items():
            if tag.startswith(f'{prefix}:'):
                actual_tag = tag.split(':', 1)[1]
                child = element.find(f'{{{ns}}}{actual_tag}')
                if child is not None and child.text:
                    return child.text
        
        return None
    
    def _clean_description(self, text: Optional[str]) -> str:
        """Clean description text, removing HTML and CDATA."""
        if not text:
            return ""
        
        import re
        
        # Remove CDATA wrapper if present
        text = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', text, flags=re.DOTALL)
        
        # Remove HTML tags but keep text
        text = re.sub(r'<[^>]+>', ' ', text)
        
        # Decode common HTML entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        text = text.replace('&#39;', "'")
        
        return text
    
    def _clean_xml(self, content: str) -> str:
        """Attempt to clean malformed XML."""
        import re
        
        # Remove XML declaration if malformed
        content = re.sub(r'<\?xml[^>]*\?>\s*', '', content)
        
        # Remove BOM
        content = content.lstrip('\ufeff')
        
        return content
