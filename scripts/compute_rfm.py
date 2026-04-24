#!/usr/bin/env python3
"""
Compute RFM segments for all customers with orders.

Usage:
    python scripts/compute_rfm.py

Reads DATABASE_URL from .env, computes Recency/Frequency/Monetary scores,
assigns segment labels, and updates ecommerce.customer_metrics.
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg2

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_env() -> dict[str, str]:
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
    env = load_env()
    url = os.environ.get("DATABASE_URL", env.get("DATABASE_URL", ""))
    if not url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)
    return url.replace("postgresql+asyncpg://", "postgresql://")


# RFM scoring thresholds (days for recency, counts for frequency, cents for monetary)
# These are generous for small datasets
RECENCY_THRESHOLDS = [7, 30, 90, 180]     # days: <=7=5, <=30=4, <=90=3, <=180=2, >180=1
FREQUENCY_THRESHOLDS = [1, 3, 5, 10]       # orders: >=10=5, >=5=4, >=3=3, >=1=2, 0=1
MONETARY_THRESHOLDS = [2000, 5000, 15000, 50000]  # cents: >=500$=5, >=150$=4, >=50$=3, >=20$=2, <20$=1

# Segment mapping: (R_score, F_score, M_score) ranges -> segment label
SEGMENT_RULES = [
    # Champions: high across all three
    (lambda r, f, m: r >= 4 and f >= 4 and m >= 4, "champion"),
    # Loyal: good frequency and monetary, decent recency
    (lambda r, f, m: f >= 3 and m >= 3 and r >= 3, "loyal"),
    # Potential Loyalist: recent with decent frequency
    (lambda r, f, m: r >= 4 and f >= 2, "potential_loyalist"),
    # New: very recent, low frequency
    (lambda r, f, m: r >= 4 and f <= 2, "new"),
    # At Risk: was good but recency dropping
    (lambda r, f, m: r <= 2 and f >= 3, "at_risk"),
    # Hibernating: low recency, some history
    (lambda r, f, m: r <= 2 and f >= 1, "hibernating"),
    # Lost: no recent activity, low everything
    (lambda r, f, m: r <= 1, "lost"),
]


def score_recency(days: int) -> int:
    for i, threshold in enumerate(RECENCY_THRESHOLDS):
        if days <= threshold:
            return 5 - i
    return 1


def score_frequency(count: int) -> int:
    for i, threshold in enumerate(reversed(FREQUENCY_THRESHOLDS)):
        if count >= threshold:
            return 5 - i
    return 1


def score_monetary(cents: int) -> int:
    for i, threshold in enumerate(reversed(MONETARY_THRESHOLDS)):
        if cents >= threshold:
            return 5 - i
    return 1


def assign_segment(r: int, f: int, m: int) -> str:
    for rule_fn, label in SEGMENT_RULES:
        if rule_fn(r, f, m):
            return label
    return "lost"


def main():
    url = get_db_url()
    conn = psycopg2.connect(url)
    cur = conn.cursor()

    # Fetch all customers with orders
    cur.execute(
        "SELECT user_id, order_count, total_spent, last_purchase_at "
        "FROM ecommerce.customer_metrics "
        "WHERE order_count > 0 AND last_purchase_at IS NOT NULL"
    )
    rows = cur.fetchall()

    if not rows:
        print("No customers with orders found. Nothing to compute.")
        conn.close()
        return

    now = datetime.now(timezone.utc)
    updates = []

    for user_id, order_count, total_spent, last_purchase_at in rows:
        days_since = (now - last_purchase_at).days
        r = score_recency(days_since)
        f = score_frequency(order_count)
        m = score_monetary(total_spent)
        segment = assign_segment(r, f, m)
        updates.append((segment, user_id))
        print(f"  {user_id}: R={r} F={f} M={m} -> {segment} (days={days_since}, orders={order_count}, spent=${total_spent/100:.2f})")

    # Batch update
    cur.executemany(
        "UPDATE ecommerce.customer_metrics "
        "SET rfm_segment = %s, last_calculated_at = NOW() "
        "WHERE user_id = %s",
        updates,
    )
    conn.commit()
    print(f"\nUpdated {len(updates)} customer RFM segments.")

    conn.close()


if __name__ == "__main__":
    main()
