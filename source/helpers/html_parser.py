"""
HTML parsing utilities wrapping BeautifulSoup4 and PyQuery.

Provides a unified interface for extracting text, attributes,
and structured data from HTML documents.
"""

from __future__ import annotations

from typing import Any, Optional

from bs4 import BeautifulSoup
from pyquery import PyQuery as pq


class HtmlParser:
    """Thin wrapper around BS4 and PyQuery for common crawl tasks."""

    def __init__(self, html: str) -> None:
        self._html = html
        self._soup: Optional[BeautifulSoup] = None
        self._pq: Optional[pq] = None

    @property
    def soup(self) -> BeautifulSoup:
        """Lazy-loaded BeautifulSoup instance."""
        if self._soup is None:
            self._soup = BeautifulSoup(self._html, "lxml")
        return self._soup

    @property
    def doc(self) -> pq:
        """Lazy-loaded PyQuery instance."""
        if self._pq is None:
            self._pq = pq(self._html)
        return self._pq

    # ------------------------------------------------------------------
    # Convenience methods
    # ------------------------------------------------------------------

    def text(self, selector: Optional[str] = None) -> str:
        """Return the stripped text content. If *selector* is given,
        return the text of the first matching element."""
        if selector:
            el = self.doc(selector)
            return el.text().strip() if el else ""
        return self.doc.text().strip()

    def attr(self, selector: str, attribute: str) -> Optional[str]:
        """Return the value of *attribute* on the first matching element."""
        el = self.doc(selector)
        if el:
            return el.attr(attribute)
        return None

    def select_all(self, selector: str) -> list[pq]:
        """Return all matching elements as a list of PyQuery objects."""
        return [pq(e) for e in self.doc(selector)]

    def select_one(self, selector: str) -> Optional[pq]:
        """Return the first matching element as a PyQuery object."""
        el = self.doc(selector)
        return pq(el) if el else None

    def extract_links(self, selector: str = "a") -> list[dict[str, Optional[str]]]:
        """Extract href and text from all matching anchor tags."""
        links: list[dict[str, Optional[str]]] = []
        for el in self.doc(selector):
            a = pq(el)
            href = a.attr("href")
            text = a.text().strip()
            if href:
                links.append({"href": href, "text": text})
        return links

    def extract_json_ld(self) -> list[dict[str, Any]]:
        """Extract all JSON-LD script blocks."""
        try:
            import json

            blocks: list[dict[str, Any]] = []
            for script in self.soup.find_all("script", type="application/ld+json"):
                if script.string:
                    blocks.append(json.loads(script.string))
            return blocks
        except Exception:
            return []

    def extract_meta(self) -> dict[str, Optional[str]]:
        """Extract all <meta name='...' content='...'> tags."""
        meta: dict[str, Optional[str]] = {}
        for tag in self.soup.find_all("meta"):
            name = tag.get("name") or tag.get("property")
            content = tag.get("content")
            if name:
                meta[name] = content
        return meta

    def __repr__(self) -> str:
        return f"HtmlParser(len={len(self._html)})"
