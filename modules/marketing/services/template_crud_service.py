"""Email template CRUD — list, get, create, update, delete, clone, preview.

Templates are stored in marketing.email_templates. Rendering is handled
by gdpr.services.template_service.render_template_db which looks up
templates by name from the DB (no filesystem fallback).
"""

import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def list_templates(
    db: AsyncSession,
    category: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> dict[str, Any]:
    """List templates (without html_content for performance)."""
    offset = (page - 1) * per_page
    params: dict[str, Any] = {"limit": per_page, "offset": offset}

    where = ""
    if category:
        where = "WHERE category = :category"
        params["category"] = category

    rows = (
        (
            await db.execute(
                text(
                    f"SELECT id, name, display_name, subject, category, "
                    f"description, variables, is_builtin, version, "
                    f"created_at, updated_at "
                    f"FROM marketing.email_templates {where} "
                    f"ORDER BY category, display_name "
                    f"LIMIT :limit OFFSET :offset"
                ),
                params,
            )
        )
        .mappings()
        .all()
    )

    count_row = (
        (
            await db.execute(
                text(
                    f"SELECT COUNT(*) as total FROM marketing.email_templates {where}"
                ),
                params,
            )
        )
        .mappings()
        .first()
    )

    return {
        "items": [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "display_name": r["display_name"],
                "subject": r["subject"],
                "category": r["category"],
                "description": r["description"],
                "variables": r["variables"],
                "is_builtin": r["is_builtin"],
                "version": r["version"],
                "created_at": str(r["created_at"]),
                "updated_at": str(r["updated_at"]),
            }
            for r in rows
        ],
        "total": count_row["total"],
        "page": page,
        "per_page": per_page,
    }


async def get_template(db: AsyncSession, template_id: str) -> dict[str, Any] | None:
    """Get a single template including html_content."""
    row = (
        (
            await db.execute(
                text(
                    "SELECT id, name, display_name, subject, html_content, "
                    "category, description, variables, is_builtin, version, "
                    "created_by, created_at, updated_at "
                    "FROM marketing.email_templates WHERE id = :tid"
                ),
                {"tid": template_id},
            )
        )
        .mappings()
        .first()
    )

    if not row:
        return None

    return {
        "id": str(row["id"]),
        "name": row["name"],
        "display_name": row["display_name"],
        "subject": row["subject"],
        "html_content": row["html_content"],
        "category": row["category"],
        "description": row["description"],
        "variables": row["variables"],
        "is_builtin": row["is_builtin"],
        "version": row["version"],
        "created_by": str(row["created_by"]) if row["created_by"] else None,
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }


async def create_template(
    db: AsyncSession,
    name: str,
    display_name: str,
    html_content: str,
    category: str = "campaign",
    subject: str | None = None,
    description: str | None = None,
    variables: list[dict[str, str]] | None = None,
    created_by: str | None = None,
) -> dict[str, Any]:
    """Create a new email template."""
    row = (
        (
            await db.execute(
                text(
                    "INSERT INTO marketing.email_templates "
                    "(name, display_name, subject, html_content, category, "
                    "description, variables, created_by) "
                    "VALUES (:name, :dname, :subj, :html, :cat, :desc, :vars, :uid) "
                    "RETURNING id, version, created_at"
                ),
                {
                    "name": name,
                    "dname": display_name,
                    "subj": subject,
                    "html": html_content,
                    "cat": category,
                    "desc": description,
                    "vars": json.dumps(variables or []),
                    "uid": created_by,
                },
            )
        )
        .mappings()
        .first()
    )

    await db.commit()
    logger.info("Template created: %s (%s)", row["id"], name)

    return {
        "id": str(row["id"]),
        "name": name,
        "display_name": display_name,
        "version": row["version"],
        "created_at": str(row["created_at"]),
    }


async def update_template(
    db: AsyncSession,
    template_id: str,
    display_name: str | None = None,
    subject: str | None = None,
    html_content: str | None = None,
    category: str | None = None,
    description: str | None = None,
    variables: list[dict[str, str]] | None = None,
) -> dict[str, Any] | None:
    """Update a template. Bumps version on each edit."""
    set_parts = ["updated_at = NOW()", "version = version + 1"]
    params: dict[str, Any] = {"tid": template_id}

    if display_name is not None:
        set_parts.append("display_name = :dname")
        params["dname"] = display_name
    if subject is not None:
        set_parts.append("subject = :subj")
        params["subj"] = subject
    if html_content is not None:
        set_parts.append("html_content = :html")
        params["html"] = html_content
    if category is not None:
        set_parts.append("category = :cat")
        params["cat"] = category
    if description is not None:
        set_parts.append("description = :desc")
        params["desc"] = description
    if variables is not None:
        set_parts.append("variables = :vars")
        params["vars"] = json.dumps(variables)

    row = (
        (
            await db.execute(
                text(
                    f"UPDATE marketing.email_templates "
                    f"SET {', '.join(set_parts)} "
                    f"WHERE id = :tid "
                    f"RETURNING id, name, display_name, version, updated_at"
                ),
                params,
            )
        )
        .mappings()
        .first()
    )

    if not row:
        return None

    await db.commit()
    logger.info("Template updated: %s (v%d)", row["name"], row["version"])

    return {
        "id": str(row["id"]),
        "name": row["name"],
        "display_name": row["display_name"],
        "version": row["version"],
        "updated_at": str(row["updated_at"]),
    }


async def delete_template(db: AsyncSession, template_id: str) -> bool:
    """Delete a template. Rejects built-in templates."""
    row = (
        (
            await db.execute(
                text(
                    "SELECT is_builtin FROM marketing.email_templates WHERE id = :tid"
                ),
                {"tid": template_id},
            )
        )
        .mappings()
        .first()
    )

    if not row:
        raise ValueError("Template not found")

    if row["is_builtin"]:
        raise ValueError("Cannot delete built-in templates")

    await db.execute(
        text("DELETE FROM marketing.email_templates WHERE id = :tid"),
        {"tid": template_id},
    )
    await db.commit()
    logger.info("Template deleted: %s", template_id)
    return True


async def clone_template(
    db: AsyncSession,
    source_id: str,
    new_name: str,
    new_display_name: str,
    created_by: str | None = None,
) -> dict[str, Any]:
    """Clone a template with a new name. Always creates a non-builtin copy."""
    source = await get_template(db, source_id)
    if not source:
        raise ValueError("Source template not found")

    return await create_template(
        db,
        name=new_name,
        display_name=new_display_name,
        html_content=source["html_content"],
        category=source["category"],
        subject=source["subject"],
        description=f"Cloned from {source['display_name']}",
        variables=source["variables"],
        created_by=created_by,
    )


async def preview_template(
    html_content: str,
    template_data: dict[str, Any] | None = None,
) -> str:
    """Render arbitrary HTML content with sample data. Returns rendered HTML."""
    from modules.gdpr.services.template_service import render_from_content

    return render_from_content(html_content, template_data)
