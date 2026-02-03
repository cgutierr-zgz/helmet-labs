"""
ATOM Feed Parser.

Handles ATOM feeds (SEC EDGAR, etc.).
"""

import xml.etree.ElementTree as ET
from typing import Optional
from .base import BaseParser, ParsedItem


class AtomParser(BaseParser):
    """
    Parser for ATOM feeds.
    
    ATOM structure (with namespace):
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <title>...</title>
        <link href="..." rel="alternate"/>
        <id>...</id>
        <updated>...</updated>
        <summary>...</summary>
        <author><name>...</name></author>
        <category term="..."/>
      </entry>
    </feed>
    """
    
    # ATOM namespace
    ATOM_NS = '{http://www.w3.org/2005/Atom}'
    
    def parse(self, content: str, source_config: dict) -> list[ParsedItem]:
        """Parse ATOM feed content into list of items."""
        items = []
        
        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            content = self._clean_xml(content)
            try:
                root = ET.fromstring(content)
            except ET.ParseError:
                return []
        
        # Find all entry elements (try with and without namespace)
        entries = root.findall(f'{self.ATOM_NS}entry')
        if not entries:
            entries = root.findall('entry')
        if not entries:
            entries = root.findall('.//{http://www.w3.org/2005/Atom}entry')
        
        for entry_el in entries:
            parsed_item = self._parse_entry(entry_el, source_config)
            if parsed_item:
                items.append(parsed_item)
        
        return items
    
    def _parse_entry(self, entry_el: ET.Element, source_config: dict) -> Optional[ParsedItem]:
        """Parse a single <entry> element."""
        ns = self.ATOM_NS
        
        # Extract core fields
        title = self._get_text(entry_el, f'{ns}title') or self._get_text(entry_el, 'title')
        
        # Link handling - ATOM uses href attribute
        link = self._get_link(entry_el)
        
        # Summary/content
        summary = (
            self._get_text(entry_el, f'{ns}summary') or 
            self._get_text(entry_el, 'summary') or
            self._get_text(entry_el, f'{ns}content') or
            self._get_text(entry_el, 'content')
        )
        
        # ID (guid in ATOM)
        guid = self._get_text(entry_el, f'{ns}id') or self._get_text(entry_el, 'id')
        
        # Date - ATOM uses <updated> or <published>
        updated = (
            self._get_text(entry_el, f'{ns}updated') or 
            self._get_text(entry_el, 'updated') or
            self._get_text(entry_el, f'{ns}published') or
            self._get_text(entry_el, 'published')
        )
        
        # Category - ATOM uses term attribute
        category = self._get_category(entry_el)
        
        # Author
        author = self._get_author(entry_el)
        
        # Must have at least title or link
        if not title and not link:
            return None
        
        # Generate guid if not present
        if not guid:
            guid = ParsedItem.generate_guid(link or "", title or "")
        
        # Clean summary
        summary = self._clean_content(summary)
        
        return ParsedItem(
            title=self.clean_text(title) or "Untitled",
            link=link or "",
            content=self.clean_text(summary),
            published_at=self.parse_date(updated),
            guid=guid,
            category=self.clean_text(category),
            author=self.clean_text(author),
        )
    
    def _get_text(self, element: ET.Element, tag: str) -> Optional[str]:
        """Get text content of a child element."""
        child = element.find(tag)
        if child is not None:
            # Handle type="html" or type="xhtml" content
            content_type = child.get('type', 'text')
            if child.text:
                return child.text
            elif content_type in ('html', 'xhtml'):
                # Serialize inner XML as text
                return ET.tostring(child, encoding='unicode', method='text')
        return None
    
    def _get_link(self, entry_el: ET.Element) -> Optional[str]:
        """Extract link from ATOM entry (handles href attribute)."""
        ns = self.ATOM_NS
        
        # Try to find alternate link first (primary link)
        for link_el in entry_el.findall(f'{ns}link') + entry_el.findall('link'):
            rel = link_el.get('rel', 'alternate')
            if rel == 'alternate':
                href = link_el.get('href')
                if href:
                    return href
        
        # Fall back to any link
        for link_el in entry_el.findall(f'{ns}link') + entry_el.findall('link'):
            href = link_el.get('href')
            if href:
                return href
        
        return None
    
    def _get_category(self, entry_el: ET.Element) -> Optional[str]:
        """Extract category from ATOM entry."""
        ns = self.ATOM_NS
        
        for cat_el in entry_el.findall(f'{ns}category') + entry_el.findall('category'):
            term = cat_el.get('term')
            if term:
                return term
            # Some feeds use label
            label = cat_el.get('label')
            if label:
                return label
        
        return None
    
    def _get_author(self, entry_el: ET.Element) -> Optional[str]:
        """Extract author name from ATOM entry."""
        ns = self.ATOM_NS
        
        author_el = entry_el.find(f'{ns}author') or entry_el.find('author')
        if author_el is not None:
            name_el = author_el.find(f'{ns}name') or author_el.find('name')
            if name_el is not None and name_el.text:
                return name_el.text
        
        return None
    
    def _clean_content(self, text: Optional[str]) -> str:
        """Clean content text, removing HTML."""
        if not text:
            return ""
        
        import re
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)
        
        # Decode HTML entities
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
        content = re.sub(r'<\?xml[^>]*\?>\s*', '', content)
        content = content.lstrip('\ufeff')
        return content
