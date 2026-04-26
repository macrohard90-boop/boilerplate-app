#!/usr/bin/env python3
"""Full-stack simulation & sanity test suite — entry point.

Usage:
    # Full simulation (all phases)
    python scripts/simulate/runner.py --target http://34.30.88.59

    # Fewer users for quick iteration
    python scripts/simulate/runner.py --target http://34.30.88.59 --users 10

    # Partial runs — test specific sections
    python scripts/simulate/runner.py --target http://34.30.88.59 --only reset,setup
    python scripts/simulate/runner.py --target http://34.30.88.59 --only auth
    python scripts/simulate/runner.py --target http://34.30.88.59 --only browse,cart
    python scripts/simulate/runner.py --target http://34.30.88.59 --only checkout
    python scripts/simulate/runner.py --target http://34.30.88.59 --only verify
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

# Add project root to path so we can import simulate package
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.simulate import phase1_reset, phase2_setup, phase3_users, phase4_verify
from scripts.simulate.config import SimConfig
from scripts.simulate.report import build_db_payload, print_summary, write_report_files

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("simulate")

# All valid section names
VALID_SECTIONS = [
    "reset",
    "setup",
    "auth",
    "browse",
    "cart",
    "checkout",
    "verify",
    "full",
]


def _load_env() -> dict[str, str]:
    """Load .env file from project root."""
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


def _get_db_url(config: SimConfig) -> str:
    """Build a psycopg2-compatible DB URL."""
    if config.db_password:
        return (
            f"postgresql://{config.db_user}:{config.db_password}"
            f"@{config.db_host}:{config.db_port}/{config.db_name}"
        )
    # Fallback: try DATABASE_URL from .env
    env = _load_env()
    url = os.environ.get("DATABASE_URL", env.get("DATABASE_URL", ""))
    return url.replace("postgresql+asyncpg://", "postgresql://")


def _save_to_db(db_url: str, payload: dict) -> None:
    """Save simulation results to analytics.simulation_runs table."""
    try:
        import psycopg2

        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()

        # Check if tables exist
        cur.execute(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.tables "
            "  WHERE table_schema = 'analytics' "
            "  AND table_name = 'simulation_runs'"
            ")"
        )
        if not cur.fetchone()[0]:
            logger.warning(
                "analytics.simulation_runs table not found — skipping DB save. "
                "Run migration 035 to create it."
            )
            cur.close()
            conn.close()
            return

        import uuid
        from datetime import datetime, timezone

        run_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        cur.execute(
            "INSERT INTO analytics.simulation_runs "
            "(id, started_at, completed_at, target_url, user_count, status, "
            " sections_run, summary, phase_results, check_results) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                run_id,
                now,
                now,
                payload["target_url"],
                payload["user_count"],
                "completed",
                payload["sections_run"],
                json.dumps(payload["summary"]),
                json.dumps(payload["phase_results"]),
                json.dumps(payload["check_results"]),
            ),
        )

        # Save user results
        for ur in payload.get("user_results", []):
            cur.execute(
                "INSERT INTO analytics.simulation_user_results "
                "(id, run_id, user_email, persona, actions, "
                " events_expected, events_recorded, result) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    str(uuid.uuid4()),
                    run_id,
                    ur["user_email"],
                    ur["persona"],
                    json.dumps(ur["actions"]),
                    ur["events_expected"],
                    ur["events_recorded"],
                    ur["result"],
                ),
            )

        cur.close()
        conn.close()
        logger.info("Results saved to analytics.simulation_runs (run_id=%s)", run_id)

    except Exception as e:
        logger.warning("Could not save results to DB: %s", e)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Full-stack simulation & sanity test suite"
    )
    parser.add_argument(
        "--target",
        default="http://localhost",
        help="Target URL (e.g. http://34.30.88.59)",
    )
    parser.add_argument(
        "--users",
        type=int,
        default=100,
        help="Number of simulated users (default: 100)",
    )
    parser.add_argument(
        "--only",
        default="",
        help="Comma-separated sections to run (reset,setup,auth,browse,cart,checkout,verify)",
    )
    parser.add_argument(
        "--report-dir",
        default="reports",
        help="Directory for report output (default: reports/)",
    )
    parser.add_argument(
        "--skip-stripe-check",
        action="store_true",
        help="Skip the Stripe test data cleanup confirmation prompt",
    )

    args = parser.parse_args()

    # Parse sections
    if args.only:
        sections = [s.strip().lower() for s in args.only.split(",")]
        for s in sections:
            if s not in VALID_SECTIONS:
                print(
                    f"ERROR: Unknown section '{s}'. Valid: {', '.join(VALID_SECTIONS)}"
                )
                return 1
    else:
        sections = ["full"]

    is_full = "full" in sections

    # Build config
    config = SimConfig.from_env()
    config.target = args.target
    config.user_count = args.users
    config.report_dir = args.report_dir
    config.only_sections = sections

    # Set Stripe key from env
    env = _load_env()
    if not config.stripe_secret_key:
        config.stripe_secret_key = os.environ.get(
            "STRIPE_SECRET_KEY", env.get("STRIPE_SECRET_KEY", "")
        )
    if config.stripe_secret_key:
        os.environ["STRIPE_SECRET_KEY"] = config.stripe_secret_key

    db_url = _get_db_url(config)

    print()
    print("=" * 60)
    print("  FULL-STACK SIMULATION")
    print(f"  Target:   {config.target}")
    print(f"  Users:    {config.user_count}")
    print(f"  Sections: {', '.join(sections)}")
    print("=" * 60)
    print()

    # Stripe cleanup reminder
    needs_stripe = is_full or any(s in sections for s in ["reset", "setup", "checkout"])
    if needs_stripe and not args.skip_stripe_check:
        answer = (
            input("Have you cleared Stripe test data in the Dashboard? [y/N] ")
            .strip()
            .lower()
        )
        if answer != "y":
            print("Aborted. Clear Stripe test data first:")
            print("  Stripe Dashboard -> Settings -> Test Data -> Delete all test data")
            return 1

    # Track overall timing and results
    start_time = time.time()
    phase_results: list[dict] = []
    checks = []
    phase2_result = None
    sim_users = None

    # ── Phase 1: Reset ──
    if is_full or "reset" in sections:
        logger.info("Phase 1: Reset — wiping database...")
        t0 = time.time()
        try:
            result = phase1_reset.run(db_url=db_url)
            elapsed = (time.time() - t0) * 1000
            if result["errors"]:
                phase_results.append(
                    {
                        "phase": "Phase 1: Reset",
                        "success": False,
                        "message": f"Truncated {result['tables_truncated']} tables, {len(result['errors'])} errors",
                        "duration_ms": elapsed,
                        "errors": result["errors"],
                    }
                )
                logger.warning("Phase 1 errors: %s", result["errors"])
            else:
                phase_results.append(
                    {
                        "phase": "Phase 1: Reset",
                        "success": True,
                        "message": f"Truncated {result['tables_truncated']} tables, seeded {result['events_seeded']} event blocks",
                        "duration_ms": elapsed,
                    }
                )
                logger.info(
                    "Phase 1: Reset complete (%d tables)", result["tables_truncated"]
                )
        except Exception as e:
            elapsed = (time.time() - t0) * 1000
            phase_results.append(
                {
                    "phase": "Phase 1: Reset",
                    "success": False,
                    "message": str(e),
                    "duration_ms": elapsed,
                }
            )
            logger.error("Phase 1 FAILED: %s", e)
            if is_full:
                print(f"\nFATAL: Phase 1 failed — {e}")
                return 1

    # ── Phase 2: Admin Setup ──
    if is_full or "setup" in sections:
        logger.info("Phase 2: Admin Setup — bootstrapping app...")
        t0 = time.time()
        try:
            phase2_result = phase2_setup.run(
                api_url=config.api_url,
                admin_email=config.admin_email,
                admin_password=config.admin_password,
            )
            elapsed = (time.time() - t0) * 1000

            if phase2_result["errors"]:
                phase_results.append(
                    {
                        "phase": "Phase 2: Admin Setup",
                        "success": False,
                        "message": f"{len(phase2_result['products'])} products, {len(phase2_result['errors'])} errors",
                        "duration_ms": elapsed,
                        "errors": phase2_result["errors"],
                    }
                )
                logger.warning("Phase 2 errors: %s", phase2_result["errors"])
                if is_full and not phase2_result["products"]:
                    print(f"\nFATAL: Phase 2 failed — no products created")
                    return 1
            else:
                phase_results.append(
                    {
                        "phase": "Phase 2: Admin Setup",
                        "success": True,
                        "message": (
                            f"{len(phase2_result['products'])} products, "
                            f"{len(phase2_result['categories'])} categories, "
                            f"Stripe {'synced' if phase2_result['stripe_synced'] else 'NOT synced'}"
                        ),
                        "duration_ms": elapsed,
                    }
                )
                logger.info(
                    "Phase 2: Setup complete (%d products, Stripe %s)",
                    len(phase2_result["products"]),
                    "synced" if phase2_result["stripe_synced"] else "NOT synced",
                )
        except Exception as e:
            elapsed = (time.time() - t0) * 1000
            phase_results.append(
                {
                    "phase": "Phase 2: Admin Setup",
                    "success": False,
                    "message": str(e),
                    "duration_ms": elapsed,
                }
            )
            logger.error("Phase 2 FAILED: %s", e)
            if is_full:
                print(f"\nFATAL: Phase 2 failed — {e}")
                return 1

    # ── Phase 3: User Simulation ──
    # Determine which sub-sections of Phase 3 to run
    p3_sections = []
    if is_full:
        p3_sections = ["auth", "browse", "cart", "checkout"]
    else:
        for s in ["auth", "browse", "cart", "checkout"]:
            if s in sections:
                p3_sections.append(s)

    if p3_sections:
        logger.info("Phase 3: User Simulation — %s...", ", ".join(p3_sections))
        t0 = time.time()

        # Get catalog from Phase 2 result or fetch from API
        catalog = []
        categories = []
        if phase2_result:
            catalog = phase2_result.get("products", [])
            categories = phase2_result.get("categories", [])
        else:
            # Try fetching from API (setup was run previously)
            try:
                import httpx

                resp = httpx.get(f"{config.api_url}/products", timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("items", data) if isinstance(data, dict) else data
                    for p in items:
                        catalog.append(
                            {
                                "name": p.get("name"),
                                "id": p.get("id"),
                                "variants": [
                                    {
                                        "id": v["id"],
                                        "name": v.get("name", ""),
                                        "stock": v.get("stock_quantity", 0),
                                    }
                                    for v in p.get("variants", [])
                                ],
                                "pricing_type": p.get("pricing_type", "one_time"),
                            }
                        )
                    logger.info("Fetched %d products from API", len(catalog))
            except Exception as e:
                logger.warning("Could not fetch catalog: %s", e)

        if not catalog:
            logger.error("No catalog available — run setup first")
            phase_results.append(
                {
                    "phase": "Phase 3: Users",
                    "success": False,
                    "message": "No catalog — run setup first",
                    "duration_ms": 0,
                }
            )
        else:
            try:
                sim_users = asyncio.run(
                    phase3_users.run(
                        api_url=config.api_url,
                        db_url=db_url,
                        user_count=config.user_count,
                        user_password=config.user_password,
                        catalog=catalog,
                        categories=categories,
                        email_pattern=config.user_email_pattern,
                    )
                )
                elapsed = (time.time() - t0) * 1000

                total_actions = sum(len(u.actions) for u in sim_users)
                total_orders = sum(len(u.orders) for u in sim_users)
                failed_users = sum(1 for u in sim_users if u.result == "FAIL")

                phase_results.append(
                    {
                        "phase": "Phase 3: Users",
                        "success": failed_users == 0,
                        "message": (
                            f"{len(sim_users)} users, {total_actions} actions, "
                            f"{total_orders} orders, {failed_users} failures"
                        ),
                        "duration_ms": elapsed,
                    }
                )
                logger.info(
                    "Phase 3: Complete — %d users, %d actions, %d orders",
                    len(sim_users),
                    total_actions,
                    total_orders,
                )
            except Exception as e:
                elapsed = (time.time() - t0) * 1000
                phase_results.append(
                    {
                        "phase": "Phase 3: Users",
                        "success": False,
                        "message": str(e),
                        "duration_ms": elapsed,
                    }
                )
                logger.error("Phase 3 FAILED: %s", e)

    # ── Phase 4: Verify ──
    if is_full or "verify" in sections:
        logger.info("Phase 4: Verify — running checks...")
        t0 = time.time()
        try:
            checks = phase4_verify.run(
                user_count=config.user_count,
                db_url=db_url,
            )
            elapsed = (time.time() - t0) * 1000

            passed = sum(1 for c in checks if c.passed)
            total = len(checks)
            phase_results.append(
                {
                    "phase": "Phase 4: Verify",
                    "success": passed == total,
                    "message": f"{passed}/{total} checks passed",
                    "duration_ms": elapsed,
                }
            )
            logger.info("Phase 4: Verify complete — %d/%d passed", passed, total)
        except Exception as e:
            elapsed = (time.time() - t0) * 1000
            phase_results.append(
                {
                    "phase": "Phase 4: Verify",
                    "success": False,
                    "message": str(e),
                    "duration_ms": elapsed,
                }
            )
            logger.error("Phase 4 FAILED: %s", e)

    # ── Report ──
    total_duration = time.time() - start_time

    if checks:
        print_summary(
            checks=checks,
            phase_results=phase_results,
            duration_secs=total_duration,
            target=config.target,
            user_count=config.user_count,
        )

    # Write files
    report_path = write_report_files(
        report_dir=config.report_dir,
        checks=checks,
        phase_results=phase_results,
        phase2_result=phase2_result,
        users=sim_users,
        duration_secs=total_duration,
        target=config.target,
        user_count=config.user_count,
    )
    print(f"Report files: {report_path}")

    # Save to DB
    if checks:
        payload = build_db_payload(
            checks=checks,
            phase_results=phase_results,
            users=sim_users,
            duration_secs=total_duration,
            target=config.target,
            user_count=config.user_count,
            sections_run=sections,
        )
        _save_to_db(db_url, payload)

    # Exit code: 0 if all checks passed, 1 otherwise
    if checks:
        all_passed = all(c.passed for c in checks)
        return 0 if all_passed else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
