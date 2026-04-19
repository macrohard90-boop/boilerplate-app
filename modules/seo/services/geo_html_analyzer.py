"""GEO-specific HTML signal extraction.

Parses rendered HTML to extract signals relevant to Generative Engine
Optimization: extractability, fact density, authority signals, freshness
indicators, and structural metadata.

Uses stdlib ``html.parser.HTMLParser`` — no external dependencies.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Domains considered authoritative for GEO citation signals
AUTHORITY_TLDS = frozenset({".edu", ".gov"})
AUTHORITY_DOMAINS = frozenset(
    {
        "wikipedia.org",
        "arxiv.org",
        "scholar.google.com",
        "pubmed.ncbi.nlm.nih.gov",
        "nature.com",
        "sciencedirect.com",
        "springer.com",
        "jstor.org",
        "ieee.org",
        "acm.org",
        "who.int",
        "cdc.gov",
        "nih.gov",
        "un.org",
        "worldbank.org",
        "statista.com",
        "reuters.com",
        "apnews.com",
    }
)

# Patterns indicating statistics/data points in text
STAT_PATTERNS = re.compile(
    r"""
    \d+(?:\.\d+)?%                      |  # 42%, 3.5%
    \$\d[\d,]*(?:\.\d+)?                |  # $100, $1,000.50
    \d[\d,]*\+?\s*(?:times|fold|x)\b    |  # 4x, 3 times, 10-fold
    \d[\d,]*\s*(?:million|billion|trillion|thousand)\b |  # 5 million
    \b(?:increased?|decreased?|grew|dropped?|rose|fell)\s+(?:by\s+)?\d  |  # increased by 30
    \d[\d,]*(?:\.\d+)?\s*(?:out of|\/)\s*\d  # 8 out of 10, 3/4
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Question starters for H2 heading analysis
QUESTION_STARTERS = re.compile(
    r"^(?:what|how|why|when|where|which|who|can|does|is|are|do|should|will|would)\b",
    re.IGNORECASE,
)

# Skip these tags' text content
_SKIP_TEXT_TAGS = frozenset({"script", "style", "noscript", "svg"})

# Filler opening patterns that indicate non-direct answers
FILLER_OPENINGS = re.compile(
    r"^(?:welcome\s+to|in\s+this\s+(?:article|post|guide)|"
    r"today\s+we(?:'re|\s+are)\s+going\s+to|"
    r"have\s+you\s+ever\s+wondered|"
    r"let(?:'s|\s+us)\s+(?:dive|explore|take\s+a\s+look))",
    re.IGNORECASE,
)

# Quote attribution patterns
QUOTE_ATTRIBUTION = re.compile(
    r"(?:according\s+to|says?\s|said\s|notes?\s|explained?\s|stated?\s|"
    r"wrote\s|reported?\s|observed?\s|argued?\s|claimed?\s)"
    r"\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?",
    re.IGNORECASE,
)


@dataclass
class GEOHTMLSignals:
    """Extracted GEO signals from rendered HTML."""

    # Extractability
    first_paragraph_text: str = ""
    first_paragraph_word_count: int = 0
    h2_headings: list[str] = field(default_factory=list)
    h2_question_count: int = 0
    h2_sections: list[dict[str, str]] = field(default_factory=list)

    # Fact density
    stat_pattern_count: int = 0
    has_data_tables: bool = False
    data_table_count: int = 0

    # Authority
    has_blockquotes: bool = False
    blockquote_count: int = 0
    quote_attribution_count: int = 0
    outbound_domains: list[str] = field(default_factory=list)
    authority_domain_count: int = 0

    # Freshness
    stale_year_references: list[str] = field(default_factory=list)

    # General
    word_count: int = 0
    sentence_count: int = 0
    paragraph_count: int = 0


class _GEOSignalExtractor(HTMLParser):
    """Single-pass HTML parser that collects GEO-specific signals."""

    def __init__(self, own_domain: str = "") -> None:
        super().__init__()
        self.signals = GEOHTMLSignals()
        self._own_domain = own_domain.lower().strip().rstrip("/")

        # State tracking
        self._in_body = False
        self._skip_depth = 0
        self._in_h2 = False
        self._in_blockquote = False
        self._in_table = False
        self._table_has_th = False

        # Content accumulation
        self._h2_parts: list[str] = []
        self._body_parts: list[str] = []
        self._current_section_parts: list[str] = []
        self._current_h2_text: str = ""
        self._first_p_captured = False
        self._in_first_p = False
        self._first_p_parts: list[str] = []
        self._p_count = 0
        self._seen_domains: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        attr_dict = {k.lower(): v for k, v in attrs if v is not None}

        if tag_lower == "body":
            self._in_body = True

        elif tag_lower in _SKIP_TEXT_TAGS:
            self._skip_depth += 1

        elif tag_lower == "h2" and self._in_body and self._skip_depth == 0:
            # Save previous section if any
            if self._current_h2_text:
                section_text = " ".join(self._current_section_parts).strip()
                self.signals.h2_sections.append(
                    {
                        "heading": self._current_h2_text,
                        "first_sentences": self._get_first_sentences(section_text, 2),
                    }
                )
            self._in_h2 = True
            self._h2_parts = []
            self._current_section_parts = []

        elif tag_lower == "p" and self._in_body and self._skip_depth == 0:
            self._p_count += 1
            if not self._first_p_captured:
                self._in_first_p = True
                self._first_p_parts = []

        elif tag_lower == "blockquote" and self._in_body:
            self._in_blockquote = True
            self.signals.has_blockquotes = True
            self.signals.blockquote_count += 1

        elif tag_lower == "table" and self._in_body and self._skip_depth == 0:
            self._in_table = True
            self._table_has_th = False

        elif tag_lower == "th" and self._in_table:
            self._table_has_th = True

        elif tag_lower == "a" and self._in_body and self._skip_depth == 0:
            href = attr_dict.get("href", "")
            if href:
                self._check_outbound_link(href)

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()

        if tag_lower in _SKIP_TEXT_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

        elif tag_lower == "h2" and self._in_h2:
            self._in_h2 = False
            heading_text = " ".join(self._h2_parts).strip()
            self._current_h2_text = heading_text
            if heading_text:
                self.signals.h2_headings.append(heading_text)
                if "?" in heading_text or QUESTION_STARTERS.search(heading_text):
                    self.signals.h2_question_count += 1

        elif tag_lower == "p" and self._in_first_p:
            self._in_first_p = False
            self._first_p_captured = True
            text = " ".join(self._first_p_parts).strip()
            self.signals.first_paragraph_text = text
            self.signals.first_paragraph_word_count = len(text.split()) if text else 0

        elif tag_lower == "blockquote":
            self._in_blockquote = False

        elif tag_lower == "table" and self._in_table:
            if self._table_has_th:
                self.signals.has_data_tables = True
                self.signals.data_table_count += 1
            self._in_table = False

        elif tag_lower == "body":
            # Save last section
            if self._current_h2_text:
                section_text = " ".join(self._current_section_parts).strip()
                self.signals.h2_sections.append(
                    {
                        "heading": self._current_h2_text,
                        "first_sentences": self._get_first_sentences(section_text, 2),
                    }
                )
            self._in_body = False

    def handle_data(self, data: str) -> None:
        if self._in_h2:
            self._h2_parts.append(data)

        if self._in_first_p:
            self._first_p_parts.append(data)

        if self._in_body and self._skip_depth == 0:
            stripped = data.strip()
            if stripped:
                self._body_parts.append(stripped)
                # Accumulate section text (after current H2)
                if self._current_h2_text and not self._in_h2:
                    self._current_section_parts.append(stripped)

    def get_result(self) -> GEOHTMLSignals:
        body_text = " ".join(self._body_parts)

        # Word and sentence counts
        words = body_text.split()
        self.signals.word_count = len(words)
        # Simple sentence splitting on . ! ?
        sentences = re.split(r"[.!?]+", body_text)
        self.signals.sentence_count = len([s for s in sentences if s.strip()])
        self.signals.paragraph_count = self._p_count

        # Stat pattern count
        self.signals.stat_pattern_count = len(STAT_PATTERNS.findall(body_text))

        # Quote attribution count
        self.signals.quote_attribution_count = len(QUOTE_ATTRIBUTION.findall(body_text))

        # Stale year references
        current_year = datetime.now(timezone.utc).year
        year_refs = re.findall(r"\b(20\d{2})\b", body_text)
        for yr_str in year_refs:
            yr = int(yr_str)
            if yr < current_year - 1:
                self.signals.stale_year_references.append(yr_str)

        return self.signals

    def _check_outbound_link(self, href: str) -> None:
        """Check if a link is external and classify as authority or regular."""
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            return

        if href.startswith("//"):
            href = "https:" + href

        if not href.startswith(("http://", "https://")):
            return

        try:
            parsed = urlparse(href)
            domain = parsed.netloc.lower()
            if not domain:
                return

            # Check if external
            domain_clean = re.sub(r"^www\.", "", domain)
            own_clean = (
                re.sub(r"^www\.", "", self._own_domain) if self._own_domain else ""
            )
            if own_clean and domain_clean == own_clean:
                return  # Internal link

            if domain_clean in self._seen_domains:
                return  # Already counted
            self._seen_domains.add(domain_clean)
            self.signals.outbound_domains.append(domain_clean)

            # Check authority
            is_authority = False
            for tld in AUTHORITY_TLDS:
                if domain_clean.endswith(tld):
                    is_authority = True
                    break
            if not is_authority:
                for auth_domain in AUTHORITY_DOMAINS:
                    if domain_clean == auth_domain or domain_clean.endswith(
                        "." + auth_domain
                    ):
                        is_authority = True
                        break
            if is_authority:
                self.signals.authority_domain_count += 1

        except Exception:
            pass

    @staticmethod
    def _get_first_sentences(text: str, n: int = 2) -> str:
        """Extract the first N sentences from text."""
        if not text:
            return ""
        parts = re.split(r"(?<=[.!?])\s+", text, maxsplit=n)
        return " ".join(parts[:n]).strip()


def analyze_geo_html(html: str, own_domain: str = "") -> GEOHTMLSignals:
    """Parse raw HTML and extract GEO-specific signals.

    Args:
        html: The raw HTML string to analyze.
        own_domain: The site's own domain for detecting external links.

    Returns:
        GEOHTMLSignals with all extracted data.
    """
    parser = _GEOSignalExtractor(own_domain)
    try:
        parser.feed(html)
    except Exception:
        logger.exception("GEO HTML analysis failed")
    return parser.get_result()
