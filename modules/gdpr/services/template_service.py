"""Jinja2 email template rendering service.

Loads HTML templates from modules/gdpr/templates/ and renders them with
provided data. Auto-injects common variables (app_name, year, frontend_url).
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from backend.core.config import settings

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
)


def render_template(template_id: str, data: dict | None = None) -> str:
    """Render an email template by ID.

    Args:
        template_id: Template filename without extension (e.g. "welcome").
        data: Template-specific variables.

    Returns:
        Rendered HTML string.
    """
    context = {
        "app_name": settings.app_name,
        "site_name": settings.site_name or settings.app_name,
        "frontend_url": settings.frontend_url,
        "year": datetime.now(timezone.utc).year,
        **(data or {}),
    }

    try:
        template = _env.get_template(f"{template_id}.html")
        return template.render(**context)
    except Exception:
        logger.exception("Failed to render email template: %s", template_id)
        raise
