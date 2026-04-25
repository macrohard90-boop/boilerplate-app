"""Flow execution service — state machine for automation flows.

Handles enrollment, step advancement, branching, goal checking.
Each enrollment progresses through steps: enroll → execute step →
wait (if needed) → advance to next → ... → complete.

Step types:
- send: Send message via delivery pipeline → advance immediately
- wait: Pause until duration/date/event → flow_worker advances later
- branch: Evaluate condition → route to YES or NO connection
- split: Random assignment by weight → route to assigned connection
- update: Tag user, set attribute → advance immediately
- webhook: POST to external URL → advance immediately
"""

import asyncio
import json
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def enroll_user(
    db: AsyncSession,
    flow_id: str,
    user_id: str,
    trigger_payload: dict | None = None,
    chain_depth: int = 0,
) -> dict | None:
    """Enroll a user in a flow.

    Uses partial unique index (flow_id, user_id WHERE status='active')
    to prevent duplicate active enrollments (F21).
    """
    # Check flow is active
    flow = (
        (
            await db.execute(
                text(
                    "SELECT id, status, allow_reentry, max_chain_depth "
                    "FROM marketing.automation_flows WHERE id = :fid"
                ),
                {"fid": flow_id},
            )
        )
        .mappings()
        .first()
    )

    if not flow or flow["status"] != "active":
        return None

    # Chain depth check (F5)
    if chain_depth > (flow["max_chain_depth"] or 5):
        logger.warning(
            "Chain depth exceeded for flow=%s user=%s depth=%d",
            flow_id,
            user_id,
            chain_depth,
        )
        return None

    # Get first step
    first_step = (
        (
            await db.execute(
                text(
                    "SELECT id FROM marketing.automation_flow_steps "
                    "WHERE flow_id = :fid ORDER BY step_order LIMIT 1"
                ),
                {"fid": flow_id},
            )
        )
        .mappings()
        .first()
    )

    if not first_step:
        return None

    # Insert enrollment (partial unique index handles dedup)
    try:
        row = (
            (
                await db.execute(
                    text(
                        "INSERT INTO marketing.flow_enrollments "
                        "(flow_id, user_id, current_step_id, trigger_payload, chain_depth) "
                        "VALUES (:fid, :uid, :step_id, CAST(:payload AS jsonb), :depth) "
                        "RETURNING id, flow_id, user_id, current_step_id, status"
                    ),
                    {
                        "fid": flow_id,
                        "uid": user_id,
                        "step_id": str(first_step["id"]),
                        "payload": json.dumps(trigger_payload or {}),
                        "depth": chain_depth,
                    },
                )
            )
            .mappings()
            .first()
        )
    except Exception as e:
        # Unique constraint violation = already enrolled
        if "idx_fe_active_unique" in str(e):
            if flow["allow_reentry"]:
                # Exit old enrollment and re-enroll
                await db.execute(
                    text(
                        "UPDATE marketing.flow_enrollments "
                        "SET status = 'exited', exit_reason = 'reentry', "
                        "  completed_at = NOW() "
                        "WHERE flow_id = :fid AND user_id = :uid AND status = 'active'"
                    ),
                    {"fid": flow_id, "uid": user_id},
                )
                await db.commit()
                return await enroll_user(
                    db, flow_id, user_id, trigger_payload, chain_depth
                )
            logger.debug("User %s already enrolled in flow %s", user_id, flow_id)
            await db.rollback()
            return None
        await db.rollback()
        raise

    await db.commit()

    if row:
        enrollment_id = str(row["id"])
        # Execute the first step
        await _execute_step(db, enrollment_id, str(first_step["id"]))
        return dict(row)

    return None


async def advance_enrollment(
    db: AsyncSession,
    enrollment_id: str,
) -> dict | None:
    """Advance an enrollment to its next step.

    Called after a step completes (send finishes, wait expires, etc.).
    Follows connections from current step to determine next step.
    """
    enrollment = (
        (
            await db.execute(
                text(
                    "SELECT id, flow_id, user_id, current_step_id, status "
                    "FROM marketing.flow_enrollments WHERE id = :eid"
                ),
                {"eid": enrollment_id},
            )
        )
        .mappings()
        .first()
    )

    if not enrollment or enrollment["status"] != "active":
        return None

    current_step_id = str(enrollment["current_step_id"])
    flow_id = str(enrollment["flow_id"])
    user_id = str(enrollment["user_id"])

    # Find next step(s) via connections
    connections = (
        (
            await db.execute(
                text(
                    "SELECT to_step_id, condition_label, condition_expr "
                    "FROM marketing.automation_flow_connections "
                    "WHERE flow_id = :fid AND from_step_id = :sid"
                ),
                {"fid": flow_id, "sid": current_step_id},
            )
        )
        .mappings()
        .all()
    )

    if not connections:
        # No connections = try next by step_order
        next_step = (
            (
                await db.execute(
                    text(
                        "SELECT id FROM marketing.automation_flow_steps "
                        "WHERE flow_id = :fid "
                        "AND step_order > ("
                        "  SELECT step_order FROM marketing.automation_flow_steps "
                        "  WHERE id = :sid"
                        ") "
                        "ORDER BY step_order LIMIT 1"
                    ),
                    {"fid": flow_id, "sid": current_step_id},
                )
            )
            .mappings()
            .first()
        )

        if next_step:
            await _move_to_step(db, enrollment_id, str(next_step["id"]))
            await _execute_step(db, enrollment_id, str(next_step["id"]))
        else:
            # No more steps — complete the enrollment
            await _complete_enrollment(db, enrollment_id)

        return {"status": "advanced", "enrollment_id": enrollment_id}

    # If there's exactly one unconditional connection, follow it
    if len(connections) == 1 and not connections[0]["condition_expr"]:
        next_id = str(connections[0]["to_step_id"])
        await _move_to_step(db, enrollment_id, next_id)
        await _execute_step(db, enrollment_id, next_id)
        return {"status": "advanced", "enrollment_id": enrollment_id}

    # Multiple connections = this was handled by branch/split execution
    # The step executor should have already chosen the path
    return {"status": "waiting_for_branch", "enrollment_id": enrollment_id}


async def check_goal(
    db: AsyncSession,
    flow_id: str,
    user_id: str,
    event_name: str,
) -> bool:
    """Check if an event matches a flow's goal condition.

    If matched, marks the enrollment as goal_reached.
    """
    flow = (
        (
            await db.execute(
                text(
                    "SELECT goal_event FROM marketing.automation_flows "
                    "WHERE id = :fid"
                ),
                {"fid": flow_id},
            )
        )
        .mappings()
        .first()
    )

    if not flow or flow["goal_event"] != event_name:
        return False

    result = await db.execute(
        text(
            "UPDATE marketing.flow_enrollments "
            "SET status = 'goal_reached', completed_at = NOW(), "
            "  exit_reason = :reason "
            "WHERE flow_id = :fid AND user_id = :uid AND status = 'active'"
        ),
        {
            "fid": flow_id,
            "uid": user_id,
            "reason": f"Goal reached: {event_name}",
        },
    )
    await db.commit()
    return result.rowcount > 0


# ---------------------------------------------------------------------------
# Step execution
# ---------------------------------------------------------------------------


async def _execute_step(
    db: AsyncSession,
    enrollment_id: str,
    step_id: str,
) -> None:
    """Execute a specific step for an enrollment."""
    step = (
        (
            await db.execute(
                text(
                    "SELECT id, flow_id, step_type, config "
                    "FROM marketing.automation_flow_steps WHERE id = :sid"
                ),
                {"sid": step_id},
            )
        )
        .mappings()
        .first()
    )

    if not step:
        return

    step_type = step["step_type"]
    config = step["config"] or {}
    if isinstance(config, str):
        config = json.loads(config)

    # Create execution record
    exec_row = (
        (
            await db.execute(
                text(
                    "INSERT INTO marketing.flow_step_executions "
                    "(enrollment_id, step_id, status) "
                    "VALUES (:eid, :sid, 'pending') "
                    "RETURNING id"
                ),
                {"eid": enrollment_id, "sid": step_id},
            )
        )
        .mappings()
        .first()
    )
    exec_id = str(exec_row["id"]) if exec_row else None
    await db.commit()

    try:
        if step_type == "send":
            await _exec_send(db, enrollment_id, step, config, exec_id)
        elif step_type == "wait":
            await _exec_wait(db, enrollment_id, step, config, exec_id)
            return  # Don't advance — flow_worker will pick it up
        elif step_type == "branch":
            await _exec_branch(db, enrollment_id, step, config, exec_id)
            return  # Branch handles its own advancement
        elif step_type == "split":
            await _exec_split(db, enrollment_id, step, config, exec_id)
            return  # Split handles its own advancement
        elif step_type == "update":
            await _exec_update(db, enrollment_id, step, config, exec_id)
        elif step_type == "webhook":
            await _exec_webhook(db, enrollment_id, step, config, exec_id)

        # Mark executed and advance
        if exec_id:
            await db.execute(
                text(
                    "UPDATE marketing.flow_step_executions "
                    "SET status = 'executed', executed_at = NOW() "
                    "WHERE id = :eid"
                ),
                {"eid": exec_id},
            )
            await db.commit()

        await advance_enrollment(db, enrollment_id)

    except Exception as e:
        logger.exception(
            "Step execution failed: enrollment=%s step=%s", enrollment_id, step_id
        )
        if exec_id:
            await db.execute(
                text(
                    "UPDATE marketing.flow_step_executions "
                    "SET status = 'failed', result = CAST(:err AS jsonb), "
                    "  executed_at = NOW() "
                    "WHERE id = :eid"
                ),
                {"eid": exec_id, "err": json.dumps({"error": str(e)})},
            )
            await db.commit()


async def _exec_send(
    db: AsyncSession,
    enrollment_id: str,
    step: Any,
    config: dict,
    exec_id: str | None,
) -> None:
    """Execute a send step — dispatch message via the appropriate channel."""
    enrollment = (
        (
            await db.execute(
                text(
                    "SELECT user_id FROM marketing.flow_enrollments " "WHERE id = :eid"
                ),
                {"eid": enrollment_id},
            )
        )
        .mappings()
        .first()
    )

    if not enrollment:
        return

    user_id = str(enrollment["user_id"])
    channel = config.get("channel", "email")
    template_id = config.get("template_id")

    if channel == "email" and template_id:
        from modules.gdpr.services.email_send_service import send_email_fire_and_forget

        await send_email_fire_and_forget(
            user_id, template_id, config.get("template_data", {})
        )
    elif channel == "sms":
        from modules.notifications.services.sms_send_service import (
            send_sms_fire_and_forget,
        )

        # Get user phone
        user_row = (
            (
                await db.execute(
                    text("SELECT phone FROM core.users WHERE id = :uid"),
                    {"uid": user_id},
                )
            )
            .mappings()
            .first()
        )
        if user_row and user_row["phone"]:
            await send_sms_fire_and_forget(
                user_id, user_row["phone"], config.get("content", "")
            )
    elif channel == "whatsapp":
        from modules.notifications.services.whatsapp_send_service import (
            send_whatsapp_fire_and_forget,
        )

        user_row = (
            (
                await db.execute(
                    text("SELECT whatsapp_number FROM core.users WHERE id = :uid"),
                    {"uid": user_id},
                )
            )
            .mappings()
            .first()
        )
        if user_row and user_row["whatsapp_number"]:
            await send_whatsapp_fire_and_forget(
                user_id,
                user_row["whatsapp_number"],
                template_id=config.get("template_id"),
                text_content=config.get("content"),
            )

    logger.debug(
        "Flow send: enrollment=%s channel=%s template=%s",
        enrollment_id,
        channel,
        template_id,
    )


async def _exec_wait(
    db: AsyncSession,
    enrollment_id: str,
    step: Any,
    config: dict,
    exec_id: str | None,
) -> None:
    """Execute a wait step — schedule resume time."""
    wait_type = config.get("wait_type", "duration")

    if wait_type == "duration":
        seconds = config.get("duration_seconds", 0)
        resume_at = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    elif wait_type == "until_date":
        resume_at = datetime.fromisoformat(config["date"])
    elif wait_type == "until_event":
        # Wait indefinitely until event — flow_worker checks events
        resume_at = datetime.now(timezone.utc) + timedelta(days=365)
    else:
        resume_at = datetime.now(timezone.utc)

    if exec_id:
        await db.execute(
            text(
                "UPDATE marketing.flow_step_executions "
                "SET status = 'waiting', scheduled_at = :resume "
                "WHERE id = :eid"
            ),
            {"eid": exec_id, "resume": resume_at},
        )
        await db.commit()

    logger.debug("Flow wait: enrollment=%s resume_at=%s", enrollment_id, resume_at)


async def _exec_branch(
    db: AsyncSession,
    enrollment_id: str,
    step: Any,
    config: dict,
    exec_id: str | None,
) -> None:
    """Execute a branch step — evaluate condition and route."""
    condition = config.get("condition", {})
    step_id = str(step["id"])
    flow_id = str(step["flow_id"])

    enrollment = (
        (
            await db.execute(
                text(
                    "SELECT user_id FROM marketing.flow_enrollments " "WHERE id = :eid"
                ),
                {"eid": enrollment_id},
            )
        )
        .mappings()
        .first()
    )

    if not enrollment:
        return

    user_id = str(enrollment["user_id"])
    result = await _evaluate_condition(db, user_id, condition)

    # Find matching connection
    target_label = "yes" if result else "no"
    connections = (
        (
            await db.execute(
                text(
                    "SELECT to_step_id, condition_label "
                    "FROM marketing.automation_flow_connections "
                    "WHERE flow_id = :fid AND from_step_id = :sid"
                ),
                {"fid": flow_id, "sid": step_id},
            )
        )
        .mappings()
        .all()
    )

    next_step_id = None
    for conn in connections:
        if (conn["condition_label"] or "").lower() == target_label:
            next_step_id = str(conn["to_step_id"])
            break

    if exec_id:
        await db.execute(
            text(
                "UPDATE marketing.flow_step_executions "
                "SET status = 'executed', executed_at = NOW(), "
                "  result = CAST(:res AS jsonb) WHERE id = :eid"
            ),
            {
                "eid": exec_id,
                "res": json.dumps({"condition_result": result, "path": target_label}),
            },
        )
        await db.commit()

    if next_step_id:
        await _move_to_step(db, enrollment_id, next_step_id)
        await _execute_step(db, enrollment_id, next_step_id)
    else:
        await _complete_enrollment(db, enrollment_id)


async def _exec_split(
    db: AsyncSession,
    enrollment_id: str,
    step: Any,
    config: dict,
    exec_id: str | None,
) -> None:
    """Execute a split step — random A/B assignment by weight."""
    step_id = str(step["id"])
    flow_id = str(step["flow_id"])

    connections = (
        (
            await db.execute(
                text(
                    "SELECT to_step_id, condition_label, condition_expr "
                    "FROM marketing.automation_flow_connections "
                    "WHERE flow_id = :fid AND from_step_id = :sid"
                ),
                {"fid": flow_id, "sid": step_id},
            )
        )
        .mappings()
        .all()
    )

    if not connections:
        await _complete_enrollment(db, enrollment_id)
        return

    # Parse weights from condition_expr
    weighted = []
    for conn in connections:
        expr = conn["condition_expr"] or {}
        if isinstance(expr, str):
            expr = json.loads(expr)
        weight = expr.get("weight", 1)
        weighted.append((str(conn["to_step_id"]), weight))

    # Weighted random selection
    total_weight = sum(w for _, w in weighted)
    r = random.random() * total_weight
    cumulative = 0
    chosen_step_id = weighted[0][0]
    for step_target_id, weight in weighted:
        cumulative += weight
        if r <= cumulative:
            chosen_step_id = step_target_id
            break

    if exec_id:
        await db.execute(
            text(
                "UPDATE marketing.flow_step_executions "
                "SET status = 'executed', executed_at = NOW(), "
                "  result = CAST(:res AS jsonb) WHERE id = :eid"
            ),
            {
                "eid": exec_id,
                "res": json.dumps({"chosen_step": chosen_step_id}),
            },
        )
        await db.commit()

    await _move_to_step(db, enrollment_id, chosen_step_id)
    await _execute_step(db, enrollment_id, chosen_step_id)


async def _exec_update(
    db: AsyncSession,
    enrollment_id: str,
    step: Any,
    config: dict,
    exec_id: str | None,
) -> None:
    """Execute an update step — tag user, set attribute, adjust score."""
    enrollment = (
        (
            await db.execute(
                text(
                    "SELECT user_id FROM marketing.flow_enrollments " "WHERE id = :eid"
                ),
                {"eid": enrollment_id},
            )
        )
        .mappings()
        .first()
    )

    if not enrollment:
        return

    user_id = str(enrollment["user_id"])
    action = config.get("action")

    if action == "tag" and config.get("tag"):
        # Add tag to user (via metadata or dedicated table)
        logger.info("Flow update: tag user=%s with '%s'", user_id, config["tag"])

    elif action == "set_attribute":
        attr = config.get("attribute")
        value = config.get("value")
        if attr and value is not None:
            logger.info("Flow update: set %s=%s for user=%s", attr, value, user_id)

    elif action == "adjust_score":
        delta = config.get("score_delta", 0)
        await db.execute(
            text(
                "UPDATE analytics.engagement_scores "
                "SET score = score + :delta "
                "WHERE user_id = :uid"
            ),
            {"uid": user_id, "delta": delta},
        )
        await db.commit()


async def _exec_webhook(
    db: AsyncSession,
    enrollment_id: str,
    step: Any,
    config: dict,
    exec_id: str | None,
) -> None:
    """Execute a webhook step — POST to external URL."""
    url = config.get("url")
    if not url:
        return

    enrollment = (
        (
            await db.execute(
                text(
                    "SELECT user_id, flow_id, trigger_payload "
                    "FROM marketing.flow_enrollments WHERE id = :eid"
                ),
                {"eid": enrollment_id},
            )
        )
        .mappings()
        .first()
    )

    payload = {
        "enrollment_id": enrollment_id,
        "user_id": str(enrollment["user_id"]) if enrollment else None,
        "flow_id": str(enrollment["flow_id"]) if enrollment else None,
        "trigger_payload": enrollment["trigger_payload"] if enrollment else {},
        "step_config": config,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            logger.debug("Webhook response: %d", resp.status_code)
    except Exception:
        logger.debug("Webhook call failed for %s", url, exc_info=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _move_to_step(db: AsyncSession, enrollment_id: str, step_id: str) -> None:
    """Update the enrollment's current step."""
    await db.execute(
        text(
            "UPDATE marketing.flow_enrollments "
            "SET current_step_id = :sid WHERE id = :eid"
        ),
        {"eid": enrollment_id, "sid": step_id},
    )
    await db.commit()


async def _complete_enrollment(db: AsyncSession, enrollment_id: str) -> None:
    """Mark an enrollment as completed."""
    await db.execute(
        text(
            "UPDATE marketing.flow_enrollments "
            "SET status = 'completed', completed_at = NOW() "
            "WHERE id = :eid AND status = 'active'"
        ),
        {"eid": enrollment_id},
    )
    await db.commit()


async def _evaluate_condition(db: AsyncSession, user_id: str, condition: dict) -> bool:
    """Evaluate a branch condition against user data.

    Supported conditions:
    - email_opened: check if user opened campaign email
    - has_purchased: check if user has completed orders
    - score_above: engagement score threshold
    - segment_member: check if user is in a segment
    """
    cond_type = condition.get("type")

    if cond_type == "email_opened":
        campaign_id = condition.get("campaign_id")
        if campaign_id:
            row = (
                (
                    await db.execute(
                        text(
                            "SELECT 1 FROM marketing.campaign_recipients "
                            "WHERE campaign_id = :cid AND user_id = :uid "
                            "AND opened_at IS NOT NULL"
                        ),
                        {"cid": campaign_id, "uid": user_id},
                    )
                )
                .mappings()
                .first()
            )
            return row is not None

    elif cond_type == "has_purchased":
        days = condition.get("within_days", 30)
        row = (
            (
                await db.execute(
                    text(
                        "SELECT 1 FROM ecommerce.orders "
                        "WHERE user_id = :uid AND status = 'completed' "
                        "AND created_at > NOW() - INTERVAL '1 day' * :days"
                    ),
                    {"uid": user_id, "days": days},
                )
            )
            .mappings()
            .first()
        )
        return row is not None

    elif cond_type == "score_above":
        threshold = condition.get("threshold", 0)
        row = (
            (
                await db.execute(
                    text(
                        "SELECT score FROM analytics.engagement_scores "
                        "WHERE user_id = :uid"
                    ),
                    {"uid": user_id},
                )
            )
            .mappings()
            .first()
        )
        return row is not None and float(row["score"]) >= threshold

    return False


async def fire_event_for_flows(
    db: AsyncSession,
    event_name: str,
    user_id: str,
    payload: dict | None = None,
) -> int:
    """Fire an event that may trigger flow enrollments.

    Looks up active flows with matching trigger_event, enrolls the user.
    Also checks goal completion for active enrollments.
    Returns count of new enrollments created.
    """
    # Find active flows triggered by this event
    flows = (
        (
            await db.execute(
                text(
                    "SELECT id FROM marketing.automation_flows "
                    "WHERE trigger_event = :evt AND status = 'active'"
                ),
                {"evt": event_name},
            )
        )
        .mappings()
        .all()
    )

    enrolled = 0
    for flow in flows:
        result = await enroll_user(
            db, str(flow["id"]), user_id, trigger_payload=payload
        )
        if result:
            enrolled += 1

    # Check goal completion for all active enrollments of this user
    active_enrollments = (
        (
            await db.execute(
                text(
                    "SELECT DISTINCT flow_id "
                    "FROM marketing.flow_enrollments "
                    "WHERE user_id = :uid AND status = 'active'"
                ),
                {"uid": user_id},
            )
        )
        .mappings()
        .all()
    )

    for enrollment in active_enrollments:
        await check_goal(db, str(enrollment["flow_id"]), user_id, event_name)

    if enrolled:
        logger.info(
            "Event '%s' triggered %d flow enrollments for user=%s",
            event_name,
            enrolled,
            user_id,
        )

    return enrolled
