"""JSON-LD structured data generation (Product, Organization, Breadcrumb, WebSite)."""

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings


def _parse_social_handles() -> dict:
    raw = settings.social_handles
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


async def get_product_schema(db: AsyncSession, slug: str) -> dict[str, Any] | None:
    """Generate JSON-LD Product schema for a product slug."""
    product = (
        (
            await db.execute(
                text(
                    "SELECT p.id, p.name, p.description, p.sku, p.base_price, p.currency, "
                    "pi.url AS image_url "
                    "FROM ecommerce.products p "
                    "LEFT JOIN ecommerce.product_images pi "
                    "  ON pi.product_id = p.id AND pi.is_primary = true "
                    "WHERE p.slug = :slug AND p.status = 'active' "
                    "  AND p.deleted_at IS NULL"
                ),
                {"slug": slug},
            )
        )
        .mappings()
        .first()
    )

    if not product:
        return None

    product_id = str(product["id"])
    base_url = settings.frontend_url.rstrip("/")

    schema: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product["name"],
        "url": f"{base_url}/products/{slug}",
    }

    if product["description"]:
        schema["description"] = product["description"]
    if product["sku"]:
        schema["sku"] = product["sku"]
    if product["image_url"]:
        schema["image"] = product["image_url"]

    # Offers (price + availability)
    if product["base_price"] is not None:
        # Check stock across variants
        stock = (
            (
                await db.execute(
                    text(
                        "SELECT COALESCE(SUM(stock_quantity), 0) AS total_stock "
                        "FROM ecommerce.product_variants WHERE product_id = :pid"
                    ),
                    {"pid": product_id},
                )
            )
            .mappings()
            .first()
        )

        total_stock = stock["total_stock"] if stock else 0
        availability = (
            "https://schema.org/InStock"
            if total_stock > 0
            else "https://schema.org/OutOfStock"
        )

        schema["offers"] = {
            "@type": "Offer",
            "price": f"{product['base_price'] / 100:.2f}",
            "priceCurrency": product["currency"] or "USD",
            "availability": availability,
        }

    # Aggregate rating from approved reviews
    rating = (
        (
            await db.execute(
                text(
                    "SELECT COUNT(*) AS count, AVG(rating) AS avg_rating "
                    "FROM ecommerce.product_reviews "
                    "WHERE product_id = :pid AND status = 'approved'"
                ),
                {"pid": product_id},
            )
        )
        .mappings()
        .first()
    )

    if rating and rating["count"] and rating["count"] > 0:
        schema["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": f"{float(rating['avg_rating']):.1f}",
            "reviewCount": int(rating["count"]),
        }

    return schema


def get_organization_schema() -> dict[str, Any]:
    """Generate JSON-LD Organization schema."""
    social = _parse_social_handles()
    base_url = settings.frontend_url.rstrip("/")

    schema: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": settings.site_name,
        "url": base_url,
    }

    if settings.default_og_image:
        schema["logo"] = settings.default_og_image

    # Social profiles
    same_as = []
    for platform in ("twitter", "facebook", "instagram", "linkedin"):
        if social.get(platform):
            same_as.append(social[platform])
    if same_as:
        schema["sameAs"] = same_as

    return schema


async def get_breadcrumb_schema(
    db: AsyncSession, category_slug: str
) -> dict[str, Any] | None:
    """Generate JSON-LD BreadcrumbList from category hierarchy."""
    base_url = settings.frontend_url.rstrip("/")

    # Walk the category hierarchy up to root
    crumbs: list[dict] = []
    current_slug = category_slug

    for _ in range(10):  # max depth guard
        cat = (
            (
                await db.execute(
                    text(
                        "SELECT id, name, slug, parent_id "
                        "FROM ecommerce.categories WHERE slug = :slug"
                    ),
                    {"slug": current_slug},
                )
            )
            .mappings()
            .first()
        )

        if not cat:
            break

        crumbs.append({"name": cat["name"], "slug": cat["slug"]})

        if cat["parent_id"]:
            parent = (
                (
                    await db.execute(
                        text("SELECT slug FROM ecommerce.categories WHERE id = :pid"),
                        {"pid": str(cat["parent_id"])},
                    )
                )
                .mappings()
                .first()
            )
            if parent:
                current_slug = parent["slug"]
                continue
        break

    if not crumbs:
        return None

    crumbs.reverse()  # root first

    items = [
        {
            "@type": "ListItem",
            "position": 1,
            "name": "Home",
            "item": f"{base_url}/",
        }
    ]
    for i, c in enumerate(crumbs, start=2):
        items.append(
            {
                "@type": "ListItem",
                "position": i,
                "name": c["name"],
                "item": f"{base_url}/categories/{c['slug']}",
            }
        )

    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": items,
    }


def get_website_schema() -> dict[str, Any]:
    """Generate JSON-LD WebSite schema with SearchAction."""
    base_url = settings.frontend_url.rstrip("/")

    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": settings.site_name,
        "url": base_url,
        "potentialAction": {
            "@type": "SearchAction",
            "target": f"{base_url}/search?q={{search_term_string}}",
            "query-input": "required name=search_term_string",
        },
    }
