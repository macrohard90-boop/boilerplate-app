"""Sitemap.xml generation with Redis caching."""

import logging
from xml.etree.ElementTree import Element, SubElement, tostring

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.redis import get_redis

logger = logging.getLogger(__name__)

REDIS_KEY = "seo:sitemap:xml"
MAX_URLS_PER_SITEMAP = 50000


async def generate_sitemap(db: AsyncSession) -> str:
    """Generate sitemap XML, using Redis cache if available."""
    redis = await get_redis()
    cached = await redis.get(REDIS_KEY)
    if cached:
        return cached.decode() if isinstance(cached, bytes) else cached

    xml = await _build_sitemap(db)
    ttl = getattr(settings, "sitemap_cache_ttl", 3600)
    await redis.set(REDIS_KEY, xml, ex=ttl)
    return xml


async def invalidate_cache() -> None:
    """Delete the cached sitemap so it regenerates on next request."""
    redis = await get_redis()
    await redis.delete(REDIS_KEY)


async def _build_sitemap(db: AsyncSession) -> str:
    """Build sitemap XML from database content."""
    base_url = settings.frontend_url.rstrip("/")

    # Collect all URLs
    urls: list[dict] = []

    # Static pages
    urls.append({"loc": f"{base_url}/", "changefreq": "monthly", "priority": "1.0"})
    urls.append(
        {"loc": f"{base_url}/about", "changefreq": "monthly", "priority": "0.5"}
    )
    urls.append(
        {"loc": f"{base_url}/contact", "changefreq": "monthly", "priority": "0.5"}
    )

    # Products
    products = (
        await db.execute(
            text(
                "SELECT slug, updated_at FROM ecommerce.products "
                "WHERE status = 'active' AND deleted_at IS NULL "
                "ORDER BY updated_at DESC"
            )
        )
    ).mappings().all()

    for p in products:
        entry: dict = {
            "loc": f"{base_url}/products/{p['slug']}",
            "changefreq": "weekly",
            "priority": "0.8",
        }
        if p["updated_at"]:
            entry["lastmod"] = str(p["updated_at"])[:10]  # YYYY-MM-DD
        urls.append(entry)

    # Categories
    categories = (
        await db.execute(
            text(
                "SELECT slug FROM ecommerce.categories ORDER BY sort_order, name"
            )
        )
    ).mappings().all()

    for c in categories:
        urls.append(
            {
                "loc": f"{base_url}/categories/{c['slug']}",
                "changefreq": "weekly",
                "priority": "0.6",
            }
        )

    # If >50k URLs, build a sitemap index
    if len(urls) > MAX_URLS_PER_SITEMAP:
        return _build_sitemap_index(urls, base_url)

    return _build_urlset(urls)


def _build_urlset(urls: list[dict]) -> str:
    """Build a single <urlset> sitemap."""
    urlset = Element("urlset")
    urlset.set("xmlns", "http://www.sitemaps.org/schemas/sitemap/0.9")

    for u in urls:
        url_el = SubElement(urlset, "url")
        SubElement(url_el, "loc").text = u["loc"]
        if "lastmod" in u:
            SubElement(url_el, "lastmod").text = u["lastmod"]
        if "changefreq" in u:
            SubElement(url_el, "changefreq").text = u["changefreq"]
        if "priority" in u:
            SubElement(url_el, "priority").text = u["priority"]

    return '<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(
        urlset, encoding="unicode"
    )


def _build_sitemap_index(urls: list[dict], base_url: str) -> str:
    """Build a <sitemapindex> for large catalogs (>50k URLs)."""
    chunks = [
        urls[i : i + MAX_URLS_PER_SITEMAP]
        for i in range(0, len(urls), MAX_URLS_PER_SITEMAP)
    ]

    index = Element("sitemapindex")
    index.set("xmlns", "http://www.sitemaps.org/schemas/sitemap/0.9")

    for i, _ in enumerate(chunks):
        sitemap = SubElement(index, "sitemap")
        SubElement(sitemap, "loc").text = f"{base_url}/sitemap-{i}.xml"

    return '<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(
        index, encoding="unicode"
    )
