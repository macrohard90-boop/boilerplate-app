"""Open Graph and Twitter Card tag generation."""

import json
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings


def _parse_social_handles() -> dict:
    """Parse social_handles setting (JSON string or empty)."""
    raw = settings.social_handles
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


async def get_og_tags(db: AsyncSession, path: str) -> dict[str, Any]:
    """Generate Open Graph and Twitter Card tags for a path."""
    base_url = settings.frontend_url.rstrip("/")
    canonical = f"{base_url}/{path.lstrip('/')}"
    social = _parse_social_handles()

    og: dict[str, Any] = {
        "og:site_name": settings.site_name,
        "og:url": canonical,
        "og:image": settings.default_og_image,
    }
    twitter: dict[str, Any] = {
        "twitter:card": "summary_large_image",
    }
    if social.get("twitter"):
        twitter["twitter:site"] = social["twitter"]

    # Product page
    match = re.match(r"^/?products/([^/]+)$", path)
    if match:
        slug = match.group(1)
        product = (
            (
                await db.execute(
                    text(
                        "SELECT p.name, p.description, p.base_price, p.currency, "
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

        if product:
            og["og:type"] = "product"
            og["og:title"] = product["name"]
            og["og:description"] = (product["description"] or f"Buy {product['name']}")[
                :160
            ]
            if product["image_url"]:
                og["og:image"] = product["image_url"]
            if product["base_price"] is not None:
                og["product:price:amount"] = f"{product['base_price'] / 100:.2f}"
                og["product:price:currency"] = product["currency"] or "USD"
            twitter["twitter:title"] = product["name"]
            twitter["twitter:description"] = og["og:description"]
            return {"og_tags": og, "twitter_tags": twitter}

    # Category page
    match = re.match(r"^/?categories/([^/]+)$", path)
    if match:
        slug = match.group(1)
        category = (
            (
                await db.execute(
                    text(
                        "SELECT name, description FROM ecommerce.categories "
                        "WHERE slug = :slug"
                    ),
                    {"slug": slug},
                )
            )
            .mappings()
            .first()
        )

        if category:
            og["og:type"] = "website"
            og["og:title"] = category["name"]
            og["og:description"] = (
                category["description"] or f"Browse {category['name']} products"
            )[:160]
            twitter["twitter:title"] = category["name"]
            twitter["twitter:description"] = og["og:description"]
            return {"og_tags": og, "twitter_tags": twitter}

    # Default page
    og["og:type"] = "website"
    og["og:title"] = settings.site_name
    og["og:description"] = f"Welcome to {settings.site_name}"
    twitter["twitter:title"] = og["og:title"]
    twitter["twitter:description"] = og["og:description"]

    return {"og_tags": og, "twitter_tags": twitter}
