"""Page discovery service — filesystem scan + DB sync → seo.page_registry.

Provides a single source of truth for all known pages used by scoring,
sitemap, audit, crawler, and rescorer.
"""

import logging
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings

logger = logging.getLogger(__name__)

# Prefixes under frontend/app/ that are NOT public SEO targets.
# Everything under these directories is skipped during filesystem scan.
_EXCLUDED_PREFIXES = (
    "admin",
    "auth",
    "dashboard",
    "merchant",
    "protected",
    "orders",
    "cart",
    "checkout",
)


def scan_frontend_pages() -> list[dict[str, Any]]:
    """Scan the Next.js app directory for page.tsx files.

    Returns a list of dicts: {"path": str, "is_dynamic": bool}.
    Dynamic routes (containing [param]) are flagged but not excluded —
    their concrete instances come from the database.
    """
    app_dir = Path(settings.frontend_app_dir)
    if not app_dir.is_dir():
        logger.warning("Frontend app dir not found: %s", app_dir)
        return []

    pages: list[dict[str, Any]] = []

    for page_file in sorted(app_dir.glob("**/page.tsx")):
        # Get the path relative to the app dir, minus the filename
        rel = page_file.parent.relative_to(app_dir)
        route = str(rel) if str(rel) != "." else ""

        # Normalise to forward slashes (Windows compat)
        route = route.replace("\\", "/")

        # Skip excluded prefixes
        first_segment = route.split("/")[0] if route else ""
        if first_segment in _EXCLUDED_PREFIXES:
            continue

        # Detect dynamic segments like [slug] or [id]
        is_dynamic = "[" in route

        pages.append({"path": route, "is_dynamic": is_dynamic})

    # Sort by path string (not Path objects) for consistent ordering
    pages.sort(key=lambda p: p["path"])
    return pages


async def sync_page_registry(db: AsyncSession) -> dict[str, Any]:
    """Sync the page registry from filesystem + database sources.

    Upserts pages into seo.page_registry. Does NOT delete missing pages
    (to preserve score history). Returns counts.
    """
    all_pages: dict[str, dict[str, Any]] = {}

    # 1. Filesystem pages
    for page in scan_frontend_pages():
        all_pages[page["path"]] = {
            "source": "filesystem",
            "is_dynamic": page["is_dynamic"],
            "changefreq": "monthly",
            "priority": 1.0 if page["path"] == "" else 0.5,
        }

    # 2. Active products → products/{slug}
    try:
        product_rows = (
            (
                await db.execute(
                    text(
                        "SELECT slug FROM ecommerce.products "
                        "WHERE status = 'active' AND deleted_at IS NULL"
                    )
                )
            )
            .scalars()
            .all()
        )
        for slug in product_rows:
            path = f"products/{slug}"
            all_pages[path] = {
                "source": "database",
                "is_dynamic": False,
                "changefreq": "weekly",
                "priority": 0.8,
            }
    except Exception:
        logger.debug("Could not query products (table may not exist)")

    # 3. Categories → categories/{slug}
    try:
        cat_rows = (
            (await db.execute(text("SELECT slug FROM ecommerce.categories")))
            .scalars()
            .all()
        )
        for slug in cat_rows:
            path = f"categories/{slug}"
            all_pages[path] = {
                "source": "database",
                "is_dynamic": False,
                "changefreq": "weekly",
                "priority": 0.6,
            }
    except Exception:
        logger.debug("Could not query categories (table may not exist)")

    # 4. Meta overrides (may include custom paths not from filesystem or DB)
    try:
        override_rows = (
            (await db.execute(text("SELECT path FROM seo.meta_overrides")))
            .scalars()
            .all()
        )
        for path in override_rows:
            if path not in all_pages:
                all_pages[path] = {
                    "source": "override",
                    "is_dynamic": False,
                    "changefreq": "monthly",
                    "priority": 0.5,
                }
    except Exception:
        logger.debug("Could not query meta overrides (table may not exist)")

    # Upsert into page_registry
    added = 0
    updated = 0
    for path, meta in all_pages.items():
        result = await db.execute(
            text(
                "INSERT INTO seo.page_registry (path, source, is_dynamic, changefreq, priority) "
                "VALUES (:path, :source, :is_dynamic, :changefreq, :priority) "
                "ON CONFLICT (path) DO UPDATE SET "
                "  source = EXCLUDED.source, "
                "  is_dynamic = EXCLUDED.is_dynamic, "
                "  changefreq = EXCLUDED.changefreq, "
                "  priority = EXCLUDED.priority, "
                "  updated_at = NOW() "
                "WHERE seo.page_registry.source != 'manual'"
                # Don't overwrite manually added pages
            ),
            {
                "path": path,
                "source": meta["source"],
                "is_dynamic": meta["is_dynamic"],
                "changefreq": meta["changefreq"],
                "priority": meta["priority"],
            },
        )
        if result.rowcount > 0:
            # Can't distinguish insert vs update with ON CONFLICT, so count all
            added += 1

    await db.commit()

    total = (
        await db.execute(text("SELECT COUNT(*) FROM seo.page_registry"))
    ).scalar() or 0

    logger.info("Page registry sync: %d upserted, %d total", added, total)
    return {"added": added, "updated": updated, "total": total}


async def collect_all_paths(db: AsyncSession) -> list[str]:
    """Get all scoreable page paths from the registry.

    Returns non-dynamic pages sorted by path. This is the single source
    of truth used by scoring, sitemap, audit, crawler, and rescorer.
    """
    rows = (
        (
            await db.execute(
                text(
                    "SELECT path FROM seo.page_registry "
                    "WHERE is_dynamic = FALSE "
                    "ORDER BY path"
                )
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


async def get_page_registry(
    db: AsyncSession, page: int = 1, page_size: int = 50
) -> dict[str, Any]:
    """List all registered pages (paginated)."""
    offset = (page - 1) * page_size

    total = (
        await db.execute(text("SELECT COUNT(*) FROM seo.page_registry"))
    ).scalar() or 0

    rows = (
        (
            await db.execute(
                text(
                    "SELECT id, path, source, is_dynamic, changefreq, priority, "
                    "created_at, updated_at "
                    "FROM seo.page_registry ORDER BY path "
                    "LIMIT :lim OFFSET :off"
                ),
                {"lim": page_size, "off": offset},
            )
        )
        .mappings()
        .all()
    )

    return {
        "items": [
            {
                "id": str(r["id"]),
                "path": r["path"],
                "source": r["source"],
                "is_dynamic": r["is_dynamic"],
                "changefreq": r["changefreq"],
                "priority": float(r["priority"]),
                "created_at": str(r["created_at"]) if r["created_at"] else None,
                "updated_at": str(r["updated_at"]) if r["updated_at"] else None,
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def add_page(
    db: AsyncSession,
    path: str,
    changefreq: str = "monthly",
    priority: float = 0.5,
) -> dict[str, str]:
    """Manually register a page path."""
    await db.execute(
        text(
            "INSERT INTO seo.page_registry (path, source, is_dynamic, changefreq, priority) "
            "VALUES (:path, 'manual', FALSE, :changefreq, :priority) "
            "ON CONFLICT (path) DO UPDATE SET "
            "  source = 'manual', changefreq = EXCLUDED.changefreq, "
            "  priority = EXCLUDED.priority, updated_at = NOW()"
        ),
        {"path": path, "changefreq": changefreq, "priority": priority},
    )
    await db.commit()
    return {"message": f"Page '{path}' registered."}


async def remove_page(db: AsyncSession, path: str) -> bool:
    """Remove a page from the registry. Returns True if found."""
    result = await db.execute(
        text("DELETE FROM seo.page_registry WHERE path = :path"),
        {"path": path},
    )
    await db.commit()
    return result.rowcount > 0
