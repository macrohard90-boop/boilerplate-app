#!/usr/bin/env python3
"""
Database seed runner.

Commands:
    python scripts/seed.py              Seed database with template-appropriate data
    python scripts/seed.py --reset      Truncate seeded tables and re-seed

Template-aware: runs common seeds + ecommerce OR saas seeds based on APP_TEMPLATE.
Idempotent by default (INSERT ... ON CONFLICT DO NOTHING for most data).
"""

import os
import sys
import argparse
from pathlib import Path

import psycopg2

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SEEDS_DIR = PROJECT_ROOT / "seeds"


def load_env() -> dict[str, str]:
    """Load .env file into a dict."""
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


def get_db_url() -> str:
    """Get sync PostgreSQL connection string."""
    env = load_env()
    url = os.environ.get("DATABASE_URL", env.get("DATABASE_URL", ""))
    if not url:
        print("ERROR: DATABASE_URL not set in .env or environment")
        sys.exit(1)
    return url.replace("postgresql+asyncpg://", "postgresql://")


def get_template() -> str:
    """Get app template from .env."""
    env = load_env()
    return os.environ.get("APP_TEMPLATE", env.get("APP_TEMPLATE", "ecommerce")).lower()


def reset_tables(conn, template: str):
    """Truncate all seeded tables (CASCADE) for clean re-seed."""
    print("  Resetting tables...")

    # Order matters: truncate child tables first or use CASCADE
    tables = [
        # GDPR (always)
        "gdpr.email_preferences",
        # Core
        "core.exchange_rates",
        "core.permissions",
        "core.users",  # CASCADE will handle sessions, api_keys, audit_log, etc.
        "core.roles",
    ]

    if template == "ecommerce":
        # Ecommerce tables (CASCADE handles children)
        tables = [
            "ecommerce.product_reviews",
            "ecommerce.product_images",
            "ecommerce.product_categories",
            "ecommerce.digital_assets",
            "ecommerce.discount_codes",
            "ecommerce.customer_metrics",
            "ecommerce.product_variants",
            "ecommerce.products",
            "ecommerce.categories",
        ] + tables
    elif template == "saas":
        tables = [
            "saas.subscriptions",
            "saas.plan_features",
            "saas.plans",
        ] + tables

    with conn.cursor() as cur:
        for table in tables:
            try:
                cur.execute(f"TRUNCATE TABLE {table} CASCADE")
            except Exception:
                conn.rollback()
                # Table might not exist yet, skip
                continue
    conn.commit()
    print("  Tables reset.")


def run_seed_file(conn, filepath: Path):
    """Execute a seed SQL file."""
    sql = filepath.read_text()
    print(f"  Seeding from {filepath.name}...", end=" ")
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        print("OK")
    except Exception as e:
        conn.rollback()
        print(f"FAILED\n  Error: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Database seed runner")
    parser.add_argument("--reset", action="store_true", help="Truncate and re-seed")
    args = parser.parse_args()

    template = get_template()
    conn = psycopg2.connect(get_db_url())

    try:
        print(f"\nSeeding database (template: {template})...")

        if args.reset:
            reset_tables(conn, template)

        # Common seeds (roles, permissions, users, exchange rates)
        run_seed_file(conn, SEEDS_DIR / "common.sql")

        # Template-specific seeds
        seed_file = SEEDS_DIR / f"{template}.sql"
        if seed_file.exists():
            run_seed_file(conn, seed_file)
        else:
            print(f"  WARNING: No seed file found for template '{template}'")

        print("\n  Seeding complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
