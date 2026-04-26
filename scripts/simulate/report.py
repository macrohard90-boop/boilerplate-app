"""Report generation — format results to terminal + files."""

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def print_summary(
    checks: list,
    phase_results: list[dict],
    duration_secs: float,
    target: str,
    user_count: int,
) -> None:
    """Print a summary report to the terminal."""
    total = len(checks)
    passed = sum(1 for c in checks if c.passed)
    failed = total - passed

    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  SIMULATION REPORT - {datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}")
    print(f"  Target: {target}")
    print(f"  Users: {user_count}")
    print(f"  Duration: {duration_secs:.0f}s")
    print(sep)

    # Phase results
    for pr in phase_results:
        status = "PASS" if pr.get("success") else "FAIL"
        marker = "+" if pr.get("success") else "X"
        name = pr.get("phase", "?")
        msg = pr.get("message", "")
        dur = pr.get("duration_ms", 0) / 1000
        print(f"  [{marker}] {name} ({dur:.1f}s) ... {msg}")

    print()

    # Group checks by category
    categories: dict[str, list] = {}
    for c in checks:
        categories.setdefault(c.category, []).append(c)

    for cat, cat_checks in categories.items():
        print(f"  {cat}")
        for c in cat_checks:
            marker = "+" if c.passed else "X"
            print(f"    [{marker}] {c.name}: {c.actual} (expected {c.expected})")
            if c.detail:
                print(f"        {c.detail}")
        print()

    # Summary
    if failed == 0:
        print(f"  RESULT: {passed}/{total} checks passed - ALL PASSED")
    else:
        print(f"  RESULT: {passed}/{total} checks passed, {failed} FAILED")
    print(sep)
    print()


def write_report_files(
    report_dir: str,
    checks: list,
    phase_results: list[dict],
    phase2_result: dict | None,
    users: list | None,
    duration_secs: float,
    target: str,
    user_count: int,
) -> Path:
    """Write detailed report files to disk. Returns the report directory path."""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = Path(report_dir) / f"sim-{ts}"
    out.mkdir(parents=True, exist_ok=True)

    total = len(checks)
    passed = sum(1 for c in checks if c.passed)

    # summary.json
    summary = {
        "timestamp": datetime.now().isoformat(),
        "target": target,
        "user_count": user_count,
        "duration_secs": round(duration_secs, 1),
        "total_checks": total,
        "passed": passed,
        "failed": total - passed,
        "phases": phase_results,
        "checks": [
            {
                "category": c.category,
                "name": c.name,
                "expected": c.expected,
                "actual": c.actual,
                "passed": c.passed,
                "detail": c.detail,
            }
            for c in checks
        ],
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2))

    # failures.json
    failures = [
        {
            "category": c.category,
            "name": c.name,
            "expected": c.expected,
            "actual": c.actual,
            "detail": c.detail,
        }
        for c in checks
        if not c.passed
    ]
    (out / "failures.json").write_text(json.dumps(failures, indent=2))

    # phase2_catalog.json
    if phase2_result:
        (out / "phase2_catalog.json").write_text(
            json.dumps(phase2_result, indent=2, default=str)
        )

    # users.json (per-user action logs)
    if users:
        user_data = []
        for u in users:
            user_data.append(
                {
                    "email": u.email,
                    "persona": u.persona.name,
                    "agent": u.agent.browser,
                    "device": u.agent.device_type,
                    "action_count": len(u.actions),
                    "orders": len(u.orders),
                    "actions": [
                        {
                            "action": a.action,
                            "endpoint": a.endpoint,
                            "method": a.method,
                            "status_code": a.status_code,
                            "passed": a.passed,
                            "detail": a.detail,
                        }
                        for a in u.actions
                    ],
                }
            )
        (out / "users.json").write_text(json.dumps(user_data, indent=2))

    # summary.txt (human-readable)
    lines = []
    lines.append("=" * 60)
    lines.append(
        f"  SIMULATION REPORT - {datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}"
    )
    lines.append(f"  Target: {target}")
    lines.append(f"  Users: {user_count}")
    lines.append(f"  Duration: {duration_secs:.0f}s")
    lines.append("=" * 60)
    lines.append("")

    for pr in phase_results:
        status = "PASS" if pr.get("success") else "FAIL"
        name = pr.get("phase", "?")
        msg = pr.get("message", "")
        lines.append(f"  [{status}] {name}: {msg}")

    lines.append("")

    categories: dict[str, list] = {}
    for c in checks:
        categories.setdefault(c.category, []).append(c)

    for cat, cat_checks in categories.items():
        lines.append(f"  {cat}")
        for c in cat_checks:
            marker = "PASS" if c.passed else "FAIL"
            lines.append(f"    [{marker}] {c.name}: {c.actual} (expected {c.expected})")
            if c.detail:
                lines.append(f"           {c.detail}")
        lines.append("")

    lines.append(f"  RESULT: {passed}/{total} checks passed")
    lines.append("=" * 60)

    (out / "summary.txt").write_text("\n".join(lines))

    logger.info("Report written to %s", out)
    return out


def build_db_payload(
    checks: list,
    phase_results: list[dict],
    users: list | None,
    duration_secs: float,
    target: str,
    user_count: int,
    sections_run: list[str],
) -> dict:
    """Build the payload for inserting into analytics.simulation_runs."""
    total = len(checks)
    passed = sum(1 for c in checks if c.passed)

    run_data = {
        "target_url": target,
        "user_count": user_count,
        "sections_run": sections_run,
        "summary": {
            "total_checks": total,
            "passed": passed,
            "failed": total - passed,
            "duration_secs": round(duration_secs, 1),
        },
        "phase_results": phase_results,
        "check_results": [
            {
                "category": c.category,
                "name": c.name,
                "expected": c.expected,
                "actual": c.actual,
                "passed": c.passed,
                "detail": c.detail,
            }
            for c in checks
        ],
    }

    user_results = []
    if users:
        for u in users:
            passed_actions = sum(1 for a in u.actions if a.passed)
            user_results.append(
                {
                    "user_email": u.email,
                    "persona": u.persona.name,
                    "actions": [
                        {
                            "action": a.action,
                            "endpoint": a.endpoint,
                            "method": a.method,
                            "status_code": a.status_code,
                            "passed": a.passed,
                            "detail": a.detail,
                        }
                        for a in u.actions
                    ],
                    "events_expected": 0,  # filled by verify
                    "events_recorded": 0,
                    "result": "PASS" if passed_actions == len(u.actions) else "FAIL",
                }
            )

    run_data["user_results"] = user_results
    return run_data
