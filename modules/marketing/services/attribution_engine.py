"""Multi-touch attribution engine — 5 models computed at report time.

All models operate on the touch_sequence JSONB stored in campaign_attributions.
Each model distributes a conversion's value across the campaigns in the
touch sequence, returning per-campaign credit.

Models:
- last_click:   100% to last touch
- first_touch:  100% to first touch
- linear:       Equal split across all touches
- time_decay:   Exponential decay favoring recent touches (7-day half-life)
- u_shaped:     40% first + 40% last + 20% spread across middle touches
"""

import math
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Half-life for time_decay model (in seconds)
_HALF_LIFE_SECONDS = 7 * 24 * 3600  # 7 days


def apply_model(
    model: str,
    touches: list[dict],
    conversion_value: float,
) -> list[dict]:
    """Apply an attribution model to a touch sequence.

    Args:
        model: One of last_click, first_touch, linear, time_decay, u_shaped.
        touches: List of touch dicts with at least {campaign_id, ts}.
        conversion_value: Total value to distribute.

    Returns:
        List of {campaign_id, credit, fraction} dicts.
    """
    if not touches:
        return []

    if model == "last_click":
        return _last_click(touches, conversion_value)
    elif model == "first_touch":
        return _first_touch(touches, conversion_value)
    elif model == "linear":
        return _linear(touches, conversion_value)
    elif model == "time_decay":
        return _time_decay(touches, conversion_value)
    elif model == "u_shaped":
        return _u_shaped(touches, conversion_value)
    else:
        # Default to last_click
        return _last_click(touches, conversion_value)


def _last_click(touches: list[dict], value: float) -> list[dict]:
    """100% credit to the last touch before conversion."""
    last = touches[-1]
    return [{"campaign_id": last["campaign_id"], "credit": value, "fraction": 1.0}]


def _first_touch(touches: list[dict], value: float) -> list[dict]:
    """100% credit to the first touch in the sequence."""
    first = touches[0]
    return [{"campaign_id": first["campaign_id"], "credit": value, "fraction": 1.0}]


def _linear(touches: list[dict], value: float) -> list[dict]:
    """Equal credit across all touches."""
    n = len(touches)
    per_touch = value / n
    fraction = 1.0 / n

    # Aggregate by campaign_id
    credits: dict[str, float] = {}
    counts: dict[str, int] = {}
    for t in touches:
        cid = t["campaign_id"]
        credits[cid] = credits.get(cid, 0) + per_touch
        counts[cid] = counts.get(cid, 0) + 1

    return [
        {
            "campaign_id": cid,
            "credit": round(credit, 2),
            "fraction": round(counts[cid] * fraction, 4),
        }
        for cid, credit in credits.items()
    ]


def _time_decay(touches: list[dict], value: float) -> list[dict]:
    """Exponential decay — more credit to recent touches.

    Uses 7-day half-life. The most recent touch gets the most credit,
    older touches get exponentially less.
    """
    if len(touches) == 1:
        return _last_click(touches, value)

    # Parse timestamps
    parsed = []
    for t in touches:
        try:
            ts = datetime.fromisoformat(t["ts"])
            parsed.append((t["campaign_id"], ts))
        except (KeyError, ValueError, TypeError):
            continue

    if not parsed:
        return _last_click(touches, value)

    # Reference point: latest touch
    latest = max(ts for _, ts in parsed)

    # Compute weights using exponential decay
    weights = []
    for cid, ts in parsed:
        seconds_ago = (latest - ts).total_seconds()
        weight = math.pow(2, -seconds_ago / _HALF_LIFE_SECONDS)
        weights.append((cid, weight))

    total_weight = sum(w for _, w in weights)
    if total_weight == 0:
        return _linear(touches, value)

    # Aggregate by campaign_id
    credits: dict[str, float] = {}
    fractions: dict[str, float] = {}
    for cid, weight in weights:
        fraction = weight / total_weight
        credits[cid] = credits.get(cid, 0) + value * fraction
        fractions[cid] = fractions.get(cid, 0) + fraction

    return [
        {
            "campaign_id": cid,
            "credit": round(credit, 2),
            "fraction": round(fractions[cid], 4),
        }
        for cid, credit in credits.items()
    ]


def _u_shaped(touches: list[dict], value: float) -> list[dict]:
    """Position-based: 40% first + 40% last + 20% distributed across middle.

    If only 1 touch: 100% to that touch.
    If only 2 touches: 50/50.
    """
    n = len(touches)

    if n == 1:
        return _first_touch(touches, value)

    if n == 2:
        return [
            {
                "campaign_id": touches[0]["campaign_id"],
                "credit": round(value * 0.5, 2),
                "fraction": 0.5,
            },
            {
                "campaign_id": touches[1]["campaign_id"],
                "credit": round(value * 0.5, 2),
                "fraction": 0.5,
            },
        ]

    first_credit = value * 0.4
    last_credit = value * 0.4
    middle_total = value * 0.2
    middle_count = n - 2
    per_middle = middle_total / middle_count if middle_count > 0 else 0

    # Aggregate by campaign_id
    credits: dict[str, float] = {}
    fractions: dict[str, float] = {}

    # First touch
    cid = touches[0]["campaign_id"]
    credits[cid] = credits.get(cid, 0) + first_credit
    fractions[cid] = fractions.get(cid, 0) + 0.4

    # Middle touches
    for t in touches[1:-1]:
        cid = t["campaign_id"]
        credits[cid] = credits.get(cid, 0) + per_middle
        fractions[cid] = fractions.get(cid, 0) + (0.2 / middle_count)

    # Last touch
    cid = touches[-1]["campaign_id"]
    credits[cid] = credits.get(cid, 0) + last_credit
    fractions[cid] = fractions.get(cid, 0) + 0.4

    return [
        {
            "campaign_id": cid,
            "credit": round(credit, 2),
            "fraction": round(fractions[cid], 4),
        }
        for cid, credit in credits.items()
    ]


async def get_campaign_attribution_report(
    db: AsyncSession,
    campaign_id: str,
    model: str = "last_click",
) -> dict[str, Any]:
    """Generate an attribution report for a campaign across all conversions.

    Queries all campaign_attributions rows that include this campaign_id
    in their touch_sequence, then applies the specified model to distribute
    credit.
    """
    rows = (
        (
            await db.execute(
                text(
                    "SELECT id, conversion_event, conversion_value, "
                    "  conversion_currency, touch_sequence, converted_at "
                    "FROM marketing.campaign_attributions "
                    "WHERE campaign_id = :cid AND converted = true"
                ),
                {"cid": campaign_id},
            )
        )
        .mappings()
        .all()
    )

    total_conversions = len(rows)
    total_revenue = 0.0
    attributed_revenue = 0.0

    for row in rows:
        value = float(row["conversion_value"] or 0)
        total_revenue += value

        touches = row["touch_sequence"] or []
        if isinstance(touches, str):
            import json

            touches = json.loads(touches)

        credits = apply_model(model, touches, value)
        for c in credits:
            if c["campaign_id"] == campaign_id:
                attributed_revenue += c["credit"]

    return {
        "campaign_id": campaign_id,
        "model": model,
        "total_conversions": total_conversions,
        "total_revenue": round(total_revenue, 2),
        "attributed_revenue": round(attributed_revenue, 2),
    }
