"""Jinja2 email template rendering service.

Loads HTML templates from modules/gdpr/templates/ and renders them with
provided data. Auto-injects common variables (app_name, year, frontend_url).

Hybrid resolution (render_template_hybrid):
  1. Check marketing.email_templates DB table
  2. Fall back to filesystem templates in modules/gdpr/templates/
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
)


def _build_context(data: dict | None = None) -> dict[str, Any]:
    """Build the standard template context with auto-injected variables."""
    return {
        "app_name": settings.app_name,
        "site_name": settings.site_name or settings.app_name,
        "frontend_url": settings.frontend_url,
        "year": datetime.now(timezone.utc).year,
        **(data or {}),
    }


def render_template(template_id: str, data: dict | None = None) -> str:
    """Render an email template from the filesystem by ID.

    Args:
        template_id: Template filename without extension (e.g. "welcome").
        data: Template-specific variables.

    Returns:
        Rendered HTML string.
    """
    context = _build_context(data)

    try:
        template = _env.get_template(f"{template_id}.html")
        return template.render(**context)
    except Exception:
        logger.exception("Failed to render email template: %s", template_id)
        raise


def render_from_content(
    html_content: str, data: dict | None = None
) -> str:
    """Render arbitrary HTML content (from DB or preview).

    If content starts with '{%', it's treated as a full Jinja2 template
    (may use {% extends "base.html" %}). Otherwise, it's wrapped in the
    base template automatically.
    """
    context = _build_context(data)

    try:
        if html_content.strip().startswith("{%"):
            template = _env.from_string(html_content)
        else:
            wrapped = (
                '{% extends "base.html" %}\n'
                "{% block content %}\n"
                + html_content
                + "\n{% endblock %}"
            )
            template = _env.from_string(wrapped)
        return template.render(**context)
    except Exception:
        logger.exception("Failed to render template content")
        raise


def _render_jinja_string(source: str, context: dict[str, Any]) -> str:
    """Render a short Jinja2 string (e.g. subject line)."""
    try:
        return _env.from_string(source).render(**context)
    except Exception:
        return source


async def render_template_hybrid(
    db: AsyncSession, template_id: str, data: dict | None = None
) -> tuple[str, str | None]:
    """Render a template checking DB first, then filesystem.

    Returns:
        (rendered_html, rendered_subject_or_None)
    """
    context = _build_context(data)

    # 1. Check DB
    try:
        row = (
            await db.execute(
                text(
                    "SELECT html_content, subject "
                    "FROM marketing.email_templates WHERE name = :name"
                ),
                {"name": template_id},
            )
        ).mappings().first()
    except Exception:
        # DB table may not exist yet (fresh install before migration)
        row = None

    if row:
        html = render_from_content(row["html_content"], data)
        subject = (
            _render_jinja_string(row["subject"], context)
            if row["subject"]
            else None
        )
        return html, subject

    # 2. Filesystem fallback
    html = render_template(template_id, data)
    return html, None
