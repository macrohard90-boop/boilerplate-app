"""HTML signal extraction for SEO scoring.

Parses rendered HTML to extract signals not available from the meta/crawl
data pipeline: viewport presence, lang attribute, favicon, image dimensions,
external links, body text, and H1 text.

Uses stdlib ``html.parser.HTMLParser`` — no external dependencies.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Elements whose text content should NOT be included in body_text.
_SKIP_TEXT_TAGS = frozenset({"script", "style", "noscript", "svg"})


@dataclass
class HTMLSignals:
    """Extracted SEO signals from rendered HTML."""

    has_viewport: bool = False
    has_lang: bool = False
    lang_value: str = ""
    has_favicon: bool = False
    images_missing_dimensions: int = 0
    total_images: int = 0
    external_links: int = 0
    body_text: str = ""
    h1_text: str = ""


class _SignalExtractor(HTMLParser):
    """Single-pass HTML parser that collects SEO signals."""

    def __init__(self, own_domain: str = "") -> None:
        super().__init__()
        self.signals = HTMLSignals()
        self._own_domain = own_domain.lower().strip().rstrip("/")

        # State tracking
        self._in_body = False
        self._skip_depth = 0  # depth inside script/style/noscript/svg
        self._in_h1 = False
        self._h1_parts: list[str] = []
        self._body_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        attr_dict = {k.lower(): v for k, v in attrs if v is not None}

        # <html lang="...">
        if tag_lower == "html":
            lang = attr_dict.get("lang", "")
            if lang:
                self.signals.has_lang = True
                self.signals.lang_value = lang

        # <meta name="viewport" ...>
        elif tag_lower == "meta":
            name = attr_dict.get("name", "").lower()
            if name == "viewport":
                self.signals.has_viewport = True

        # <link rel="icon" ...> / <link rel="shortcut icon" ...> / apple-touch-icon
        elif tag_lower == "link":
            rel = attr_dict.get("rel", "").lower()
            if any(kw in rel for kw in ("icon", "shortcut icon", "apple-touch-icon")):
                self.signals.has_favicon = True

        # <body>
        elif tag_lower == "body":
            self._in_body = True

        # Skip-text elements
        elif tag_lower in _SKIP_TEXT_TAGS:
            self._skip_depth += 1

        # <h1>
        elif tag_lower == "h1" and not self.signals.h1_text:
            # Only capture the first H1
            self._in_h1 = True
            self._h1_parts = []

        # <img> — count total + check for dimensions
        elif tag_lower == "img":
            self.signals.total_images += 1
            has_width = "width" in attr_dict
            has_height = "height" in attr_dict
            if not (has_width and has_height):
                self.signals.images_missing_dimensions += 1

        # <a href="..."> — count external links
        elif tag_lower == "a":
            href = attr_dict.get("href", "")
            if href and self._is_external(href):
                self.signals.external_links += 1

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()

        if tag_lower in _SKIP_TEXT_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

        elif tag_lower == "h1" and self._in_h1:
            self._in_h1 = False
            self.signals.h1_text = " ".join(self._h1_parts).strip()

        elif tag_lower == "body":
            self._in_body = False

    def handle_data(self, data: str) -> None:
        if self._in_h1:
            self._h1_parts.append(data)

        if self._in_body and self._skip_depth == 0:
            stripped = data.strip()
            if stripped:
                self._body_parts.append(stripped)

    def get_result(self) -> HTMLSignals:
        self.signals.body_text = " ".join(self._body_parts)
        return self.signals

    def _is_external(self, href: str) -> bool:
        """Check if a link is external (different domain)."""
        # Skip anchors, mailto, tel, javascript
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            return False

        # Protocol-relative or absolute URLs
        if href.startswith("//"):
            href = "https:" + href

        if href.startswith(("http://", "https://")):
            try:
                parsed = urlparse(href)
                link_domain = parsed.netloc.lower()
                if not self._own_domain:
                    return True  # No own domain set — treat all absolute as external
                # Strip www. for comparison
                link_clean = re.sub(r"^www\.", "", link_domain)
                own_clean = re.sub(r"^www\.", "", self._own_domain)
                return link_clean != own_clean
            except Exception:
                return False

        # Relative URLs are internal
        return False


def analyze_html(html: str, own_domain: str = "") -> HTMLSignals:
    """Parse raw HTML and extract SEO signals.

    Args:
        html: The raw HTML string to analyze.
        own_domain: The site's own domain (e.g. "example.com") for detecting
            external links.  When empty, all absolute URLs are counted as
            external.

    Returns:
        HTMLSignals with all extracted data.
    """
    parser = _SignalExtractor(own_domain)
    try:
        parser.feed(html)
    except Exception:
        logger.exception("HTML analysis failed")
    return parser.get_result()
