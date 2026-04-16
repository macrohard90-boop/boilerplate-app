"""Lightweight HTML meta verification — fetches rendered page and extracts meta tags.

Uses httpx + html.parser instead of Playwright. Works because Next.js
server-renders all meta tags without JavaScript.
"""

import logging
from html.parser import HTMLParser
from typing import Any

import httpx

from backend.core.config import settings
from modules.seo.services.meta_service import get_meta_tags

logger = logging.getLogger(__name__)


class _MetaExtractor(HTMLParser):
    """Extract SEO-relevant meta tags from HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.title: str | None = None
        self.description: str | None = None
        self.canonical: str | None = None
        self.robots: str | None = None
        self.og_tags: dict[str, str] = {}
        self.twitter_tags: dict[str, str] = {}

        self._in_title = False
        self._title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = {k: v for k, v in attrs if v is not None}

        if tag == "title":
            self._in_title = True
            self._title_parts = []

        elif tag == "meta":
            name = attr_dict.get("name", "").lower()
            prop = attr_dict.get("property", "").lower()
            content = attr_dict.get("content", "")

            if name == "description":
                self.description = content
            elif name == "robots":
                self.robots = content
            elif prop.startswith("og:"):
                self.og_tags[prop] = content
            elif name.startswith("twitter:"):
                self.twitter_tags[name] = content

        elif tag == "link":
            rel = attr_dict.get("rel", "").lower()
            href = attr_dict.get("href", "")
            if rel == "canonical" and href:
                self.canonical = href

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title" and self._in_title:
            self._in_title = False
            self.title = "".join(self._title_parts).strip()


async def verify_rendered_meta(path: str) -> dict[str, Any]:
    """Fetch the live page via HTTP and extract meta tags from the HTML."""
    base = settings.internal_frontend_url or settings.frontend_url
    url = f"{base}/{path}"

    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=15, follow_redirects=True)
        response.raise_for_status()

    parser = _MetaExtractor()
    parser.feed(response.text)

    return {
        "title": parser.title,
        "description": parser.description,
        "canonical_url": parser.canonical,
        "robots": parser.robots,
        "og_title": parser.og_tags.get("og:title"),
        "og_description": parser.og_tags.get("og:description"),
        "og_image": parser.og_tags.get("og:image"),
    }


async def verify_and_compare(db: Any, path: str) -> dict[str, Any]:
    """Fetch rendered HTML, compare to API meta, return mismatches."""
    rendered = await verify_rendered_meta(path)
    api_meta = await get_meta_tags(db, path)

    expected = {
        "title": api_meta.get("title"),
        "description": api_meta.get("description"),
        "canonical_url": api_meta.get("canonical_url"),
        "robots": api_meta.get("robots"),
        "og_title": (api_meta.get("og_tags") or {}).get("og:title"),
        "og_description": (api_meta.get("og_tags") or {}).get("og:description"),
        "og_image": (api_meta.get("og_tags") or {}).get("og:image"),
    }

    mismatches = []
    for field in expected:
        exp = expected[field]
        act = rendered.get(field)

        # Normalize None vs empty string
        exp_norm = (exp or "").strip() if exp else ""
        act_norm = (act or "").strip() if act else ""

        # Title: use substring check (rendered may include site name suffix)
        if field == "title" and exp_norm and act_norm:
            if exp_norm not in act_norm:
                mismatches.append(
                    {"field": field, "expected": exp, "actual": act}
                )
        elif exp_norm != act_norm:
            mismatches.append({"field": field, "expected": exp, "actual": act})

    return {
        "rendered": rendered,
        "expected": expected,
        "mismatches": mismatches,
        "match": len(mismatches) == 0,
    }
