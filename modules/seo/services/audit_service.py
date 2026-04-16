"""Site-wide SEO audit service.

Runs 15 checks across 4 categories (technical, content, social, performance)
to surface every SEO gap when spinning up a new instance or periodically.

Unlike per-page scoring, audit checks are site-wide: duplicate titles,
canonical conflicts, missing metadata across all pages, etc.
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from modules.seo.services.meta_service import get_meta_tags

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class AuditCheck:
    check_id: str
    category: str  # "technical", "content", "social", "performance"
    severity: str  # "critical", "warning", "info"
    passed: bool
    title: str
    description: str
    recommendation: str | None = None
    affected_pages: list[str] | None = None


@dataclass
class AuditReport:
    checks: list[AuditCheck]
    summary: dict[str, int] = field(default_factory=dict)
    score: int = 0
    created_at: str = ""


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def run_full_audit(db: AsyncSession, user_id: str | None = None) -> AuditReport:
    """Run a full site audit and store the result."""
    from modules.seo.services.scoring_service import _collect_all_paths

    paths = await _collect_all_paths(db)

    # Gather meta for all pages
    page_metas: dict[str, dict[str, Any]] = {}
    for path in paths:
        try:
            page_metas[path] = await get_meta_tags(db, path)
        except Exception:
            logger.exception("Failed to get meta for path: %s", path)

    # Gather crawl data (latest per path)
    crawl_data = await _get_all_crawl_data(db)

    # Run all checks
    checks: list[AuditCheck] = []
    checks.append(_check_ssl_configured())
    checks.append(_check_robots_valid())
    checks.append(await _check_sitemap_freshness(db))
    checks.append(_check_canonical_conflicts(page_metas))
    checks.append(_check_duplicate_titles(page_metas))
    checks.append(_check_duplicate_descriptions(page_metas))
    checks.append(_check_all_pages_have_meta(page_metas))
    checks.append(_check_thin_content(crawl_data))
    checks.append(_check_missing_h1(crawl_data))
    checks.append(_check_missing_alt_images(crawl_data))
    checks.append(_check_all_pages_have_og(page_metas))
    checks.append(_check_custom_og_images(page_metas))
    checks.append(_check_image_heavy_pages(crawl_data))
    checks.append(_check_no_404_pages(crawl_data))
    checks.append(_check_sitemap_coverage(paths, page_metas))

    # Compute summary
    summary = {
        "critical": sum(1 for c in checks if not c.passed and c.severity == "critical"),
        "warning": sum(1 for c in checks if not c.passed and c.severity == "warning"),
        "info": sum(1 for c in checks if not c.passed and c.severity == "info"),
        "passed": sum(1 for c in checks if c.passed),
        "total": len(checks),
    }

    # Site health score: weighted by severity
    total_weight = len(checks) * 3  # max 3 per check (critical weight)
    earned = 0
    for c in checks:
        weight = {"critical": 3, "warning": 2, "info": 1}.get(c.severity, 1)
        if c.passed:
            earned += weight
    score = round(earned / total_weight * 100) if total_weight > 0 else 0

    report = AuditReport(
        checks=checks,
        summary=summary,
        score=score,
    )

    # Store in DB
    checks_json = [asdict(c) for c in checks]
    result = await db.execute(
        text(
            "INSERT INTO seo.site_audits (checks, summary, score, triggered_by) "
            "VALUES (CAST(:checks AS jsonb), CAST(:summary AS jsonb), :score, :uid) "
            "RETURNING id, created_at"
        ),
        {
            "checks": json.dumps(checks_json),
            "summary": json.dumps(summary),
            "score": score,
            "uid": user_id,
        },
    )
    row = result.mappings().first()
    await db.commit()
    if row:
        report.created_at = str(row["created_at"])

    return report


async def get_latest_audit(db: AsyncSession) -> dict[str, Any] | None:
    """Get the most recent site audit."""
    row = (
        await db.execute(
            text(
                "SELECT id, checks, summary, score, triggered_by, created_at "
                "FROM seo.site_audits ORDER BY created_at DESC LIMIT 1"
            )
        )
    ).mappings().first()
    if not row:
        return None
    return _format_audit_row(row)


async def list_audits(
    db: AsyncSession, page: int = 1, page_size: int = 20
) -> dict[str, Any]:
    """List past audits, newest first."""
    offset = (page - 1) * page_size

    total = (
        await db.execute(text("SELECT COUNT(*) FROM seo.site_audits"))
    ).scalar() or 0

    rows = (
        await db.execute(
            text(
                "SELECT id, checks, summary, score, triggered_by, created_at "
                "FROM seo.site_audits ORDER BY created_at DESC "
                "LIMIT :lim OFFSET :off"
            ),
            {"lim": page_size, "off": offset},
        )
    ).mappings().all()

    return {
        "items": [_format_audit_row(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def _format_audit_row(row: Any) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "checks": row["checks"],
        "summary": row["summary"],
        "score": row["score"],
        "triggered_by": str(row["triggered_by"]) if row["triggered_by"] else None,
        "created_at": str(row["created_at"]),
    }


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------


async def _get_all_crawl_data(db: AsyncSession) -> dict[str, dict[str, Any]]:
    """Get the latest crawl result for each path."""
    try:
        rows = (
            await db.execute(
                text(
                    "SELECT DISTINCT ON (path) path, status_code, rendered_meta "
                    "FROM seo.crawl_results ORDER BY path, crawled_at DESC"
                )
            )
        ).mappings().all()
        return {
            r["path"]: {
                "status_code": r["status_code"],
                **(r["rendered_meta"] or {}),
            }
            for r in rows
        }
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Technical checks
# ---------------------------------------------------------------------------


def _check_ssl_configured() -> AuditCheck:
    """Check that FRONTEND_URL uses HTTPS (or localhost in dev)."""
    url = settings.frontend_url
    is_dev = "localhost" in url or "127.0.0.1" in url
    passed = url.startswith("https://") or is_dev
    return AuditCheck(
        check_id="ssl_configured",
        category="technical",
        severity="critical",
        passed=passed,
        title="SSL/HTTPS configured",
        description="Frontend URL uses HTTPS for secure connections."
        if passed
        else "Frontend URL is not using HTTPS.",
        recommendation=None
        if passed
        else "Set FRONTEND_URL to an https:// URL in production.",
    )


def _check_robots_valid() -> AuditCheck:
    """Check that robots.txt allows important paths."""
    from modules.seo.services.robots_service import generate_robots

    robots_txt = generate_robots()
    # Check it doesn't block the root or important pages.
    # A bare "Disallow: /" blocks everything; "Disallow: /api/" is fine.
    lines = robots_txt.strip().split("\n")
    blocks_root = any(line.strip() == "Disallow: /" for line in lines)
    has_sitemap = "Sitemap:" in robots_txt

    passed = has_sitemap and not blocks_root
    issues = []
    if not has_sitemap:
        issues.append("no Sitemap directive")
    if blocks_root:
        issues.append("blocks root path")

    return AuditCheck(
        check_id="robots_valid",
        category="technical",
        severity="critical",
        passed=passed,
        title="robots.txt valid",
        description="robots.txt allows crawling and includes sitemap reference."
        if passed
        else f"robots.txt issues: {', '.join(issues)}.",
        recommendation=None if passed else "Fix robots.txt to allow crawling of public pages and include a Sitemap directive.",
    )


def _check_canonical_conflicts(page_metas: dict[str, dict[str, Any]]) -> AuditCheck:
    """Check for pages sharing the same canonical URL."""
    canonicals: dict[str, list[str]] = {}
    for path, meta in page_metas.items():
        canon = meta.get("canonical_url")
        if canon:
            canonicals.setdefault(canon, []).append(path)

    conflicts = {c: paths for c, paths in canonicals.items() if len(paths) > 1}
    passed = len(conflicts) == 0
    affected = []
    for canon_url, paths in conflicts.items():
        affected.extend(paths)

    return AuditCheck(
        check_id="canonical_conflicts",
        category="technical",
        severity="critical",
        passed=passed,
        title="No canonical URL conflicts",
        description="Each page has a unique canonical URL."
        if passed
        else f"{len(conflicts)} canonical URL(s) shared by multiple pages.",
        recommendation=None
        if passed
        else "Ensure each page has its own unique canonical URL.",
        affected_pages=affected if affected else None,
    )


def _check_duplicate_titles(page_metas: dict[str, dict[str, Any]]) -> AuditCheck:
    """Check for pages with identical titles."""
    titles: dict[str, list[str]] = {}
    for path, meta in page_metas.items():
        title = meta.get("title")
        if title:
            titles.setdefault(title, []).append(path)

    dupes = {t: paths for t, paths in titles.items() if len(paths) > 1}
    passed = len(dupes) == 0
    affected = []
    for title, paths in dupes.items():
        affected.extend(paths)

    return AuditCheck(
        check_id="duplicate_titles",
        category="technical",
        severity="warning",
        passed=passed,
        title="No duplicate titles",
        description="All pages have unique titles."
        if passed
        else f"{len(dupes)} title(s) shared by multiple pages.",
        recommendation=None
        if passed
        else "Give each page a unique, descriptive title.",
        affected_pages=affected if affected else None,
    )


def _check_duplicate_descriptions(page_metas: dict[str, dict[str, Any]]) -> AuditCheck:
    """Check for pages with identical descriptions."""
    descs: dict[str, list[str]] = {}
    for path, meta in page_metas.items():
        desc = meta.get("description")
        if desc:
            descs.setdefault(desc, []).append(path)

    dupes = {d: paths for d, paths in descs.items() if len(paths) > 1}
    passed = len(dupes) == 0
    affected = []
    for desc, paths in dupes.items():
        affected.extend(paths)

    return AuditCheck(
        check_id="duplicate_descriptions",
        category="technical",
        severity="warning",
        passed=passed,
        title="No duplicate descriptions",
        description="All pages have unique meta descriptions."
        if passed
        else f"{len(dupes)} description(s) shared by multiple pages.",
        recommendation=None
        if passed
        else "Write unique descriptions for each page.",
        affected_pages=affected if affected else None,
    )


def _check_no_404_pages(crawl_data: dict[str, dict[str, Any]]) -> AuditCheck:
    """Check that all crawled pages return HTTP 200."""
    if not crawl_data:
        return AuditCheck(
            check_id="no_404_pages",
            category="technical",
            severity="warning",
            passed=True,
            title="No broken pages detected",
            description="No crawl data available. Run the crawler to check for broken pages.",
        )

    broken = [
        path for path, data in crawl_data.items()
        if data.get("status_code") and data["status_code"] >= 400
    ]
    passed = len(broken) == 0
    return AuditCheck(
        check_id="no_404_pages",
        category="technical",
        severity="critical",
        passed=passed,
        title="No broken pages detected",
        description="All crawled pages return HTTP 200."
        if passed
        else f"{len(broken)} page(s) returning error status codes.",
        recommendation=None
        if passed
        else "Fix or remove broken pages that return 4xx/5xx status codes.",
        affected_pages=broken if broken else None,
    )


# ---------------------------------------------------------------------------
# Content checks
# ---------------------------------------------------------------------------


def _check_all_pages_have_meta(page_metas: dict[str, dict[str, Any]]) -> AuditCheck:
    """Check that every page has both title and description."""
    missing = [
        path
        for path, meta in page_metas.items()
        if not meta.get("title") or not meta.get("description")
    ]
    passed = len(missing) == 0
    return AuditCheck(
        check_id="all_pages_have_meta",
        category="content",
        severity="critical",
        passed=passed,
        title="All pages have meta tags",
        description="Every page has a title and description."
        if passed
        else f"{len(missing)} page(s) missing title or description.",
        recommendation=None
        if passed
        else "Add title and description to all pages via the Meta Editor.",
        affected_pages=missing if missing else None,
    )


def _check_thin_content(crawl_data: dict[str, dict[str, Any]]) -> AuditCheck:
    """Flag pages with < 200 characters of content."""
    if not crawl_data:
        return AuditCheck(
            check_id="thin_content_pages",
            category="content",
            severity="info",
            passed=True,
            title="No thin content detected",
            description="No crawl data available. Run the crawler to check content length.",
        )

    thin = [
        path
        for path, data in crawl_data.items()
        if (data.get("content_length") or 0) < 200
    ]
    passed = len(thin) == 0
    return AuditCheck(
        check_id="thin_content_pages",
        category="content",
        severity="warning",
        passed=passed,
        title="No thin content detected",
        description="All pages have sufficient content (200+ characters)."
        if passed
        else f"{len(thin)} page(s) with thin content (< 200 characters).",
        recommendation=None
        if passed
        else "Add more substantive content to thin pages.",
        affected_pages=thin if thin else None,
    )


def _check_missing_h1(crawl_data: dict[str, dict[str, Any]]) -> AuditCheck:
    """Check for pages missing H1 headings."""
    if not crawl_data:
        return AuditCheck(
            check_id="missing_h1_pages",
            category="content",
            severity="info",
            passed=True,
            title="No missing H1 headings",
            description="No crawl data available. Run the crawler to check headings.",
        )

    missing = []
    for path, data in crawl_data.items():
        headings = data.get("headings")
        if headings is not None:
            has_h1 = any(
                h.get("tag", "").lower() == "h1" for h in headings
            )
            if not has_h1:
                missing.append(path)

    passed = len(missing) == 0
    return AuditCheck(
        check_id="missing_h1_pages",
        category="content",
        severity="warning",
        passed=passed,
        title="No missing H1 headings",
        description="All crawled pages have an H1 heading."
        if passed
        else f"{len(missing)} page(s) missing an H1 heading.",
        recommendation=None
        if passed
        else "Add a clear H1 heading to every page.",
        affected_pages=missing if missing else None,
    )


def _check_missing_alt_images(crawl_data: dict[str, dict[str, Any]]) -> AuditCheck:
    """Check for pages with images missing alt text."""
    if not crawl_data:
        return AuditCheck(
            check_id="missing_alt_images",
            category="content",
            severity="info",
            passed=True,
            title="No images missing alt text",
            description="No crawl data available. Run the crawler to check image alt attributes.",
        )

    affected = [
        path
        for path, data in crawl_data.items()
        if data.get("images_without_alt") and len(data["images_without_alt"]) > 0
    ]
    total_missing = sum(
        len(data.get("images_without_alt", []))
        for data in crawl_data.values()
    )
    passed = len(affected) == 0
    return AuditCheck(
        check_id="missing_alt_images",
        category="content",
        severity="warning",
        passed=passed,
        title="No images missing alt text",
        description="All images have descriptive alt text."
        if passed
        else f"{total_missing} image(s) across {len(affected)} page(s) missing alt text.",
        recommendation=None
        if passed
        else "Add descriptive alt text to all images for accessibility and SEO.",
        affected_pages=affected if affected else None,
    )


# ---------------------------------------------------------------------------
# Social checks
# ---------------------------------------------------------------------------


def _check_all_pages_have_og(page_metas: dict[str, dict[str, Any]]) -> AuditCheck:
    """Check that every page has OG tags."""
    missing = []
    for path, meta in page_metas.items():
        og = meta.get("og_tags") or {}
        if not og.get("og:title") or not og.get("og:description"):
            missing.append(path)

    passed = len(missing) == 0
    return AuditCheck(
        check_id="all_pages_have_og",
        category="social",
        severity="warning",
        passed=passed,
        title="All pages have Open Graph tags",
        description="Every page has OG title and description for social sharing."
        if passed
        else f"{len(missing)} page(s) missing OG tags.",
        recommendation=None
        if passed
        else "Add Open Graph tags (title, description) to all pages.",
        affected_pages=missing if missing else None,
    )


def _check_custom_og_images(page_metas: dict[str, dict[str, Any]]) -> AuditCheck:
    """Count pages using default vs custom OG image."""
    default_image = settings.default_og_image
    using_default = []
    for path, meta in page_metas.items():
        og = meta.get("og_tags") or {}
        og_image = og.get("og:image", "")
        if not og_image or og_image == default_image or og_image.endswith(default_image):
            using_default.append(path)

    total = len(page_metas)
    custom_count = total - len(using_default)
    passed = len(using_default) == 0
    return AuditCheck(
        check_id="custom_og_images",
        category="social",
        severity="info",
        passed=passed,
        title="Pages use custom OG images",
        description=f"All {total} page(s) have custom OG images."
        if passed
        else f"{len(using_default)} of {total} page(s) using default OG image.",
        recommendation=None
        if passed
        else "Set page-specific OG images for better social media previews.",
        affected_pages=using_default if using_default else None,
    )


# ---------------------------------------------------------------------------
# Performance checks
# ---------------------------------------------------------------------------


def _check_image_heavy_pages(crawl_data: dict[str, dict[str, Any]]) -> AuditCheck:
    """Flag pages with > 20 images (performance concern)."""
    if not crawl_data:
        return AuditCheck(
            check_id="image_heavy_pages",
            category="performance",
            severity="info",
            passed=True,
            title="No image-heavy pages",
            description="No crawl data available. Run the crawler to check image counts.",
        )

    # We can infer image count from images_without_alt list length as a proxy
    # The crawler extracts images_without_alt but not total image count.
    # For a more complete check, we'd need total image count from crawl data.
    # For now, we check if any page has many images missing alt (indicator).
    heavy = [
        path
        for path, data in crawl_data.items()
        if len(data.get("images_without_alt", [])) > 20
    ]
    passed = len(heavy) == 0
    return AuditCheck(
        check_id="image_heavy_pages",
        category="performance",
        severity="info",
        passed=passed,
        title="No image-heavy pages",
        description="No pages have excessive unoptimized images."
        if passed
        else f"{len(heavy)} page(s) with many unoptimized images.",
        recommendation=None
        if passed
        else "Optimize images on heavy pages: compress, lazy-load, and use responsive sizes.",
        affected_pages=heavy if heavy else None,
    )


async def _check_sitemap_freshness(db: AsyncSession) -> AuditCheck:
    """Check if sitemap was recently generated (proxy: check Redis cache or DB activity)."""
    import redis.asyncio as redis

    try:
        r = redis.from_url(settings.redis_url)
        ttl = await r.ttl("seo:sitemap:xml")
        await r.aclose()

        if ttl > 0:
            # Cache exists and hasn't expired
            max_ttl = settings.sitemap_cache_ttl
            age_seconds = max_ttl - ttl
            # Fresh if generated within last 7 days
            passed = age_seconds < 7 * 24 * 3600
        elif ttl == -1:
            # Key exists but has no expiry — treat as stale
            passed = False
        else:
            # Key doesn't exist — sitemap hasn't been generated
            passed = False
    except Exception:
        # Redis unavailable — can't check
        return AuditCheck(
            check_id="sitemap_freshness",
            category="performance",
            severity="info",
            passed=True,
            title="Sitemap freshness",
            description="Unable to check sitemap cache status.",
        )

    return AuditCheck(
        check_id="sitemap_freshness",
        category="performance",
        severity="warning",
        passed=passed,
        title="Sitemap freshness",
        description="Sitemap was recently generated."
        if passed
        else "Sitemap may be stale or not yet generated.",
        recommendation=None
        if passed
        else "Regenerate the sitemap from the SEO Overview page.",
    )


def _check_sitemap_coverage(
    paths: list[str], page_metas: dict[str, dict[str, Any]]
) -> AuditCheck:
    """Check that all known paths have meta tags generated."""
    uncovered = [p for p in paths if p not in page_metas]
    passed = len(uncovered) == 0
    return AuditCheck(
        check_id="sitemap_coverage",
        category="technical",
        severity="warning",
        passed=passed,
        title="All sitemap pages have metadata",
        description="Every page in the sitemap has generated meta tags."
        if passed
        else f"{len(uncovered)} page(s) in sitemap have no metadata.",
        recommendation=None
        if passed
        else "Check meta generation for uncovered pages.",
        affected_pages=uncovered if uncovered else None,
    )
