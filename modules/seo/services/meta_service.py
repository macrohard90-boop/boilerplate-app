"""Meta tag management — auto-generation and custom overrides."""

import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings


def _truncate(value: str | None, limit: int) -> str | None:
    """Truncate string to limit, adding ellipsis if needed."""
    if not value:
        return value
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def _build_robots(index: bool, follow: bool) -> str:
    idx = "index" if index else "noindex"
    fol = "follow" if follow else "nofollow"
    return f"{idx}, {fol}"


async def get_meta_tags(db: AsyncSession, path: str) -> dict[str, Any]:
    """Get meta tags for a page path.

    Priority: custom override > auto-generated from content.
    Enriched with OG tags, Twitter tags, and structured data.
    """
    from modules.seo.services.og_service import get_og_tags
    from modules.seo.services.structured_data_service import (
        get_breadcrumb_schema,
        get_organization_schema,
        get_product_schema,
        get_website_schema,
    )

    # Check for custom override first
    override = (
        await db.execute(
            text(
                "SELECT id, path, title, description, robots_index, robots_follow, "
                "canonical_url FROM seo.meta_overrides WHERE path = :path"
            ),
            {"path": path},
        )
    ).mappings().first()

    if override:
        result = {
            "path": path,
            "title": override["title"],
            "description": override["description"],
            "canonical_url": override["canonical_url"]
            or f"{settings.frontend_url}/{path.lstrip('/')}",
            "robots": _build_robots(override["robots_index"], override["robots_follow"]),
            "is_custom": True,
            "og_tags": None,
            "twitter_tags": None,
            "structured_data": None,
        }
    else:
        result = await _auto_generate(db, path)

    # Enrich with OG + Twitter tags
    og_data = await get_og_tags(db, path)
    result["og_tags"] = og_data.get("og_tags")
    result["twitter_tags"] = og_data.get("twitter_tags")

    # Enrich with structured data
    structured: list[dict] = [get_organization_schema(), get_website_schema()]

    product_match = re.match(r"^/?products/([^/]+)$", path)
    if product_match:
        product_sd = await get_product_schema(db, product_match.group(1))
        if product_sd:
            structured.append(product_sd)

    category_match = re.match(r"^/?categories/([^/]+)$", path)
    if category_match:
        breadcrumb = await get_breadcrumb_schema(db, category_match.group(1))
        if breadcrumb:
            structured.append(breadcrumb)

    result["structured_data"] = structured
    return result


async def _auto_generate(db: AsyncSession, path: str) -> dict[str, Any]:
    """Auto-generate meta tags from product/category content."""
    canonical = f"{settings.frontend_url}/{path.lstrip('/')}"

    # Product page: /products/{slug}
    match = re.match(r"^/?products/([^/]+)$", path)
    if match:
        slug = match.group(1)
        product = (
            await db.execute(
                text(
                    "SELECT name, description, base_price, currency "
                    "FROM ecommerce.products "
                    "WHERE slug = :slug AND status = 'active' AND deleted_at IS NULL"
                ),
                {"slug": slug},
            )
        ).mappings().first()

        if product:
            title = _truncate(product["name"], 60)
            desc = _truncate(
                product["description"] or f"Buy {product['name']}",
                160,
            )
            return {
                "path": path,
                "title": title,
                "description": desc,
                "canonical_url": canonical,
                "robots": "index, follow",
                "is_custom": False,
                "og_tags": None,
                "twitter_tags": None,
                "structured_data": None,
            }

    # Category page: /categories/{slug}
    match = re.match(r"^/?categories/([^/]+)$", path)
    if match:
        slug = match.group(1)
        category = (
            await db.execute(
                text(
                    "SELECT name, description FROM ecommerce.categories "
                    "WHERE slug = :slug"
                ),
                {"slug": slug},
            )
        ).mappings().first()

        if category:
            title = _truncate(category["name"], 60)
            desc = _truncate(
                category["description"] or f"Browse {category['name']} products",
                160,
            )
            return {
                "path": path,
                "title": title,
                "description": desc,
                "canonical_url": canonical,
                "robots": "index, follow",
                "is_custom": False,
                "og_tags": None,
                "twitter_tags": None,
                "structured_data": None,
            }

    # Products listing page
    if path.strip("/") == "products":
        return {
            "path": path,
            "title": _truncate(f"Products | {settings.site_name}", 60),
            "description": _truncate(
                f"Browse the full catalog at {settings.site_name}. "
                "Discover quality products across all categories.",
                160,
            ),
            "canonical_url": canonical,
            "robots": "index, follow",
            "is_custom": False,
            "og_tags": None,
            "twitter_tags": None,
            "structured_data": None,
        }

    # About page
    if path.strip("/") == "about":
        return {
            "path": path,
            "title": _truncate(f"About | {settings.site_name}", 60),
            "description": _truncate(
                f"Learn about {settings.site_name}, our mission, and what sets us apart.",
                160,
            ),
            "canonical_url": canonical,
            "robots": "index, follow",
            "is_custom": False,
            "og_tags": None,
            "twitter_tags": None,
            "structured_data": None,
        }

    # Contact page
    if path.strip("/") == "contact":
        return {
            "path": path,
            "title": _truncate(f"Contact | {settings.site_name}", 60),
            "description": _truncate(
                f"Get in touch with {settings.site_name}. "
                "We'd love to hear from you.",
                160,
            ),
            "canonical_url": canonical,
            "robots": "index, follow",
            "is_custom": False,
            "og_tags": None,
            "twitter_tags": None,
            "structured_data": None,
        }

    # Default: use site name
    return {
        "path": path,
        "title": _truncate(settings.site_name, 60),
        "description": _truncate(f"Welcome to {settings.site_name}", 160),
        "canonical_url": canonical,
        "robots": "index, follow",
        "is_custom": False,
        "og_tags": None,
        "twitter_tags": None,
        "structured_data": None,
    }


async def set_meta_override(
    db: AsyncSession,
    path: str,
    title: str | None,
    description: str | None,
    robots_index: bool,
    robots_follow: bool,
    canonical_url: str | None,
    user_id: str,
) -> dict[str, Any]:
    """Create or update a custom meta tag override."""
    title = _truncate(title, 60)
    description = _truncate(description, 160)

    existing = (
        await db.execute(
            text("SELECT id FROM seo.meta_overrides WHERE path = :path"),
            {"path": path},
        )
    ).mappings().first()

    if existing:
        await db.execute(
            text(
                "UPDATE seo.meta_overrides SET title = :title, description = :desc, "
                "robots_index = :ri, robots_follow = :rf, canonical_url = :cu, "
                "updated_at = NOW() WHERE path = :path"
            ),
            {
                "path": path,
                "title": title,
                "desc": description,
                "ri": robots_index,
                "rf": robots_follow,
                "cu": canonical_url,
            },
        )
    else:
        await db.execute(
            text(
                "INSERT INTO seo.meta_overrides "
                "(path, title, description, robots_index, robots_follow, canonical_url, created_by) "
                "VALUES (:path, :title, :desc, :ri, :rf, :cu, :uid)"
            ),
            {
                "path": path,
                "title": title,
                "desc": description,
                "ri": robots_index,
                "rf": robots_follow,
                "cu": canonical_url,
                "uid": user_id,
            },
        )
    await db.commit()

    # Take audit snapshot if scoring is enabled
    if settings.enable_seo_scoring:
        try:
            from modules.seo.services.snapshot_service import take_snapshot

            await take_snapshot(db, path, trigger="override_change", changed_by=user_id)
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                "Failed to take snapshot after override set for %s", path
            )

    return {"message": f"Meta override set for {path}"}


async def delete_meta_override(db: AsyncSession, path: str) -> dict[str, Any]:
    """Remove a custom meta tag override."""
    result = await db.execute(
        text("DELETE FROM seo.meta_overrides WHERE path = :path"),
        {"path": path},
    )
    await db.commit()
    if result.rowcount == 0:
        raise ValueError(f"No override found for path: {path}")

    # Take audit snapshot if scoring is enabled
    if settings.enable_seo_scoring:
        try:
            from modules.seo.services.snapshot_service import take_snapshot

            await take_snapshot(db, path, trigger="override_change")
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                "Failed to take snapshot after override delete for %s", path
            )

    return {"message": f"Meta override removed for {path}"}


async def list_meta_overrides(
    db: AsyncSession, page: int = 1, page_size: int = 20
) -> dict[str, Any]:
    """List all custom meta tag overrides (paginated)."""
    offset = (page - 1) * page_size

    total = (
        await db.execute(text("SELECT COUNT(*) FROM seo.meta_overrides"))
    ).scalar() or 0

    rows = (
        await db.execute(
            text(
                "SELECT id, path, title, description, robots_index, robots_follow, "
                "canonical_url, created_at, updated_at "
                "FROM seo.meta_overrides ORDER BY path "
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
                "title": r["title"],
                "description": r["description"],
                "robots_index": r["robots_index"],
                "robots_follow": r["robots_follow"],
                "canonical_url": r["canonical_url"],
                "created_at": str(r["created_at"]) if r["created_at"] else None,
                "updated_at": str(r["updated_at"]) if r["updated_at"] else None,
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
