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
    """Build sitemap XML from the page registry."""
    base_url = settings.frontend_url.rstrip("/")

    # Get all non-dynamic pages from the registry
    rows = (
        (
            await db.execute(
                text(
                    "SELECT path, changefreq, priority "
                    "FROM seo.page_registry "
                    "WHERE is_dynamic = FALSE "
                    "ORDER BY path"
                )
            )
        )
        .mappings()
        .all()
    )

    urls: list[dict] = []

    # Look up product updated_at dates for lastmod
    product_dates: dict[str, str] = {}
    try:
        product_rows = (
            (
                await db.execute(
                    text(
                        "SELECT slug, updated_at FROM ecommerce.products "
                        "WHERE status = 'active' AND deleted_at IS NULL"
                    )
                )
            )
            .mappings()
            .all()
        )
        for p in product_rows:
            if p["updated_at"]:
                product_dates[p["slug"]] = str(p["updated_at"])[:10]
    except Exception:
        pass  # ecommerce tables may not exist

    for row in rows:
        path = row["path"]
        loc = f"{base_url}/" if path == "" else f"{base_url}/{path}"

        entry: dict = {
            "loc": loc,
            "changefreq": row["changefreq"],
            "priority": f"{float(row['priority']):.1f}",
        }

        # Add lastmod for product pages
        if path.startswith("products/"):
            slug = path[len("products/") :]
            if slug in product_dates:
                entry["lastmod"] = product_dates[slug]

        urls.append(entry)

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
