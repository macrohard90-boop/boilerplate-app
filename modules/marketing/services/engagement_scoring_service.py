"""Engagement scoring service — computes per-user engagement scores.

Formula:
    score = Σ(event_weight × recency_decay × frequency_boost)

Weights:
    email_opened=2, clicked=5, wa_read=3, page_viewed=1,
    product_viewed=2, add_to_cart=8, purchase=20

Decay:
    weight × 2^(-days_since_event / 14)   (half-life = 14 days)

Frequency Boost:
    if 3+ actions in last 7 days → 1.5× multiplier

Velocity:
    (score_now - score_14_days_ago) / 14
    Positive = increasing engagement, negative = declining
"""

import logging
import math
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Event weights for scoring
_EVENT_WEIGHTS = {
    "email_opened": 2,
    "email_clicked": 5,
    "whatsapp_read": 3,
    "page_view": 1,
    "product_viewed": 2,
    "add_to_cart": 8,
    "purchase": 20,
}

# Half-life in days for recency decay
_HALF_LIFE_DAYS = 14

# Frequency boost threshold and multiplier
_FREQ_THRESHOLD = 3  # 3+ actions in 7 days
_FREQ_MULTIPLIER = 1.5


async def compute_user_score(db: AsyncSession, user_id: str) -> dict:
    """Compute engagement score for a single user.

    Aggregates events from multiple sources:
    - campaign_recipients (opens, clicks)
    - analytics.page_views (site visits)
    - analytics.events (product_viewed, add_to_cart)
    - ecommerce.orders (purchases)
    """
    now = datetime.now(timezone.utc)

    # Collect scored events: list of (weight, days_ago)
    events: list[tuple[float, float]] = []
    recent_count = 0  # actions in last 7 days

    # 1. Email opens and clicks from campaign_recipients
    rows = (
        (
            await db.execute(
                text(
                    "SELECT status, opened_at, clicked_at "
                    "FROM marketing.campaign_recipients "
                    "WHERE user_id = :uid "
                    "AND (opened_at IS NOT NULL OR clicked_at IS NOT NULL) "
                    "AND created_at > NOW() - INTERVAL '90 days'"
                ),
                {"uid": user_id},
            )
        )
        .mappings()
        .all()
    )

    last_email_open = None
    last_email_click = None

    for row in rows:
        if row["opened_at"]:
            days = (
                now - row["opened_at"].replace(tzinfo=timezone.utc)
            ).total_seconds() / 86400
            events.append((_EVENT_WEIGHTS["email_opened"], days))
            if days <= 7:
                recent_count += 1
            if last_email_open is None or row["opened_at"] > last_email_open:
                last_email_open = row["opened_at"]

        if row["clicked_at"]:
            days = (
                now - row["clicked_at"].replace(tzinfo=timezone.utc)
            ).total_seconds() / 86400
            events.append((_EVENT_WEIGHTS["email_clicked"], days))
            if days <= 7:
                recent_count += 1
            if last_email_click is None or row["clicked_at"] > last_email_click:
                last_email_click = row["clicked_at"]

    # 2. Page views (last 90 days)
    pv_row = (
        (
            await db.execute(
                text(
                    "SELECT COUNT(*) as cnt, MAX(created_at) as last_at "
                    "FROM analytics.page_views "
                    "WHERE user_id = :uid "
                    "AND created_at > NOW() - INTERVAL '90 days'"
                ),
                {"uid": user_id},
            )
        )
        .mappings()
        .first()
    )

    last_site_visit = None
    if pv_row and pv_row["cnt"]:
        # Sample: use count × average recency
        pv_recent = (
            (
                await db.execute(
                    text(
                        "SELECT created_at FROM analytics.page_views "
                        "WHERE user_id = :uid "
                        "AND created_at > NOW() - INTERVAL '90 days' "
                        "ORDER BY created_at DESC LIMIT 50"
                    ),
                    {"uid": user_id},
                )
            )
            .mappings()
            .all()
        )
        for pvr in pv_recent:
            days = (
                now - pvr["created_at"].replace(tzinfo=timezone.utc)
            ).total_seconds() / 86400
            events.append((_EVENT_WEIGHTS["page_view"], days))
            if days <= 7:
                recent_count += 1
        if pv_row["last_at"]:
            last_site_visit = pv_row["last_at"]

    # 3. Product viewed + add_to_cart events
    ev_rows = (
        (
            await db.execute(
                text(
                    "SELECT event_type, created_at "
                    "FROM analytics.events "
                    "WHERE user_id = :uid "
                    "AND event_type IN ('product_viewed', 'add_to_cart') "
                    "AND created_at > NOW() - INTERVAL '90 days' "
                    "ORDER BY created_at DESC LIMIT 100"
                ),
                {"uid": user_id},
            )
        )
        .mappings()
        .all()
    )

    for ev in ev_rows:
        weight = _EVENT_WEIGHTS.get(ev["event_type"], 1)
        days = (
            now - ev["created_at"].replace(tzinfo=timezone.utc)
        ).total_seconds() / 86400
        events.append((weight, days))
        if days <= 7:
            recent_count += 1

    # 4. Purchases
    order_rows = (
        (
            await db.execute(
                text(
                    "SELECT created_at FROM ecommerce.orders "
                    "WHERE user_id = :uid AND status = 'completed' "
                    "AND created_at > NOW() - INTERVAL '90 days' "
                    "ORDER BY created_at DESC LIMIT 20"
                ),
                {"uid": user_id},
            )
        )
        .mappings()
        .all()
    )

    last_purchase = None
    for o in order_rows:
        days = (
            now - o["created_at"].replace(tzinfo=timezone.utc)
        ).total_seconds() / 86400
        events.append((_EVENT_WEIGHTS["purchase"], days))
        if days <= 7:
            recent_count += 1
        if last_purchase is None or o["created_at"] > last_purchase:
            last_purchase = o["created_at"]

    # 5. WhatsApp reads from campaign_recipients
    wa_rows = (
        (
            await db.execute(
                text(
                    "SELECT opened_at FROM marketing.campaign_recipients "
                    "WHERE user_id = :uid AND channel = 'whatsapp' "
                    "AND opened_at IS NOT NULL "
                    "AND created_at > NOW() - INTERVAL '90 days'"
                ),
                {"uid": user_id},
            )
        )
        .mappings()
        .all()
    )

    for wa in wa_rows:
        days = (
            now - wa["opened_at"].replace(tzinfo=timezone.utc)
        ).total_seconds() / 86400
        events.append((_EVENT_WEIGHTS["whatsapp_read"], days))
        if days <= 7:
            recent_count += 1

    # Compute score with recency decay
    score = 0.0
    for weight, days_ago in events:
        decay = math.pow(2, -days_ago / _HALF_LIFE_DAYS)
        score += weight * decay

    # Apply frequency boost
    if recent_count >= _FREQ_THRESHOLD:
        score *= _FREQ_MULTIPLIER

    # Compute velocity (approximate — compare current score vs hypothetical 14-day-ago score)
    # We use events older than 14 days to estimate past score
    past_score = 0.0
    for weight, days_ago in events:
        if days_ago >= 14:
            past_decay = math.pow(2, -(days_ago - 14) / _HALF_LIFE_DAYS)
            past_score += weight * past_decay

    velocity = (score - past_score) / 14 if events else 0

    return {
        "user_id": user_id,
        "score": round(score, 2),
        "velocity": round(velocity, 2),
        "last_email_open": last_email_open,
        "last_email_click": last_email_click,
        "last_site_visit": last_site_visit,
        "last_purchase": last_purchase,
    }


async def upsert_engagement_score(db: AsyncSession, user_id: str) -> dict:
    """Compute and store engagement score for a user."""
    result = await compute_user_score(db, user_id)

    await db.execute(
        text(
            "INSERT INTO analytics.engagement_scores "
            "(user_id, score, velocity, last_email_open, last_email_click, "
            " last_site_visit, last_purchase, computed_at) "
            "VALUES (:uid, :score, :vel, :leo, :lec, :lsv, :lp, NOW()) "
            "ON CONFLICT (user_id) DO UPDATE SET "
            " score = EXCLUDED.score, "
            " velocity = EXCLUDED.velocity, "
            " last_email_open = EXCLUDED.last_email_open, "
            " last_email_click = EXCLUDED.last_email_click, "
            " last_site_visit = EXCLUDED.last_site_visit, "
            " last_purchase = EXCLUDED.last_purchase, "
            " computed_at = NOW()"
        ),
        {
            "uid": user_id,
            "score": result["score"],
            "vel": result["velocity"],
            "leo": result["last_email_open"],
            "lec": result["last_email_click"],
            "lsv": result["last_site_visit"],
            "lp": result["last_purchase"],
        },
    )
    await db.commit()

    return result
