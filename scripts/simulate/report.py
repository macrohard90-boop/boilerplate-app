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


def _json_html(obj: object, max_depth: int = 3) -> str:
    """Render a Python object as syntax-highlighted HTML JSON."""
    try:
        raw = json.dumps(obj, indent=2, default=str)
    except Exception:
        raw = str(obj)
    # Escape HTML, then colorize
    s = _esc(raw)
    # Keys
    s = s.replace("&quot;", '"')
    import re

    # Color strings (values)
    s = re.sub(
        r'"([^"]*)"(\s*:)',
        r'<span class="jk">"\1"</span>\2',
        s,
    )
    s = re.sub(
        r'"([^"]*)"',
        r'<span class="js">"\1"</span>',
        s,
    )
    # Numbers
    s = re.sub(r"\b(\d+\.?\d*)\b", r'<span class="jn">\1</span>', s)
    # Booleans / null
    s = re.sub(r"\b(true|false|null)\b", r'<span class="jb">\1</span>', s)
    return f'<pre class="json-block">{s}</pre>'


def _classify_api_call(url: str, method: str) -> str:
    """Classify an API call into a group for tab filtering."""
    if "/auth/" in url:
        return "auth"
    if "/categories" in url:
        return "categories"
    if "/variants" in url:
        return "variants"
    if "/images" in url:
        return "images"
    if "/products" in url:
        return "products"
    if "/discounts" in url:
        return "coupons"
    if "/tracking/" in url:
        return "tracking"
    return "other"


def _status_color(code: int) -> str:
    if 200 <= code < 300:
        return "#22c55e"
    if 300 <= code < 400:
        return "#facc15"
    if 400 <= code < 500:
        return "#f97316"
    return "#ef4444"


def _build_admin_card(phase2_result: dict) -> str:
    """Section A: Admin User Card."""
    admin = phase2_result.get("admin_detail", {})
    api_log = phase2_result.get("api_log", [])
    analytics = phase2_result.get("analytics_summary", {})
    total_events = sum(analytics.get("admin_events", {}).values())

    return f"""
    <section>
        <h2>Admin User</h2>
        <div style="background:#171717;border:1px solid #333;border-radius:8px;padding:16px;margin:8px 0">
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:0.85rem">
                <div><span style="color:#a3a3a3">Email:</span> <code>{_esc(admin.get('email', ''))}</code></div>
                <div><span style="color:#a3a3a3">Role:</span> <code>{_esc(admin.get('role', ''))}</code></div>
                <div><span style="color:#a3a3a3">User ID:</span> <code style="font-size:0.75rem">{_esc(admin.get('user_id', ''))}</code></div>
                <div><span style="color:#a3a3a3">Session ID:</span> <code style="font-size:0.75rem">{_esc(admin.get('session_id', ''))}</code></div>
            </div>
        </div>
        <div class="kpi-row">
            <div class="kpi"><div class="kpi-value">{len(api_log)}</div><div class="kpi-label">API Calls</div></div>
            <div class="kpi"><div class="kpi-value">{total_events}</div><div class="kpi-label">Admin Events</div></div>
            <div class="kpi"><div class="kpi-value">{analytics.get('page_views', 0)}</div><div class="kpi-label">Page Views</div></div>
            <div class="kpi"><div class="kpi-value">{analytics.get('sessions', 0)}</div><div class="kpi-label">Sessions</div></div>
            <div class="kpi"><div class="kpi-value">{analytics.get('builtin_templates', 0)}</div><div class="kpi-label">Templates</div></div>
        </div>
    </section>
    """


def _build_db_delta(phase2_result: dict) -> str:
    """Section B: Database State Delta."""
    db_before = phase2_result.get("db_before", {})
    db_after = phase2_result.get("db_after", {})
    if not db_before and not db_after:
        return ""

    all_tables = sorted(set(list(db_before.keys()) + list(db_after.keys())))
    rows = ""
    total_before = 0
    total_after = 0
    for table in all_tables:
        before = db_before.get(table, 0)
        after = db_after.get(table, 0)
        delta = after - before
        total_before += before
        total_after += after

        if after == 0 and before == 0:
            continue  # Skip empty tables

        if delta > 0:
            delta_html = f'<span style="color:#22c55e">+{delta}</span>'
        elif delta < 0:
            delta_html = f'<span style="color:#ef4444">{delta}</span>'
        else:
            delta_html = '<span style="color:#525252">0</span>'

        row_bg = (
            "" if delta == 0 else ' style="background:#0d1f0d"' if delta > 0 else ""
        )
        rows += (
            f"<tr{row_bg}>"
            f"<td><code>{_esc(table)}</code></td>"
            f'<td style="text-align:right">{before}</td>'
            f'<td style="text-align:right">{after}</td>'
            f'<td style="text-align:right">{delta_html}</td>'
            f"</tr>\n"
        )

    total_delta = total_after - total_before
    delta_color = "#22c55e" if total_delta > 0 else "#a3a3a3"

    return f"""
    <section>
        <h2>Database State Delta</h2>
        <div class="kpi-row">
            <div class="kpi"><div class="kpi-value">{total_before}</div><div class="kpi-label">Rows Before</div></div>
            <div class="kpi"><div class="kpi-value">{total_after}</div><div class="kpi-label">Rows After</div></div>
            <div class="kpi"><div class="kpi-value" style="color:{delta_color}">+{total_delta}</div><div class="kpi-label">New Rows</div></div>
        </div>
        <table>
            <thead><tr>
                <th>Table</th>
                <th style="text-align:right">Before</th>
                <th style="text-align:right">After</th>
                <th style="text-align:right">Delta</th>
            </tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </section>
    """


def _build_api_log(phase2_result: dict) -> str:
    """Section C: API Call Log with tabs."""
    api_log = phase2_result.get("api_log", [])
    if not api_log:
        return ""

    # Group calls
    groups: dict[str, list] = {}
    for i, call in enumerate(api_log):
        group = _classify_api_call(call["url"], call["method"])
        groups.setdefault(group, []).append((i, call))

    # Tab order
    tab_order = [
        "all",
        "auth",
        "categories",
        "products",
        "variants",
        "images",
        "coupons",
        "tracking",
        "other",
    ]
    tab_labels = {
        "all": "All",
        "auth": "Auth",
        "categories": "Categories",
        "products": "Products",
        "variants": "Variants",
        "images": "Images",
        "coupons": "Coupons",
        "tracking": "Tracking",
        "other": "Other",
    }

    # Build tab buttons
    tabs_html = ""
    for tab_key in tab_order:
        if tab_key == "all":
            count = len(api_log)
        else:
            count = len(groups.get(tab_key, []))
            if count == 0:
                continue
        active = " tab-active" if tab_key == "all" else ""
        tabs_html += (
            f'<button class="api-tab{active}" data-tab="{tab_key}">'
            f"{tab_labels.get(tab_key, tab_key)} "
            f'<span class="tab-badge">{count}</span></button>\n'
        )

    # Build call entries
    entries_html = ""
    for i, call in enumerate(api_log):
        group = _classify_api_call(call["url"], call["method"])
        method = call["method"]
        # Strip base URL to show just path
        url_path = call["url"]
        for prefix in [
            "http://localhost:8000",
            "http://localhost",
            "http://34.30.88.59",
        ]:
            if url_path.startswith(prefix):
                url_path = url_path[len(prefix) :]
                break
        status = call["status"]
        color = _status_color(status)
        duration = call.get("duration_ms", 0)

        method_colors = {
            "GET": "#60a5fa",
            "POST": "#22c55e",
            "PUT": "#facc15",
            "DELETE": "#ef4444",
            "PATCH": "#c084fc",
        }
        method_color = method_colors.get(method, "#a3a3a3")

        req_json = (
            _json_html(call.get("request_body"))
            if call.get("request_body")
            else '<span style="color:#525252">No body</span>'
        )
        resp_json = (
            _json_html(call.get("response_body"))
            if call.get("response_body")
            else '<span style="color:#525252">No body</span>'
        )

        entries_html += f"""
        <details class="api-entry" data-group="{group}">
            <summary>
                <span class="api-method" style="color:{method_color}">{method}</span>
                <span class="api-path">{_esc(url_path)}</span>
                <span class="api-status" style="color:{color}">{status}</span>
                <span class="api-dur">{duration:.0f}ms</span>
            </summary>
            <div class="api-body">
                <div class="api-section">
                    <h4>Request Body</h4>
                    {req_json}
                </div>
                <div class="api-section">
                    <h4>Response Body</h4>
                    {resp_json}
                </div>
            </div>
        </details>
        """

    return f"""
    <section>
        <h2>API Call Log ({len(api_log)} calls)</h2>
        <div class="api-tabs">{tabs_html}</div>
        <div class="api-log">{entries_html}</div>
    </section>
    """


def _build_catalog_detail(phase2_result: dict) -> str:
    """Section D: Enhanced Catalog Detail."""
    products = phase2_result.get("products", [])
    cats = phase2_result.get("categories", [])
    coupons = phase2_result.get("coupons", [])
    archived = phase2_result.get("archived_products", [])
    active = len([p for p in products if p.get("status") == "active"])
    draft = len([p for p in products if p.get("status") == "draft"])
    subs = len([p for p in products if p.get("pricing_type") == "recurring"])
    parent_cats = [c for c in cats if c.get("parent") is None]
    sub_cats = [c for c in cats if c.get("parent") is not None]

    # Category tree
    cat_tree_html = ""
    for parent in parent_cats:
        children = [c for c in sub_cats if c.get("parent") == parent["name"]]
        children_html = ""
        for child in children:
            children_html += (
                f'<div style="margin-left:24px;padding:2px 0">'
                f'<span style="color:#525252">|_</span> {_esc(child["name"])} '
                f'<code style="font-size:0.7rem;color:#525252">{_esc(child.get("id", ""))[:8]}</code>'
                f"</div>\n"
            )
        cat_tree_html += (
            f'<div style="padding:4px 0">'
            f'<span style="color:#60a5fa;font-weight:600">{_esc(parent["name"])}</span> '
            f'<code style="font-size:0.7rem;color:#525252">{_esc(parent.get("id", ""))[:8]}</code>'
            f"{children_html}</div>\n"
        )

    # Products with variants
    product_rows = ""
    total_variants = 0
    for p in products:
        variants = p.get("variants", [])
        total_variants += len(variants)
        status = p.get("status", "")
        is_archived = p.get("name", "") in archived
        status_badge = ""
        if is_archived:
            status_badge = '<span style="color:#ef4444;font-size:0.7rem;background:#ef4444/10;padding:1px 4px;border-radius:3px">ARCHIVED</span>'
        elif status == "draft":
            status_badge = '<span style="color:#facc15;font-size:0.7rem">draft</span>'
        elif status == "active":
            status_badge = '<span style="color:#22c55e;font-size:0.7rem">active</span>'

        pricing = p.get("pricing_type", "one_time")
        pricing_badge = (
            ' <span style="color:#c084fc;font-size:0.7rem;background:#c084fc20;padding:1px 4px;border-radius:3px">recurring</span>'
            if pricing == "recurring"
            else ""
        )

        # Variant sub-rows
        var_html = ""
        if variants:
            var_items = ""
            for v in variants:
                stock = v.get("stock", 0)
                stock_color = "#22c55e" if stock > 0 else "#ef4444"
                var_items += (
                    f'<tr style="background:#0a0a0a">'
                    f'<td style="padding-left:30px;color:#a3a3a3;font-size:0.8rem">'
                    f'|_ {_esc(v.get("name", ""))}</td>'
                    f'<td style="font-size:0.8rem"><code style="font-size:0.7rem;color:#525252">'
                    f'{_esc(v.get("id", ""))[:8]}</code></td>'
                    f'<td style="font-size:0.8rem;color:{stock_color}">{stock}</td>'
                    f'<td colspan="2"></td></tr>\n'
                )
            var_html = var_items

        # Price display: $X.XX/mo or $X.XX/yr for recurring
        base_price = p.get("base_price", 0) / 100
        interval = p.get("recurring_interval")
        if pricing == "recurring" and interval:
            abbr = "mo" if interval == "month" else "yr"
            price_display = f"${base_price:.2f}/{abbr}"
        else:
            price_display = f"${base_price:.2f}"

        product_rows += (
            f"<tr>"
            f'<td>{_esc(p.get("name", ""))} {pricing_badge}</td>'
            f"<td>{status_badge}</td>"
            f"<td>{price_display}</td>"
            f'<td>{_esc(p.get("category", ""))}</td>'
            f"<td>{len(variants)}</td>"
            f"</tr>\n{var_html}"
        )

    # Coupon rows with all fields
    coupon_rows = ""
    for c in coupons:
        val = (
            f'{c.get("value", 0)}%'
            if c.get("type") == "percentage"
            else (
                "Free Shipping"
                if c.get("type") == "free_shipping"
                else f'${c.get("value", 0) / 100:.2f}'
            )
        )
        stripe_badge = (
            '<span style="color:#22c55e;font-size:0.7rem">synced</span>'
            if c.get("stripe_synced")
            else '<span style="color:#f97316;font-size:0.7rem">pending</span>'
        )
        coupon_rows += (
            f"<tr>"
            f'<td><code>{_esc(c.get("code", ""))}</code></td>'
            f'<td>{_esc(c.get("type", ""))}</td>'
            f"<td>{val}</td>"
            f'<td>{_esc(c.get("description", ""))}</td>'
            f"<td>{stripe_badge}</td>"
            f'<td><code style="font-size:0.7rem;color:#525252">{_esc(c.get("id", ""))[:8]}</code></td>'
            f"</tr>\n"
        )

    return f"""
    <section>
        <h2>Catalog Detail</h2>
        <div class="kpi-row">
            <div class="kpi"><div class="kpi-value">{len(products)}</div><div class="kpi-label">Products</div></div>
            <div class="kpi"><div class="kpi-value">{active}</div><div class="kpi-label">Active</div></div>
            <div class="kpi"><div class="kpi-value">{draft}</div><div class="kpi-label">Draft</div></div>
            <div class="kpi"><div class="kpi-value">{subs}</div><div class="kpi-label">Subscriptions</div></div>
            <div class="kpi"><div class="kpi-value">{len(archived)}</div><div class="kpi-label">Archived</div></div>
            <div class="kpi"><div class="kpi-value">{total_variants}</div><div class="kpi-label">Variants</div></div>
            <div class="kpi"><div class="kpi-value">{len(parent_cats)}+{len(sub_cats)}</div><div class="kpi-label">Categories</div></div>
            <div class="kpi"><div class="kpi-value">{len(coupons)}</div><div class="kpi-label">Coupons</div></div>
        </div>

        <details><summary>Category Tree ({len(parent_cats)} parents, {len(sub_cats)} children)</summary>
        <div style="font-family:monospace;font-size:0.85rem;padding:8px;background:#111;border-radius:6px;margin:4px 0">
            {cat_tree_html}
        </div>
        </details>

        <details open><summary>Products ({len(products)}) &mdash; with variant sub-rows</summary>
        <table>
            <thead><tr><th>Name</th><th>Status</th><th>Price</th><th>Category</th><th>Variants</th></tr></thead>
            <tbody>{product_rows}</tbody>
        </table>
        </details>

        <details><summary>Coupons ({len(coupons)})</summary>
        <table>
            <thead><tr><th>Code</th><th>Type</th><th>Value</th><th>Description</th><th>Stripe</th><th>ID</th></tr></thead>
            <tbody>{coupon_rows}</tbody>
        </table>
        </details>
    </section>
    """


def _build_stripe_detail(phase2_result: dict) -> str:
    """Section: Stripe Lifecycle Validation."""
    stripe = phase2_result.get("stripe_detail")
    if not stripe:
        return ""

    summary = stripe.get("summary", {})
    total = summary.get("total", 0)
    passed = summary.get("passed", 0)
    failed = summary.get("failed", 0)
    all_pass = failed == 0 and total > 0
    summary_color = "#22c55e" if all_pass else "#ef4444"

    admin = stripe.get("admin_customer", {})
    products = stripe.get("products", [])
    variants = stripe.get("variants", [])
    coupons = stripe.get("coupons", [])

    synced_products = sum(1 for p in products if p.get("stripe_product_id"))
    expected_synced_products = sum(
        1 for p in products if p.get("expected", "").startswith("id=not null")
    )
    synced_variants = sum(1 for v in variants if v.get("stripe_price_id"))
    expected_synced_variants = sum(
        1 for v in variants if v.get("expected", "").startswith("id=not null")
    )
    synced_coupons = sum(
        1 for c in coupons if c.get("stripe_coupon_id") or c.get("active") is False
    )
    expected_synced_coupons = sum(
        1 for c in coupons if c.get("type") != "free_shipping"
    )

    # ── Admin customer card ──
    cust_id = admin.get("stripe_customer_id") or "MISSING"
    cust_pass = admin.get("pass", False)
    cust_badge = (
        '<span style="color:#22c55e;font-weight:700">PASS</span>'
        if cust_pass
        else '<span style="color:#ef4444;font-weight:700">FAIL</span>'
    )
    cust_id_html = (
        f"<code>{_esc(cust_id)}</code>"
        if cust_pass
        else '<span style="color:#ef4444;font-weight:700">MISSING</span>'
    )

    admin_card = f"""
    <div style="background:#171717;border:1px solid #333;border-radius:8px;padding:16px;margin:12px 0">
        <h4 style="margin:0 0 8px;color:#a3a3a3">Admin Stripe Customer</h4>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:0.85rem">
            <div><span style="color:#a3a3a3">Email:</span> <code>{_esc(admin.get('email', ''))}</code></div>
            <div><span style="color:#a3a3a3">Customer ID:</span> {cust_id_html}</div>
            <div><span style="color:#a3a3a3">Expected:</span> Customer created on registration</div>
            <div><span style="color:#a3a3a3">Result:</span> {cust_badge}</div>
        </div>
    </div>
    """

    # ── Products table ──
    prod_rows = ""
    for p in products:
        name = p.get("name", "")
        pricing = p.get("pricing_type", "one_time")
        interval = p.get("recurring_interval")
        if pricing == "recurring" and interval:
            abbr = "mo" if interval == "month" else "yr"
            type_display = f"recurring/{abbr}"
        else:
            type_display = "one_time"

        status = p.get("status", "")
        is_archived = p.get("deleted_at") is not None
        if is_archived:
            status_html = '<span style="color:#ef4444;font-size:0.75rem;background:#ef444420;padding:1px 6px;border-radius:3px;font-weight:600">ARCHIVED</span>'
        elif status == "draft":
            status_html = '<span style="color:#facc15;font-size:0.75rem">draft</span>'
        else:
            status_html = '<span style="color:#22c55e;font-size:0.75rem">active</span>'

        spid = p.get("stripe_product_id")
        spid_html = (
            f'<code style="font-size:0.75rem">{_esc(spid[:16])}...</code>'
            if spid and len(spid) > 16
            else (
                f'<code style="font-size:0.75rem">{_esc(spid)}</code>'
                if spid
                else '<span style="color:#525252">--</span>'
            )
        )

        sync = p.get("stripe_sync_status") or "none"
        sync_color = "#22c55e" if sync == "synced" else "#a3a3a3"

        # Expected column
        if is_archived and p.get("expected", "").find("pre-archive") >= 0:
            exp_display = "synced (pre-archive)"
        elif "unsynced" in p.get("expected", ""):
            exp_display = "unsynced"
        else:
            exp_display = "synced"

        ok = p.get("pass", False)
        sync_error = p.get("stripe_sync_error") or ""
        if ok:
            result_badge = '<span style="color:#22c55e;font-weight:700;font-size:0.75rem;background:#22c55e20;padding:1px 6px;border-radius:3px">PASS</span>'
        else:
            result_badge = (
                f'<span style="color:#ef4444;font-weight:700;font-size:0.75rem;background:#ef444420;padding:1px 6px;border-radius:3px">FAIL</span>'
                f'<div style="color:#fca5a5;font-size:0.72rem;margin-top:2px;max-width:300px;word-break:break-word">{_esc(sync_error)}</div>'
                if sync_error
                else '<span style="color:#ef4444;font-weight:700;font-size:0.75rem;background:#ef444420;padding:1px 6px;border-radius:3px">FAIL</span>'
            )

        row_bg = "" if ok else ' style="background:#1f0d0d"'
        prod_rows += (
            f"<tr{row_bg}>"
            f"<td>{_esc(name)}</td>"
            f"<td><code style='font-size:0.75rem'>{type_display}</code></td>"
            f"<td>{status_html}</td>"
            f"<td>{spid_html}</td>"
            f'<td style="color:{sync_color};font-size:0.8rem">{sync}</td>'
            f"<td>{exp_display}</td>"
            f"<td>{result_badge}</td>"
            f"</tr>\n"
        )

    # ── Variants table ──
    var_rows = ""
    for v in variants:
        prod_name = v.get("product_name", "")
        var_name = v.get("name", "")
        price = v.get("price") or v.get("base_price") or 0
        currency = (v.get("currency") or "usd").upper()
        pricing = v.get("pricing_type", "one_time")
        interval = v.get("recurring_interval")

        if pricing == "recurring" and interval:
            abbr = "mo" if interval == "month" else "yr"
            price_display = f"${price / 100:.2f}/{abbr}"
            recur_display = f"{interval} x1"
        else:
            price_display = f"${price / 100:.2f}"
            recur_display = "--"

        spid = v.get("stripe_price_id")
        spid_html = (
            f'<code style="font-size:0.75rem">{_esc(spid[:16])}...</code>'
            if spid and len(spid) > 16
            else (
                f'<code style="font-size:0.75rem">{_esc(spid)}</code>'
                if spid
                else '<span style="color:#525252">--</span>'
            )
        )

        sync = v.get("stripe_sync_status") or "none"
        sync_color = "#22c55e" if sync == "synced" else "#a3a3a3"

        if "unsynced" in v.get("expected", ""):
            exp_display = "unsynced"
        elif "pre-archive" in v.get("expected", ""):
            exp_display = "synced (pre-archive)"
        else:
            exp_display = "synced"

        ok = v.get("pass", False)
        sync_error = v.get("stripe_sync_error") or ""
        if ok:
            result_badge = '<span style="color:#22c55e;font-weight:700;font-size:0.75rem;background:#22c55e20;padding:1px 6px;border-radius:3px">PASS</span>'
        else:
            result_badge = (
                f'<span style="color:#ef4444;font-weight:700;font-size:0.75rem;background:#ef444420;padding:1px 6px;border-radius:3px">FAIL</span>'
                f'<div style="color:#fca5a5;font-size:0.72rem;margin-top:2px;max-width:300px;word-break:break-word">{_esc(sync_error)}</div>'
                if sync_error
                else '<span style="color:#ef4444;font-weight:700;font-size:0.75rem;background:#ef444420;padding:1px 6px;border-radius:3px">FAIL</span>'
            )

        row_bg = "" if ok else ' style="background:#1f0d0d"'
        var_rows += (
            f"<tr{row_bg}>"
            f"<td>{_esc(prod_name)}</td>"
            f"<td>{_esc(var_name)}</td>"
            f"<td>{price_display}</td>"
            f"<td>{spid_html}</td>"
            f'<td style="font-size:0.8rem">{recur_display}</td>'
            f'<td style="color:{sync_color};font-size:0.8rem">{sync}</td>'
            f"<td>{exp_display}</td>"
            f"<td>{result_badge}</td>"
            f"</tr>\n"
        )

    # ── Coupons table ──
    coup_rows = ""
    for c in coupons:
        code = c.get("code", "")
        ctype = c.get("type", "")
        value = c.get("value", 0)
        if ctype == "percentage":
            val_display = f"{value}%"
        elif ctype == "free_shipping":
            val_display = "Free Shipping"
        else:
            val_display = f"${value / 100:.2f}"

        dur = c.get("stripe_duration", "once")

        scid = c.get("stripe_coupon_id")
        scid_html = (
            f'<code style="font-size:0.75rem">{_esc(scid[:16])}...</code>'
            if scid and len(scid) > 16
            else (
                f'<code style="font-size:0.75rem">{_esc(scid)}</code>'
                if scid
                else '<span style="color:#525252">--</span>'
            )
        )
        spid = c.get("stripe_promotion_code_id")
        spid_html = (
            f'<code style="font-size:0.75rem">{_esc(spid[:16])}...</code>'
            if spid and len(spid) > 16
            else (
                f'<code style="font-size:0.75rem">{_esc(spid)}</code>'
                if spid
                else '<span style="color:#525252">--</span>'
            )
        )

        sync = c.get("stripe_sync_status") or "none"
        sync_color = "#22c55e" if sync == "synced" else "#a3a3a3"

        ok = c.get("pass", False)

        is_deactivated = c.get("active") is False

        if ctype == "free_shipping":
            exp_display = '<span style="color:#525252">N/A (by design)</span>'
            sync_display = '<span style="color:#525252">N/A</span>'
        elif is_deactivated:
            exp_display = '<span style="color:#a78bfa">deactivated</span>'
            sync_display = '<span style="color:#a78bfa">deactivated</span>'
        else:
            exp_display = "synced"
            sync_display = f'<span style="color:{sync_color}">{sync}</span>'

        sync_error = c.get("stripe_sync_error") or ""
        if ok:
            result_badge = '<span style="color:#22c55e;font-weight:700;font-size:0.75rem;background:#22c55e20;padding:1px 6px;border-radius:3px">PASS</span>'
        else:
            result_badge = (
                f'<span style="color:#ef4444;font-weight:700;font-size:0.75rem;background:#ef444420;padding:1px 6px;border-radius:3px">FAIL</span>'
                f'<div style="color:#fca5a5;font-size:0.72rem;margin-top:2px;max-width:300px;word-break:break-word">{_esc(sync_error)}</div>'
                if sync_error
                else '<span style="color:#ef4444;font-weight:700;font-size:0.75rem;background:#ef444420;padding:1px 6px;border-radius:3px">FAIL</span>'
            )

        row_bg = "" if ok else ' style="background:#1f0d0d"'
        coup_rows += (
            f"<tr{row_bg}>"
            f"<td><code>{_esc(code)}</code></td>"
            f"<td>{_esc(ctype)}</td>"
            f"<td>{val_display}</td>"
            f"<td>{dur}</td>"
            f"<td>{scid_html}</td>"
            f"<td>{spid_html}</td>"
            f"<td>{sync_display}</td>"
            f"<td>{exp_display}</td>"
            f"<td>{result_badge}</td>"
            f"</tr>\n"
        )

    # ── Errors summary (only if failures) ──
    failures = [
        s
        for s in (
            [
                {
                    "resource": "admin_customer",
                    "name": admin.get("email", ""),
                    "reason": "Customer not created",
                }
            ]
            if not admin.get("pass", False)
            else []
        )
        + [
            {"resource": "product", "name": p["name"], "reason": p.get("reason", "")}
            for p in products
            if not p.get("pass", True)
        ]
        + [
            {
                "resource": "variant",
                "name": f"{v['product_name']}/{v['name']}",
                "reason": v.get("reason", ""),
            }
            for v in variants
            if not v.get("pass", True)
        ]
        + [
            {"resource": "coupon", "name": c["code"], "reason": c.get("reason", "")}
            for c in coupons
            if not c.get("pass", True)
        ]
    ]

    errors_html = ""
    if failures:
        error_items = "".join(
            f'<li><strong>{_esc(f["resource"])}:</strong> {_esc(f["name"])} &mdash; {_esc(f["reason"])}</li>'
            for f in failures
        )
        errors_html = f"""
        <div style="background:#1f0d0d;border:1px solid #ef4444;border-radius:8px;padding:12px 16px;margin:16px 0">
            <h4 style="color:#ef4444;margin:0 0 8px">Failures ({len(failures)})</h4>
            <ul style="padding-left:16px;color:#fca5a5;font-size:0.85rem">{error_items}</ul>
        </div>
        """

    return f"""
    <section>
        <h2>Stripe Lifecycle Validation</h2>
        <div class="kpi-row">
            <div class="kpi"><div class="kpi-value" style="color:{summary_color}">{passed}/{total}</div><div class="kpi-label">Checks Passed</div></div>
            <div class="kpi"><div class="kpi-value">{synced_products}/{expected_synced_products}</div><div class="kpi-label">Synced Products</div></div>
            <div class="kpi"><div class="kpi-value">{synced_variants}/{expected_synced_variants}</div><div class="kpi-label">Synced Variants</div></div>
            <div class="kpi"><div class="kpi-value">{synced_coupons}/{expected_synced_coupons}</div><div class="kpi-label">Synced Coupons</div></div>
            <div class="kpi"><div class="kpi-value" style="color:{'#22c55e' if cust_pass else '#ef4444'}">{'OK' if cust_pass else 'MISSING'}</div><div class="kpi-label">Stripe Customer</div></div>
        </div>

        {admin_card}

        <details open><summary>Products Stripe Sync ({len(products)})</summary>
        <table>
            <thead><tr><th>Name</th><th>Type</th><th>Status</th><th>Stripe Product ID</th><th>Sync</th><th>Expected</th><th>Result</th></tr></thead>
            <tbody>{prod_rows}</tbody>
        </table>
        </details>

        <details><summary>Variants Stripe Sync ({len(variants)})</summary>
        <table>
            <thead><tr><th>Product</th><th>Variant</th><th>Price</th><th>Stripe Price ID</th><th>Recurring</th><th>Sync</th><th>Expected</th><th>Result</th></tr></thead>
            <tbody>{var_rows}</tbody>
        </table>
        </details>

        <details><summary>Coupons Stripe Sync ({len(coupons)})</summary>
        <table>
            <thead><tr><th>Code</th><th>Type</th><th>Value</th><th>Duration</th><th>Stripe Coupon ID</th><th>Promo Code ID</th><th>Sync</th><th>Expected</th><th>Result</th></tr></thead>
            <tbody>{coup_rows}</tbody>
        </table>
        </details>

        {errors_html}
    </section>
    """


def _build_analytics_detail(phase2_result: dict) -> str:
    """Section E: Analytics & Tracking Detail."""
    detail = phase2_result.get("analytics_detail", {})
    if not detail:
        return ""

    events = detail.get("events", [])
    page_views = detail.get("page_views", [])
    sessions = detail.get("sessions", [])
    templates = detail.get("email_templates", [])
    consent = detail.get("consent_records", [])
    cookies = detail.get("cookie_preferences", [])

    # Events table
    event_rows = ""
    for e in events:
        data_html = _json_html(e.get("event_data", {}))
        ts = e.get("created_at", "")[:19] if e.get("created_at") else ""
        event_rows += (
            f"<tr>"
            f'<td><code>{_esc(e.get("event_type", ""))}</code></td>'
            f"<td>{ts}</td>"
            f'<td><details><summary style="font-size:0.75rem">payload</summary>{data_html}</details></td>'
            f"</tr>\n"
        )

    # Page views table
    pv_rows = ""
    for pv in page_views:
        ts = pv.get("created_at", "")[:19] if pv.get("created_at") else ""
        dur = pv.get("duration_ms") or 0
        pv_rows += (
            f"<tr>"
            f'<td><code>{_esc(pv.get("path", ""))}</code></td>'
            f'<td>{_esc(pv.get("referrer", "") or "")}</td>'
            f"<td>{dur}ms</td>"
            f"<td>{ts}</td>"
            f"</tr>\n"
        )

    # Sessions table
    session_rows = ""
    for s in sessions:
        started = s.get("started_at", "")[:19] if s.get("started_at") else ""
        ended = s.get("ended_at", "")[:19] if s.get("ended_at") else "active"
        session_rows += (
            f"<tr>"
            f'<td><code style="font-size:0.75rem">{_esc(s.get("session_id", ""))[:12]}...</code></td>'
            f"<td>{started}</td>"
            f"<td>{ended}</td>"
            f'<td>{s.get("page_count", 0)}</td>'
            f"</tr>\n"
        )

    # Templates table
    template_rows = ""
    for t in templates:
        builtin_badge = (
            '<span style="color:#22c55e;font-size:0.7rem;background:#22c55e20;padding:1px 4px;border-radius:3px">built-in</span>'
            if t.get("is_builtin")
            else '<span style="color:#a3a3a3;font-size:0.7rem">custom</span>'
        )
        template_rows += (
            f"<tr>"
            f'<td><code>{_esc(t.get("name", ""))}</code></td>'
            f'<td>{_esc(t.get("display_name", ""))}</td>'
            f'<td>{_esc(t.get("category", ""))}</td>'
            f'<td>{_esc(t.get("subject", "") or "")}</td>'
            f"<td>{builtin_badge}</td>"
            f"</tr>\n"
        )

    # Consent / Cookies
    consent_rows = ""
    for c in consent:
        granted_color = "#22c55e" if c.get("granted") else "#ef4444"
        consent_rows += (
            f"<tr>"
            f'<td>{_esc(c.get("email", ""))}</td>'
            f'<td>{_esc(c.get("consent_type", ""))}</td>'
            f'<td style="color:{granted_color}">{"granted" if c.get("granted") else "denied"}</td>'
            f"</tr>\n"
        )
    cookie_rows = ""
    for ck in cookies:

        def _yn(v):
            return (
                '<span style="color:#22c55e">Y</span>'
                if v
                else '<span style="color:#ef4444">N</span>'
            )

        cookie_rows += (
            f"<tr>"
            f'<td>{_esc(ck.get("email", ""))}</td>'
            f'<td>{_yn(ck.get("necessary"))}</td>'
            f'<td>{_yn(ck.get("analytics"))}</td>'
            f'<td>{_yn(ck.get("marketing"))}</td>'
            f'<td>{_yn(ck.get("preferences"))}</td>'
            f"</tr>\n"
        )

    return f"""
    <section>
        <h2>Analytics &amp; Tracking Detail</h2>

        <details open><summary>Admin Events ({len(events)})</summary>
        <table>
            <thead><tr><th>Event Type</th><th>Timestamp</th><th>Data</th></tr></thead>
            <tbody>{event_rows}</tbody>
        </table>
        </details>

        <details><summary>Page Views ({len(page_views)})</summary>
        <table>
            <thead><tr><th>Path</th><th>Referrer</th><th>Duration</th><th>Timestamp</th></tr></thead>
            <tbody>{pv_rows}</tbody>
        </table>
        </details>

        <details><summary>Sessions ({len(sessions)})</summary>
        <table>
            <thead><tr><th>Session ID</th><th>Started</th><th>Ended</th><th>Pages</th></tr></thead>
            <tbody>{session_rows}</tbody>
        </table>
        </details>

        <details open><summary>Email Templates ({len(templates)})</summary>
        <table>
            <thead><tr><th>Name</th><th>Display Name</th><th>Category</th><th>Subject</th><th>Type</th></tr></thead>
            <tbody>{template_rows}</tbody>
        </table>
        </details>

        <details><summary>GDPR Consent ({len(consent)} records, {len(cookies)} cookie prefs)</summary>
        <h4 style="margin:8px 0 4px;font-size:0.85rem;color:#a3a3a3">Consent Records</h4>
        <table>
            <thead><tr><th>Email</th><th>Type</th><th>Status</th></tr></thead>
            <tbody>{consent_rows if consent_rows else '<tr><td colspan="3" style="color:#525252">No consent records</td></tr>'}</tbody>
        </table>
        <h4 style="margin:8px 0 4px;font-size:0.85rem;color:#a3a3a3">Cookie Preferences</h4>
        <table>
            <thead><tr><th>Email</th><th>Necessary</th><th>Analytics</th><th>Marketing</th><th>Preferences</th></tr></thead>
            <tbody>{cookie_rows if cookie_rows else '<tr><td colspan="5" style="color:#525252">No cookie preferences</td></tr>'}</tbody>
        </table>
        </details>
    </section>
    """


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
    """Generate a self-contained HTML report with extreme detail."""
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

    # ── New enhanced sections ──
    admin_card_html = ""
    db_delta_html = ""
    api_log_html = ""
    catalog_detail_html = ""
    stripe_detail_html = ""
    analytics_detail_html = ""

    if phase2_result:
        admin_card_html = _build_admin_card(phase2_result)
        db_delta_html = _build_db_delta(phase2_result)
        api_log_html = _build_api_log(phase2_result)
        catalog_detail_html = _build_catalog_detail(phase2_result)
        stripe_detail_html = _build_stripe_detail(phase2_result)
        analytics_detail_html = _build_analytics_detail(phase2_result)

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
<title>Simulation Report &mdash; {ts}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0a0a0a;color:#e5e5e5;padding:24px;max-width:1400px;margin:0 auto}}
h1{{font-size:1.5rem;margin-bottom:4px}}
h2{{font-size:1.2rem;margin:24px 0 12px;border-bottom:1px solid #333;padding-bottom:6px}}
h3{{font-size:1rem;margin:16px 0 8px}}
h4{{font-size:0.9rem;color:#a3a3a3;margin:8px 0 4px}}
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
section{{margin-bottom:32px}}
/* API log styles */
.api-tabs{{display:flex;gap:4px;flex-wrap:wrap;margin:8px 0 12px;padding:4px;background:#111;border-radius:8px}}
.api-tab{{background:transparent;border:1px solid transparent;color:#a3a3a3;padding:6px 12px;border-radius:6px;cursor:pointer;font-size:0.8rem;font-family:inherit;transition:all 0.15s}}
.api-tab:hover{{color:#e5e5e5;background:#1a1a1a}}
.api-tab.tab-active{{background:#1a1a2e;color:#60a5fa;border-color:#60a5fa40}}
.tab-badge{{display:inline-block;background:#333;padding:1px 6px;border-radius:10px;font-size:0.7rem;margin-left:4px}}
.api-entry{{margin:2px 0;border:1px solid #1a1a1a;border-radius:6px;overflow:hidden}}
.api-entry summary{{padding:8px 12px;font-size:0.82rem;display:flex;align-items:center;gap:8px;background:#111}}
.api-entry summary:hover{{background:#1a1a1a}}
.api-entry[open] summary{{border-bottom:1px solid #262626}}
.api-method{{font-weight:700;min-width:52px;font-family:monospace}}
.api-path{{flex:1;font-family:monospace;color:#e5e5e5;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.api-status{{font-weight:700;font-family:monospace}}
.api-dur{{color:#525252;font-size:0.75rem;min-width:50px;text-align:right}}
.api-body{{padding:8px 12px;background:#0a0a0a}}
.api-section{{margin:4px 0}}
.api-section h4{{font-size:0.78rem;color:#525252;margin:4px 0;text-transform:uppercase}}
.json-block{{background:#0d0d0d;border:1px solid #1a1a1a;border-radius:4px;padding:8px;font-size:0.78rem;overflow-x:auto;max-height:300px;overflow-y:auto;line-height:1.4}}
.jk{{color:#60a5fa}} /* json key */
.js{{color:#22c55e}} /* json string */
.jn{{color:#facc15}} /* json number */
.jb{{color:#c084fc}} /* json bool/null */
/* Nav */
.nav-bar{{position:sticky;top:0;z-index:100;background:#0a0a0aee;backdrop-filter:blur(8px);border-bottom:1px solid #262626;padding:8px 0;margin:-24px -24px 24px;padding:8px 24px;display:flex;gap:12px;flex-wrap:wrap}}
.nav-bar a{{color:#a3a3a3;text-decoration:none;font-size:0.8rem;padding:4px 8px;border-radius:4px;transition:all 0.15s}}
.nav-bar a:hover{{color:#60a5fa;background:#1a1a2e}}
</style>
</head>
<body>

<div class="nav-bar">
    <a href="#phases">Phases</a>
    {"<a href='#admin'>Admin</a>" if admin_card_html else ""}
    {"<a href='#dbdelta'>DB Delta</a>" if db_delta_html else ""}
    {"<a href='#apilog'>API Log</a>" if api_log_html else ""}
    {"<a href='#catalog'>Catalog</a>" if catalog_detail_html else ""}
    {"<a href='#stripe'>Stripe Sync</a>" if stripe_detail_html else ""}
    {"<a href='#analytics'>Analytics</a>" if analytics_detail_html else ""}
    {("<a href='#users'>Users</a>" if users_html else "")}
    <a href="#checks">Checks</a>
</div>

<div class="header">
    <div>
        <h1>Simulation Report</h1>
        <div class="meta">{ts} &middot; {_esc(target)} &middot; {user_count} users &middot; {duration_secs:.0f}s</div>
    </div>
    <div class="status">{status_text}</div>
</div>

<section id="phases">
    <h2>Phases</h2>
    <table>
        <thead><tr><th></th><th>Phase</th><th>Result</th><th>Duration</th></tr></thead>
        <tbody>{phase_rows}</tbody>
    </table>
</section>

<div id="admin">{admin_card_html}</div>
<div id="dbdelta">{db_delta_html}</div>
<div id="apilog">{api_log_html}</div>
<div id="catalog">{catalog_detail_html}</div>
<div id="stripe">{stripe_detail_html}</div>
<div id="analytics">{analytics_detail_html}</div>
<div id="users">{users_html}</div>

<section id="checks">
    <h2>Verification Checks ({passed}/{total})</h2>
    {check_sections if check_sections else '<p style="color:#a3a3a3">No checks were run in this session.</p>'}
</section>

<script>
// Tab switching for API log
document.querySelectorAll('.api-tab').forEach(btn => {{
    btn.addEventListener('click', () => {{
        const group = btn.dataset.tab;
        // Update active tab
        btn.closest('.api-tabs').querySelectorAll('.api-tab').forEach(b => b.classList.remove('tab-active'));
        btn.classList.add('tab-active');
        // Filter entries
        btn.closest('section').querySelectorAll('.api-entry').forEach(entry => {{
            if (group === 'all' || entry.dataset.group === group) {{
                entry.style.display = '';
            }} else {{
                entry.style.display = 'none';
            }}
        }});
    }});
}});
</script>

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
