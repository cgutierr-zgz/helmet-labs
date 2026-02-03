"""
Parsers package - Specialized parsers for different feed/page types.

Each parser extracts structured items from raw content.
"""

from .base import BaseParser, ParsedItem
from .rss import RSSParser
from .atom import AtomParser
from .html import HTMLParser

# Parser registry by type
PARSERS = {
    'rss': RSSParser,
    'atom': AtomParser,
    'html': HTMLParser,
}


def get_parser(source_type: str) -> BaseParser:
    """Get parser instance for source type."""
    parser_class = PARSERS.get(source_type)
    if not parser_class:
        raise ValueError(f"Unknown source type: {source_type}")
    return parser_class()


__all__ = [
    'BaseParser',
    'ParsedItem',
    'RSSParser',
    'AtomParser',
    'HTMLParser',
    'PARSERS',
    'get_parser',
]
