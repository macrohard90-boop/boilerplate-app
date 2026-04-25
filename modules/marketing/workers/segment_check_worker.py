"""Segment membership check worker — fires segment.entered events.

Every 15 minutes, checks for users who have entered segments that
trigger automation flows. Tracks previous membership in Redis to
detect new entries.
"""

import json
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_REDIS_PREFIX = "seg_members:"


async def check_segment_membership(db: AsyncSession) -> dict:
    """Check all segments that trigger flows, fire events for new members.

    Finds segments referenced by active flows with trigger_event='segment.entered',
    computes current membership, compares against cached membership in Redis,
    and fires events for newly entered users.
    """
    # Find segments referenced by active flows
    flow_rows = (
        (
            await db.execute(
                text(
                    "SELECT id, trigger_conditions "
                    "FROM marketing.automation_flows "
                    "WHERE trigger_event = 'segment.entered' "
                    "AND status = 'active'"
                )
            )
        )
        .mappings()
        .all()
    )

    if not flow_rows:
        return {"flows_checked": 0, "events_fired": 0}

    from backend.core.redis import get_redis
    from modules.marketing.services.segment_service import resolve_segment_user_ids

    redis = await get_redis()
    total_events = 0

    for flow in flow_rows:
        conditions = flow["trigger_conditions"] or {}
        if isinstance(conditions, str):
            conditions = json.loads(conditions)

        segment_id = conditions.get("segment_id")
        if not segment_id:
            continue

        # Get current segment members
        try:
            current_members = await resolve_segment_user_ids(db, segment_id)
            current_set = set(current_members)
        except Exception:
            logger.debug("Failed to resolve segment %s", segment_id, exc_info=True)
            continue

        # Get previous members from Redis
        cache_key = f"{_REDIS_PREFIX}{segment_id}"
        previous_raw = await redis.get(cache_key)
        previous_set = set(json.loads(previous_raw)) if previous_raw else set()

        # Find new members
        new_members = current_set - previous_set

        if new_members:
            from modules.marketing.services.flow_execution_service import (
                fire_event_for_flows,
            )

            for user_id in new_members:
                try:
                    await fire_event_for_flows(
                        db,
                        "segment.entered",
                        user_id,
                        {"segment_id": segment_id},
                    )
                    total_events += 1
                except Exception:
                    logger.debug(
                        "Failed to fire segment.entered for user=%s",
                        user_id,
                        exc_info=True,
                    )

        # Cache current membership (TTL = 1 hour)
        await redis.setex(cache_key, 3600, json.dumps(list(current_set)))

    logger.info(
        "Segment check: %d flows checked, %d events fired",
        len(flow_rows),
        total_events,
    )

    return {"flows_checked": len(flow_rows), "events_fired": total_events}
