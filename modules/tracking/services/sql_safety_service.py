"""SQL safety validation for admin custom metrics.

Multi-layer defence:
1. Keyword deny-list  – regex blocks DDL / DML / control statements
2. Schema whitelist   – only analytics.* tables allowed
3. LIMIT enforcement  – cap result rows at 1000
4. (Caller applies)   SET TRANSACTION READ ONLY + statement_timeout at DB level

This is NOT a full SQL parser — it is a practical guard-rail for an
admin-only feature.  The PostgreSQL READ ONLY transaction is the true
security boundary; regex is the user-facing error layer.
"""

from __future__ import annotations

import re

# ── Allowed tables ──────────────────────────────────────────────────

ALLOWED_TABLES: set[str] = {
    # Analytics
    "analytics.page_views",
    "analytics.analytics_sessions",
    "analytics.events",
    "analytics.user_agents",
    "analytics.referral_sources",
    "analytics.utm_tracking",
    "analytics.saved_metrics",
    "analytics.engagement_scores",
    # Core
    "core.users",
    "core.roles",
    # GDPR (audience eligibility)
    "gdpr.email_preferences",
    # Ecommerce (audience segmentation)
    "ecommerce.customer_metrics",
    "ecommerce.carts",
    "ecommerce.wishlists",
    # Marketing (audience segmentation)
    "marketing.communication_types",
    "marketing.user_communication_preferences",
}

# ── Blocked schemas ─────────────────────────────────────────────────

BLOCKED_SCHEMAS: set[str] = {
    "saas",
    "public",
    "pg_catalog",
    "information_schema",
}

# ── Forbidden SQL keywords (word-boundary regex patterns) ───────────

_FORBIDDEN_PATTERNS: list[str] = [
    r"\bINSERT\b",
    r"\bUPDATE\b",
    r"\bDELETE\b",
    r"\bDROP\b",
    r"\bCREATE\b",
    r"\bALTER\b",
    r"\bTRUNCATE\b",
    r"\bGRANT\b",
    r"\bREVOKE\b",
    r"\bCOPY\b",
    r"\bEXECUTE\b",
    r"\bCALL\b",
    r"\bSET\b",
    r"\bVACUUM\b",
    r"\bLOCK\b",
    r"\bUNLOCK\b",
    r"\bIMPORT\b",
    r"\bLOAD\b",
    r"\bRESET\b",
    r"\bDISCARD\b",
    r"\bREINDEX\b",
    r"\bNOTIFY\b",
    r"\bLISTEN\b",
    r"\bUNLISTEN\b",
    r"\bPREPARE\b",
    r"\bDEALLOCATE\b",
    r"\bDO\b\s+\$",  # PL/pgSQL DO $$ blocks
]

MAX_QUERY_LENGTH = 10_000
MAX_ROWS = 1000


class SQLValidationError(Exception):
    """Raised when a SQL query fails safety validation."""


def validate_query(sql: str) -> str:
    """Validate *sql* and return a (possibly LIMIT-adjusted) safe version.

    Raises :class:`SQLValidationError` with a human-readable message on
    any validation failure.
    """
    if not sql or not sql.strip():
        raise SQLValidationError("Query cannot be empty")

    if len(sql) > MAX_QUERY_LENGTH:
        raise SQLValidationError(
            f"Query exceeds maximum length ({MAX_QUERY_LENGTH:,} characters)"
        )

    # ── Block semicolons (statement chaining) ───────────────────────
    if ";" in sql:
        raise SQLValidationError("Multiple statements (;) are not allowed")

    # ── Block SQL comments ──────────────────────────────────────────
    if "--" in sql or "/*" in sql:
        raise SQLValidationError("SQL comments (-- or /* */) are not allowed")

    # ── Must start with SELECT or WITH ──────────────────────────────
    if not re.match(r"\s*(SELECT|WITH)\b", sql, re.IGNORECASE):
        raise SQLValidationError("Query must start with SELECT or WITH")

    # ── Normalize for keyword scanning ──────────────────────────────
    normalized = " ".join(sql.upper().split())

    # ── Forbidden keyword check ─────────────────────────────────────
    for pattern in _FORBIDDEN_PATTERNS:
        m = re.search(pattern, normalized)
        if m:
            raise SQLValidationError(f"Forbidden keyword: {m.group().strip()}")

    # ── Extract CTE names (WITH x AS …) ────────────────────────────
    cte_names: set[str] = {
        n.upper()
        for n in re.findall(
            r"(?:WITH|,)\s+(?:RECURSIVE\s+)?(\w+)\s+AS\s*\(",
            normalized,
        )
    }

    # ── Extract table references from FROM / JOIN clauses ───────────
    table_refs = re.findall(r"(?:FROM|JOIN)\s+(\w+(?:\.\w+)?)", normalized)

    for ref in table_refs:
        ref_upper = ref.upper()

        # Skip CTE self-references
        if ref_upper in cte_names:
            continue

        # Must be schema-qualified
        if "." not in ref:
            raise SQLValidationError(
                f"Unqualified table name '{ref}' — "
                "all tables must use schema.table_name format"
            )

        # Explicitly allowed tables always pass
        if ref.lower() in ALLOWED_TABLES:
            continue

        schema = ref.split(".")[0].lower()
        if schema in BLOCKED_SCHEMAS:
            raise SQLValidationError(
                f"Access to schema '{schema}' is not allowed. "
                "Only whitelisted tables are accessible."
            )

        raise SQLValidationError(
            f"Table '{ref}' is not in the allowed list. "
            f"Allowed: {', '.join(sorted(ALLOWED_TABLES))}"
        )

    # ── Enforce row LIMIT ───────────────────────────────────────────
    if not re.search(r"\bLIMIT\b", normalized):
        sql = sql.rstrip() + f" LIMIT {MAX_ROWS}"
    else:
        limit_match = re.search(r"\bLIMIT\s+(\d+)", normalized)
        if limit_match and int(limit_match.group(1)) > MAX_ROWS:
            sql = re.sub(r"(?i)\bLIMIT\s+\d+", f"LIMIT {MAX_ROWS}", sql)

    return sql
