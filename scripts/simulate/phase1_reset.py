"""Phase 1: Reset — wipe database for clean simulation run."""

import logging
import os
import sys
from pathlib import Path

import psycopg2

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _load_env() -> dict[str, str]:
    env = {}
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def _get_db_url() -> str:
    env = _load_env()
    url = os.environ.get("DATABASE_URL", env.get("DATABASE_URL", ""))
    if not url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)
    # Convert async URL to sync for psycopg2
    return url.replace("postgresql+asyncpg://", "postgresql://")


# Tables to truncate (order matters due to FK constraints — CASCADE handles it)
TRUNCATE_TABLES = [
    # Analytics
    "analytics.simulation_user_results",
    "analytics.simulation_runs",
    "analytics.engagement_scores",
    "analytics.page_click_interactions",
    "analytics.utm_tracking",
    "analytics.referral_sources",
    "analytics.user_agents",
    "analytics.events",
    "analytics.page_views",
    "analytics.analytics_sessions",
    # Marketing
    "marketing.flow_step_executions",
    "marketing.flow_enrollments",
    "marketing.message_pressure_log",
    "marketing.campaign_stats_summary",
    "marketing.campaign_attributions",
    "marketing.campaign_link_clicks",
    "marketing.campaign_recipients",
    # Ecommerce
    "ecommerce.payment_records",
    "ecommerce.order_items",
    "ecommerce.orders",
    "ecommerce.cart_items",
    "ecommerce.carts",
    "ecommerce.product_reviews",
    "ecommerce.wishlist_items",
    "ecommerce.wishlists",
    "ecommerce.product_images",
    "ecommerce.product_categories",
    "ecommerce.product_variants",
    "ecommerce.products",
    "ecommerce.categories",
    "ecommerce.subscriptions",
    "ecommerce.abandoned_cart_events",
    # GDPR
    "gdpr.consent_records",
    "gdpr.cookie_preferences",
    "gdpr.data_processing_records",
    # Core (users last — many FKs point here)
    "core.user_sessions",
    "core.api_keys",
    "core.users",
]


def run(db_url: str | None = None) -> dict:
    """Truncate all user-facing tables, re-seed event definitions.

    Returns dict with status info.
    """
    url = db_url or _get_db_url()
    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()

    result = {"tables_truncated": 0, "events_seeded": 0, "errors": []}

    # Truncate tables
    for table in TRUNCATE_TABLES:
        try:
            cur.execute(f"TRUNCATE TABLE {table} CASCADE")
            result["tables_truncated"] += 1
        except Exception as e:
            # Table might not exist yet — non-fatal
            conn.rollback()
            conn.autocommit = True
            if "does not exist" not in str(e):
                result["errors"].append(f"Truncate {table}: {e}")
                logger.warning("Failed to truncate %s: %s", table, e)

    # Re-seed event definitions (they were truncated with analytics tables)
    migration_file = PROJECT_ROOT / "migrations" / "034_event_definitions.sql"
    if migration_file.exists():
        sql = migration_file.read_text()
        # Extract only the INSERT statements (skip CREATE TABLE which already exists)
        lines = sql.split("\n")
        insert_block = []
        in_insert = False
        for line in lines:
            if line.strip().startswith("INSERT INTO"):
                in_insert = True
            if in_insert:
                insert_block.append(line)
            if in_insert and line.strip().endswith(";"):
                # Execute each INSERT block
                stmt = "\n".join(insert_block)
                try:
                    cur.execute(stmt)
                    result["events_seeded"] += 1
                except Exception as e:
                    logger.warning("Event seed failed: %s", e)
                    conn.rollback()
                    conn.autocommit = True
                insert_block = []
                in_insert = False

    # Re-seed roles and permissions (needed for admin user creation)
    common_seed = PROJECT_ROOT / "seeds" / "common.sql"
    if common_seed.exists():
        sql = common_seed.read_text()
        # Extract only role/permission inserts (first ~50 lines typically)
        for stmt in sql.split(";"):
            stmt = stmt.strip()
            if not stmt:
                continue
            if "core.roles" in stmt or "core.permissions" in stmt or "core.role_permissions" in stmt:
                try:
                    cur.execute(stmt + ";")
                except Exception:
                    conn.rollback()
                    conn.autocommit = True

    cur.close()
    conn.close()

    return result
