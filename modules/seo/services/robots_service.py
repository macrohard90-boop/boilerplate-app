"""Robots.txt generation."""

from backend.core.config import settings


def generate_robots() -> str:
    """Generate robots.txt content."""
    domain = settings.domain
    if domain == "localhost":
        sitemap_url = f"{settings.backend_url}/sitemap.xml"
    else:
        sitemap_url = f"https://{domain}/sitemap.xml"

    lines = [
        "User-agent: *",
        "Allow: /",
        "",
        "# Disallow API and admin paths",
        "Disallow: /api/admin/",
        "Disallow: /api/auth/",
        "Disallow: /api/gdpr/",
        "Disallow: /api/tracking/",
        "",
        f"Sitemap: {sitemap_url}",
    ]
    return "\n".join(lines) + "\n"
