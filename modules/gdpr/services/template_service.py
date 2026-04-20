"""Jinja2 email template rendering service.

Renders email templates from the marketing.email_templates DB table.
Auto-injects common variables (app_name, year, frontend_url).

The base.html layout in modules/gdpr/templates/ is still used to wrap
content-block templates with standard header/footer/styling.
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


def render_from_content(html_content: str, data: dict | None = None) -> str:
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
                "{% block content %}\n" + html_content + "\n{% endblock %}"
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


async def render_template_db(
    db: AsyncSession, template_id: str, data: dict | None = None
) -> tuple[str, str | None]:
    """Render a template from the DB by name.

    All templates live in marketing.email_templates (seeded via migration).
    There is no filesystem fallback.

    Returns:
        (rendered_html, rendered_subject_or_None)

    Raises:
        ValueError: If the template is not found in the DB.
    """
    context = _build_context(data)

    row = (
        (
            await db.execute(
                text(
                    "SELECT html_content, subject "
                    "FROM marketing.email_templates WHERE name = :name"
                ),
                {"name": template_id},
            )
        )
        .mappings()
        .first()
    )

    if not row:
        raise ValueError(f"Email template '{template_id}' not found in database")

    html = render_from_content(row["html_content"], data)
    subject = _render_jinja_string(row["subject"], context) if row["subject"] else None
    return html, subject
