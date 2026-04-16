"""SEO crawler service — verifies rendered HTML matches API-generated meta.

Uses Playwright to load pages in a headless browser and extract the actual
meta tags, OG tags, Twitter cards, structured data, and headings from the
rendered HTML. Compares this to what the backend API generates.

Only available when ENABLE_SEO_CRAWLER=true and Playwright is installed.
"""

import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from modules.seo.services.meta_service import get_meta_tags

logger = logging.getLogger(__name__)


async def crawl_page(db: AsyncSession, path: str) -> dict[str, Any]:
    """Crawl a rendered page and compare to API meta."""
    from playwright.async_api import async_playwright

    base_url = settings.frontend_url.rstrip("/")
    full_url = f"{base_url}/{path.lstrip('/')}"

    rendered: dict[str, Any] = {}
    status_code: int | None = None

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            response = await page.goto(full_url, wait_until="networkidle", timeout=30000)
            status_code = response.status if response else None

            rendered = {
                "title": await page.title(),
                "description": await page.evaluate(
                    '() => document.querySelector("meta[name=description]")?.content || null'
                ),
                "og_tags": await _extract_og_tags(page),
                "twitter_tags": await _extract_twitter_tags(page),
                "structured_data": await _extract_json_ld(page),
                "headings": await _extract_headings(page),
                "images_without_alt": await _extract_images_without_alt(page),
                "canonical": await page.evaluate(
                    '() => document.querySelector("link[rel=canonical]")?.href || null'
                ),
                "robots": await page.evaluate(
                    '() => document.querySelector("meta[name=robots]")?.content || null'
                ),
                "internal_links": await page.evaluate(
                    '() => document.querySelectorAll(\'a[href^="/"]\').length'
                ),
                "content_length": await page.evaluate(
                    "() => (document.body?.innerText || '').length"
                ),
            }
        except Exception:
            logger.exception("Failed to crawl %s", full_url)
        finally:
            await browser.close()

    # Get API meta for comparison
    api_meta = await get_meta_tags(db, path)

    # Compute mismatches
    mismatches = _compare_rendered_vs_api(rendered, api_meta)

    # Store result
    await db.execute(
        text(
            "INSERT INTO seo.crawl_results "
            "(path, status_code, rendered_meta, api_meta, mismatches) "
            "VALUES (:path, :status_code, CAST(:rendered AS jsonb), CAST(:api AS jsonb), CAST(:mismatches AS jsonb))"
        ),
        {
            "path": path,
            "status_code": status_code,
            "rendered": json.dumps(rendered),
            "api": json.dumps(api_meta, default=str),
            "mismatches": json.dumps(mismatches),
        },
    )
    await db.commit()

    return {
        "path": path,
        "status_code": status_code,
        "rendered": rendered,
        "api_meta": api_meta,
        "mismatches": mismatches,
    }


async def crawl_all_pages(db: AsyncSession) -> list[dict[str, Any]]:
    """Crawl all known pages from the sitemap."""
    from modules.seo.services.scoring_service import _collect_all_paths
    import asyncio

    paths = await _collect_all_paths(db)
    results = []
    for path in paths:
        try:
            result = await crawl_page(db, path)
            results.append({"path": path, "mismatches": len(result["mismatches"])})
        except Exception:
            logger.exception("Failed to crawl path: %s", path)
        await asyncio.sleep(1)  # Be gentle — each crawl launches a browser
    return results


async def list_crawl_results(
    db: AsyncSession, page: int = 1, page_size: int = 20
) -> dict[str, Any]:
    """List crawl results, newest first."""
    offset = (page - 1) * page_size

    total = (
        await db.execute(text("SELECT COUNT(*) FROM seo.crawl_results"))
    ).scalar() or 0

    rows = (
        await db.execute(
            text(
                "SELECT id, path, status_code, rendered_meta, api_meta, "
                "mismatches, crawled_at "
                "FROM seo.crawl_results ORDER BY crawled_at DESC "
                "LIMIT :lim OFFSET :off"
            ),
            {"lim": page_size, "off": offset},
        )
    ).mappings().all()

    return {
        "items": [
            {
                "id": str(r["id"]),
                "path": r["path"],
                "status_code": r["status_code"],
                "rendered_meta": r["rendered_meta"],
                "api_meta": r["api_meta"],
                "mismatches": r["mismatches"],
                "crawled_at": str(r["crawled_at"]),
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def get_crawl_result(
    db: AsyncSession, result_id: str
) -> dict[str, Any] | None:
    """Get a single crawl result by ID."""
    row = (
        await db.execute(
            text(
                "SELECT id, path, status_code, rendered_meta, api_meta, "
                "mismatches, crawled_at "
                "FROM seo.crawl_results WHERE id = :id"
            ),
            {"id": result_id},
        )
    ).mappings().first()

    if not row:
        return None

    return {
        "id": str(row["id"]),
        "path": row["path"],
        "status_code": row["status_code"],
        "rendered_meta": row["rendered_meta"],
        "api_meta": row["api_meta"],
        "mismatches": row["mismatches"],
        "crawled_at": str(row["crawled_at"]),
    }


# ── Extraction helpers ────────────────────────────────────────


async def _extract_og_tags(page: Any) -> dict[str, str]:
    """Extract all Open Graph meta tags from the page."""
    return await page.evaluate("""
        () => {
            const tags = {};
            document.querySelectorAll('meta[property^="og:"]').forEach(el => {
                tags[el.getAttribute('property')] = el.getAttribute('content') || '';
            });
            return tags;
        }
    """)


async def _extract_twitter_tags(page: Any) -> dict[str, str]:
    """Extract all Twitter Card meta tags from the page."""
    return await page.evaluate("""
        () => {
            const tags = {};
            document.querySelectorAll('meta[name^="twitter:"]').forEach(el => {
                tags[el.getAttribute('name')] = el.getAttribute('content') || '';
            });
            return tags;
        }
    """)


async def _extract_json_ld(page: Any) -> list[dict[str, Any]]:
    """Extract all JSON-LD structured data scripts."""
    return await page.evaluate("""
        () => {
            const scripts = document.querySelectorAll('script[type="application/ld+json"]');
            return Array.from(scripts).map(s => {
                try { return JSON.parse(s.textContent); }
                catch { return null; }
            }).filter(Boolean);
        }
    """)


async def _extract_headings(page: Any) -> list[dict[str, str]]:
    """Extract all headings (h1-h6) from the page."""
    return await page.evaluate("""
        () => {
            const headings = [];
            document.querySelectorAll('h1, h2, h3, h4, h5, h6').forEach(el => {
                headings.push({ tag: el.tagName.toLowerCase(), text: el.textContent.trim() });
            });
            return headings;
        }
    """)


async def _extract_images_without_alt(page: Any) -> list[str]:
    """Extract images that are missing alt text."""
    return await page.evaluate("""
        () => {
            return Array.from(document.querySelectorAll('img'))
                .filter(img => !img.alt || img.alt.trim() === '')
                .map(img => img.src)
                .slice(0, 50);
        }
    """)


def _compare_rendered_vs_api(
    rendered: dict[str, Any], api_meta: dict[str, Any]
) -> list[dict[str, Any]]:
    """Compare rendered HTML meta to API-generated meta and find mismatches."""
    mismatches = []

    # Title
    api_title = api_meta.get("title")
    rendered_title = rendered.get("title")
    if api_title and rendered_title and api_title not in rendered_title:
        mismatches.append({
            "field": "title",
            "expected": api_title,
            "actual": rendered_title,
            "severity": "critical",
        })
    elif api_title and not rendered_title:
        mismatches.append({
            "field": "title",
            "expected": api_title,
            "actual": None,
            "severity": "critical",
        })

    # Description
    api_desc = api_meta.get("description")
    rendered_desc = rendered.get("description")
    if api_desc and api_desc != rendered_desc:
        mismatches.append({
            "field": "description",
            "expected": api_desc,
            "actual": rendered_desc,
            "severity": "critical",
        })

    # Canonical
    api_canonical = api_meta.get("canonical_url")
    rendered_canonical = rendered.get("canonical")
    if api_canonical and api_canonical != rendered_canonical:
        mismatches.append({
            "field": "canonical_url",
            "expected": api_canonical,
            "actual": rendered_canonical,
            "severity": "warning",
        })

    # OG tags
    api_og = api_meta.get("og_tags") or {}
    rendered_og = rendered.get("og_tags") or {}
    for key in ("og:title", "og:description", "og:image"):
        api_val = api_og.get(key)
        rendered_val = rendered_og.get(key)
        if api_val and api_val != rendered_val:
            mismatches.append({
                "field": key,
                "expected": api_val,
                "actual": rendered_val,
                "severity": "warning",
            })

    # Twitter tags
    api_tw = api_meta.get("twitter_tags") or {}
    rendered_tw = rendered.get("twitter_tags") or {}
    for key in ("twitter:card", "twitter:title", "twitter:description"):
        api_val = api_tw.get(key)
        rendered_val = rendered_tw.get(key)
        if api_val and api_val != rendered_val:
            mismatches.append({
                "field": key,
                "expected": api_val,
                "actual": rendered_val,
                "severity": "warning",
            })

    # Structured data count
    api_sd_count = len(api_meta.get("structured_data") or [])
    rendered_sd_count = len(rendered.get("structured_data") or [])
    if api_sd_count > 0 and rendered_sd_count == 0:
        mismatches.append({
            "field": "structured_data",
            "expected": f"{api_sd_count} schema(s)",
            "actual": "0 schemas",
            "severity": "critical",
        })
    elif api_sd_count != rendered_sd_count:
        mismatches.append({
            "field": "structured_data",
            "expected": f"{api_sd_count} schema(s)",
            "actual": f"{rendered_sd_count} schema(s)",
            "severity": "info",
        })

    return mismatches
