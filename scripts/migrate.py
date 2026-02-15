#!/usr/bin/env python3
"""
Database migration runner.

Commands:
    python scripts/migrate.py up              Apply all pending migrations
    python scripts/migrate.py down            Roll back all migrations
    python scripts/migrate.py down --to 001   Roll back to a specific version
    python scripts/migrate.py status          Show applied migrations

Template-aware: runs 002_ecommerce or 002_saas based on APP_TEMPLATE.
Skips 004_analytics if ENABLE_TRACKING=false.
Each migration is wrapped in a transaction (BEGIN/COMMIT/ROLLBACK on error).
"""

import os
import re
import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone

import psycopg2

# Resolve project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"

# Load .env file manually (no dependency on pydantic for scripts)
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
    """Get sync PostgreSQL connection string from DATABASE_URL."""
    env = load_env()
    url = os.environ.get("DATABASE_URL", env.get("DATABASE_URL", ""))
    if not url:
        print("ERROR: DATABASE_URL not set in .env or environment")
        sys.exit(1)
    # Convert asyncpg URL to psycopg2 format
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    return url


def get_config() -> dict[str, str]:
    """Get migration-relevant config from .env."""
    env = load_env()
    return {
        "app_template": os.environ.get("APP_TEMPLATE", env.get("APP_TEMPLATE", "ecommerce")).lower(),
        "enable_tracking": os.environ.get("ENABLE_TRACKING", env.get("ENABLE_TRACKING", "true")).lower() == "true",
    }


def get_connection():
    """Create a psycopg2 connection."""
    return psycopg2.connect(get_db_url())


def ensure_migrations_table(conn):
    """Create the schema_migrations tracking table if it doesn't exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.schema_migrations (
                version VARCHAR(10) PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
    conn.commit()


def get_applied_versions(conn) -> set[str]:
    """Get set of already-applied migration versions."""
    with conn.cursor() as cur:
        cur.execute("SELECT version FROM public.schema_migrations ORDER BY version")
        return {row[0] for row in cur.fetchall()}


def parse_migration(filepath: Path) -> tuple[str, str]:
    """Parse a migration file into UP and DOWN SQL sections."""
    content = filepath.read_text()

    # Split on -- UP and -- DOWN markers
    up_match = re.search(r"^-- UP\s*$", content, re.MULTILINE)
    down_match = re.search(r"^-- DOWN\s*$", content, re.MULTILINE)

    if not up_match or not down_match:
        print(f"ERROR: Migration {filepath.name} missing -- UP or -- DOWN markers")
        sys.exit(1)

    up_sql = content[up_match.end():down_match.start()].strip()
    down_sql = content[down_match.end():].strip()

    return up_sql, down_sql


def get_migration_files(config: dict) -> list[tuple[str, Path]]:
    """
    Get ordered list of (version, filepath) tuples for applicable migrations.
    Filters based on template and module toggles.
    """
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    result = []

    for f in files:
        version = f.name.split("_")[0]  # e.g., "000", "001", "002"
        name = f.stem  # e.g., "002_ecommerce_schema"

        # Template-aware filtering for 002_*
        if name.startswith("002_"):
            if config["app_template"] == "ecommerce" and "saas" in name:
                continue
            if config["app_template"] == "saas" and "ecommerce" in name:
                continue

        # Skip analytics if tracking disabled
        if name.startswith("004_") and not config["enable_tracking"]:
            continue

        result.append((version, f))

    return result


def migrate_up(conn, config: dict):
    """Apply all pending migrations."""
    ensure_migrations_table(conn)
    applied = get_applied_versions(conn)
    migrations = get_migration_files(config)
    pending = [(v, f) for v, f in migrations if v not in applied]

    if not pending:
        print("No pending migrations.")
        return

    for version, filepath in pending:
        up_sql, _ = parse_migration(filepath)
        print(f"  Applying {filepath.name}...", end=" ")
        try:
            with conn.cursor() as cur:
                cur.execute(up_sql)
                cur.execute(
                    "INSERT INTO public.schema_migrations (version, applied_at) VALUES (%s, %s)",
                    (version, datetime.now(timezone.utc)),
                )
            conn.commit()
            print("OK")
        except Exception as e:
            conn.rollback()
            print(f"FAILED\n  Error: {e}")
            sys.exit(1)

    print(f"\n  {len(pending)} migration(s) applied.")


def migrate_down(conn, config: dict, target_version: str | None = None):
    """Roll back migrations. If target_version given, roll back to (but not including) that version."""
    ensure_migrations_table(conn)
    applied = get_applied_versions(conn)
    migrations = get_migration_files(config)

    # Only roll back applied migrations, in reverse order
    to_rollback = [(v, f) for v, f in reversed(migrations) if v in applied]

    if target_version is not None:
        # Roll back until we reach the target version (keep target applied)
        to_rollback = [(v, f) for v, f in to_rollback if v > target_version]

    if not to_rollback:
        print("Nothing to roll back.")
        return

    for version, filepath in to_rollback:
        _, down_sql = parse_migration(filepath)
        print(f"  Rolling back {filepath.name}...", end=" ")
        try:
            with conn.cursor() as cur:
                cur.execute(down_sql)
                cur.execute(
                    "DELETE FROM public.schema_migrations WHERE version = %s",
                    (version,),
                )
            conn.commit()
            print("OK")
        except Exception as e:
            conn.rollback()
            print(f"FAILED\n  Error: {e}")
            sys.exit(1)

    print(f"\n  {len(to_rollback)} migration(s) rolled back.")


def migrate_status(conn, config: dict):
    """Show migration status."""
    ensure_migrations_table(conn)
    applied = get_applied_versions(conn)
    migrations = get_migration_files(config)

    print(f"\n  Template: {config['app_template']}")
    print(f"  Tracking: {'enabled' if config['enable_tracking'] else 'disabled'}")
    print(f"\n  {'Version':<10} {'File':<40} {'Status':<12} {'Applied At'}")
    print(f"  {'─' * 10} {'─' * 40} {'─' * 12} {'─' * 25}")

    with conn.cursor() as cur:
        for version, filepath in migrations:
            if version in applied:
                cur.execute(
                    "SELECT applied_at FROM public.schema_migrations WHERE version = %s",
                    (version,),
                )
                row = cur.fetchone()
                applied_at = row[0].strftime("%Y-%m-%d %H:%M:%S") if row else "—"
                status = "applied"
            else:
                applied_at = "—"
                status = "pending"

            print(f"  {version:<10} {filepath.name:<40} {status:<12} {applied_at}")

    print()


def main():
    parser = argparse.ArgumentParser(description="Database migration runner")
    subparsers = parser.add_subparsers(dest="command", help="Migration command")

    subparsers.add_parser("up", help="Apply all pending migrations")

    down_parser = subparsers.add_parser("down", help="Roll back migrations")
    down_parser.add_argument("--to", dest="target", help="Roll back to this version (keep it applied)")

    subparsers.add_parser("status", help="Show migration status")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    config = get_config()
    conn = get_connection()

    try:
        if args.command == "up":
            print("\nRunning migrations UP...")
            migrate_up(conn, config)
        elif args.command == "down":
            target = getattr(args, "target", None)
            if target:
                print(f"\nRolling back to version {target}...")
            else:
                print("\nRolling back ALL migrations...")
            migrate_down(conn, config, target)
        elif args.command == "status":
            migrate_status(conn, config)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
