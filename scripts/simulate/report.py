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

    # report.html (visual browser report)
    _write_html_report(
        out,
        checks=checks,
        phase_results=phase_results,
        phase2_result=phase2_result,
        users=users,
        duration_secs=duration_secs,
        target=target,
        user_count=user_count,
        total=total,
        passed=passed,
    )

    logger.info("Report written to %s", out)
    return out


def _write_html_report(
    out: Path,
    checks: list,
    phase_results: list[dict],
    phase2_result: dict | None,
    users: list | None,
    duration_secs: float,
    target: str,
    user_count: int,
    total: int,
    passed: int,
) -> None:
    """Generate a self-contained HTML report."""
    failed = total - passed
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    all_passed = failed == 0 and total > 0
    status_color = "#22c55e" if all_passed else ("#ef4444" if total > 0 else "#a3a3a3")
    status_text = (
        "ALL PASSED"
        if all_passed
        else (f"{failed} FAILED" if total > 0 else "NO CHECKS RUN")
    )

    # Phase rows
    phase_rows = ""
    for pr in phase_results:
        ok = pr.get("success", False)
        icon = "&#10003;" if ok else "&#10007;"
        color = "#22c55e" if ok else "#ef4444"
        dur = pr.get("duration_ms", 0) / 1000
        errors_html = ""
        if pr.get("errors"):
            errors_html = (
                '<ul class="errors">'
                + "".join(f"<li>{_esc(e)}</li>" for e in pr["errors"])
                + "</ul>"
            )
        phase_rows += (
            f'<tr><td style="color:{color};font-weight:700">{icon}</td>'
            f'<td>{_esc(pr.get("phase", "?"))}</td>'
            f'<td>{_esc(pr.get("message", ""))}{errors_html}</td>'
            f"<td>{dur:.1f}s</td></tr>\n"
        )

    # Check rows grouped by category
    check_sections = ""
    if checks:
        categories: dict[str, list] = {}
        for c in checks:
            categories.setdefault(c.category, []).append(c)
        for cat, cat_checks in categories.items():
            cat_passed = sum(1 for c in cat_checks if c.passed)
            cat_total = len(cat_checks)
            cat_color = "#22c55e" if cat_passed == cat_total else "#ef4444"
            rows = ""
            for c in cat_checks:
                ok = c.passed
                icon = "&#10003;" if ok else "&#10007;"
                color = "#22c55e" if ok else "#ef4444"
                detail = (
                    f'<div class="detail">{_esc(c.detail)}</div>' if c.detail else ""
                )
                rows += (
                    f'<tr><td style="color:{color}">{icon}</td>'
                    f"<td>{_esc(c.name)}</td>"
                    f"<td>{_esc(str(c.actual))}</td>"
                    f"<td>{_esc(str(c.expected))}</td>"
                    f"<td>{detail}</td></tr>\n"
                )
            check_sections += f"""
            <div class="check-group">
                <h3 style="color:{cat_color}">{_esc(cat)} ({cat_passed}/{cat_total})</h3>
                <table>
                    <thead><tr><th></th><th>Check</th><th>Actual</th><th>Expected</th><th>Detail</th></tr></thead>
                    <tbody>{rows}</tbody>
                </table>
            </div>
            """

    # Catalog summary
    catalog_html = ""
    if phase2_result:
        products = phase2_result.get("products", [])
        cats = phase2_result.get("categories", [])
        coupons = phase2_result.get("coupons", [])
        active = len([p for p in products if p.get("status") == "active"])
        draft = len([p for p in products if p.get("status") == "draft"])
        subs = len([p for p in products if p.get("pricing_type") == "recurring"])
        parent_cats = len([c for c in cats if c.get("parent") is None])
        sub_cats = len([c for c in cats if c.get("parent") is not None])

        product_rows = ""
        for p in products:
            variant_count = len(p.get("variants", []))
            product_rows += (
                f'<tr><td>{_esc(p.get("name", ""))}</td>'
                f'<td>{_esc(p.get("status", ""))}</td>'
                f'<td>{_esc(p.get("pricing_type", "one_time"))}</td>'
                f'<td>${p.get("base_price", 0) / 100:.2f}</td>'
                f'<td>{_esc(p.get("category", ""))}</td>'
                f"<td>{variant_count}</td></tr>\n"
            )

        coupon_rows = ""
        for c in coupons:
            val = (
                f'{c.get("value", 0)}%'
                if c.get("type") == "percentage"
                else f'${c.get("value", 0) / 100:.2f}'
            )
            coupon_rows += (
                f'<tr><td><code>{_esc(c.get("code", ""))}</code></td>'
                f'<td>{_esc(c.get("type", ""))}</td>'
                f"<td>{val}</td>"
                f'<td>{_esc(c.get("description", ""))}</td></tr>\n'
            )

        catalog_html = f"""
        <section>
            <h2>Catalog Summary</h2>
            <div class="kpi-row">
                <div class="kpi"><div class="kpi-value">{len(products)}</div><div class="kpi-label">Products</div></div>
                <div class="kpi"><div class="kpi-value">{active}</div><div class="kpi-label">Active</div></div>
                <div class="kpi"><div class="kpi-value">{draft}</div><div class="kpi-label">Draft</div></div>
                <div class="kpi"><div class="kpi-value">{subs}</div><div class="kpi-label">Subscriptions</div></div>
                <div class="kpi"><div class="kpi-value">{parent_cats}+{sub_cats}</div><div class="kpi-label">Categories</div></div>
                <div class="kpi"><div class="kpi-value">{len(coupons)}</div><div class="kpi-label">Coupons</div></div>
            </div>
            <details><summary>Products ({len(products)})</summary>
            <table>
                <thead><tr><th>Name</th><th>Status</th><th>Type</th><th>Price</th><th>Category</th><th>Variants</th></tr></thead>
                <tbody>{product_rows}</tbody>
            </table>
            </details>
            <details><summary>Coupons ({len(coupons)})</summary>
            <table>
                <thead><tr><th>Code</th><th>Type</th><th>Value</th><th>Description</th></tr></thead>
                <tbody>{coupon_rows}</tbody>
            </table>
            </details>
        </section>
        """

    # User summary
    users_html = ""
    if users:
        total_actions = sum(len(u.actions) for u in users)
        total_orders = sum(len(u.orders) for u in users)
        failed_users = sum(1 for u in users if u.result == "FAIL")
        users_html = f"""
        <section>
            <h2>User Simulation</h2>
            <div class="kpi-row">
                <div class="kpi"><div class="kpi-value">{len(users)}</div><div class="kpi-label">Users</div></div>
                <div class="kpi"><div class="kpi-value">{total_actions}</div><div class="kpi-label">Actions</div></div>
                <div class="kpi"><div class="kpi-value">{total_orders}</div><div class="kpi-label">Orders</div></div>
                <div class="kpi"><div class="kpi-value">{failed_users}</div><div class="kpi-label">Failed</div></div>
            </div>
        </section>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Simulation Report — {ts}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0a0a0a;color:#e5e5e5;padding:24px;max-width:1200px;margin:0 auto}}
h1{{font-size:1.5rem;margin-bottom:4px}}
h2{{font-size:1.2rem;margin:24px 0 12px;border-bottom:1px solid #333;padding-bottom:6px}}
h3{{font-size:1rem;margin:16px 0 8px}}
.header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:24px;padding:16px;background:#171717;border-radius:8px;border:1px solid #333}}
.status{{font-size:1.1rem;font-weight:700;color:{status_color}}}
.meta{{color:#a3a3a3;font-size:0.85rem;margin-top:4px}}
table{{width:100%;border-collapse:collapse;margin:8px 0;font-size:0.85rem}}
th{{text-align:left;padding:8px 10px;background:#1a1a1a;border-bottom:2px solid #333;font-weight:600;color:#a3a3a3;text-transform:uppercase;font-size:0.75rem;letter-spacing:0.5px}}
td{{padding:6px 10px;border-bottom:1px solid #262626}}
tr:hover td{{background:#1a1a1a}}
.kpi-row{{display:flex;gap:12px;flex-wrap:wrap;margin:12px 0}}
.kpi{{background:#171717;border:1px solid #333;border-radius:8px;padding:12px 20px;text-align:center;min-width:100px}}
.kpi-value{{font-size:1.5rem;font-weight:700;color:#f5f5f5}}
.kpi-label{{font-size:0.75rem;color:#a3a3a3;text-transform:uppercase;margin-top:2px}}
.check-group{{margin:12px 0}}
.detail{{color:#a3a3a3;font-size:0.8rem}}
.errors{{margin-top:4px;padding-left:16px;color:#fca5a5;font-size:0.8rem}}
details{{margin:8px 0}}
summary{{cursor:pointer;color:#60a5fa;font-weight:600;padding:4px 0}}
code{{background:#262626;padding:2px 6px;border-radius:3px;font-size:0.85rem}}
section{{margin-bottom:24px}}
</style>
</head>
<body>
<div class="header">
    <div>
        <h1>Simulation Report</h1>
        <div class="meta">{ts} &middot; {_esc(target)} &middot; {user_count} users &middot; {duration_secs:.0f}s</div>
    </div>
    <div class="status">{status_text}</div>
</div>

<section>
    <h2>Phases</h2>
    <table>
        <thead><tr><th></th><th>Phase</th><th>Result</th><th>Duration</th></tr></thead>
        <tbody>{phase_rows}</tbody>
    </table>
</section>

{catalog_html}
{users_html}

<section>
    <h2>Verification Checks ({passed}/{total})</h2>
    {check_sections if check_sections else '<p style="color:#a3a3a3">No checks were run in this session.</p>'}
</section>

</body>
</html>"""

    (out / "report.html").write_text(html)


def _esc(text: str) -> str:
    """Escape HTML special characters."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


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
