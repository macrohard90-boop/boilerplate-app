"""Flow builder service — CRUD, validation, cycle detection.

Manages automation_flows, automation_flow_steps, and
automation_flow_connections. Validates flow structure on activation:
- No cycles in the step graph
- Chain depth limit (max 5 by default)
- All connections reference valid steps
"""

import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_MAX_CHAIN_DEPTH = 5


# ---------------------------------------------------------------------------
# Flow CRUD
# ---------------------------------------------------------------------------


async def create_flow(
    db: AsyncSession,
    name: str,
    trigger_event: str,
    *,
    description: str | None = None,
    trigger_conditions: dict | None = None,
    goal_event: str | None = None,
    goal_window_days: int = 7,
    allow_reentry: bool = False,
    created_by: str | None = None,
) -> dict:
    """Create a new automation flow in draft status."""
    row = (
        (
            await db.execute(
                text(
                    "INSERT INTO marketing.automation_flows "
                    "(name, description, trigger_event, trigger_conditions, "
                    " goal_event, goal_window_days, allow_reentry, created_by) "
                    "VALUES (:name, :desc, :trigger, CAST(:cond AS jsonb), "
                    " :goal, :goal_days, :reentry, :created_by) "
                    "RETURNING id, name, status, trigger_event, created_at"
                ),
                {
                    "name": name,
                    "desc": description,
                    "trigger": trigger_event,
                    "cond": json.dumps(trigger_conditions or {}),
                    "goal": goal_event,
                    "goal_days": goal_window_days,
                    "reentry": allow_reentry,
                    "created_by": created_by,
                },
            )
        )
        .mappings()
        .first()
    )

    await db.commit()
    return dict(row) if row else {}


async def get_flow(db: AsyncSession, flow_id: str) -> dict | None:
    """Get a flow with its steps and connections."""
    flow = (
        (
            await db.execute(
                text(
                    "SELECT id, name, description, trigger_event, trigger_conditions, "
                    "  status, goal_event, goal_window_days, allow_reentry, "
                    "  max_chain_depth, exit_tag, created_by, created_at, updated_at "
                    "FROM marketing.automation_flows WHERE id = :fid"
                ),
                {"fid": flow_id},
            )
        )
        .mappings()
        .first()
    )

    if not flow:
        return None

    steps = (
        (
            await db.execute(
                text(
                    "SELECT id, step_type, step_order, config, created_at "
                    "FROM marketing.automation_flow_steps "
                    "WHERE flow_id = :fid ORDER BY step_order"
                ),
                {"fid": flow_id},
            )
        )
        .mappings()
        .all()
    )

    connections = (
        (
            await db.execute(
                text(
                    "SELECT id, from_step_id, to_step_id, condition_label, condition_expr "
                    "FROM marketing.automation_flow_connections "
                    "WHERE flow_id = :fid"
                ),
                {"fid": flow_id},
            )
        )
        .mappings()
        .all()
    )

    result = dict(flow)
    result["steps"] = [_serialize_step(s) for s in steps]
    result["connections"] = [
        {
            "id": str(c["id"]),
            "from_step_id": str(c["from_step_id"]),
            "to_step_id": str(c["to_step_id"]),
            "condition_label": c["condition_label"],
            "condition_expr": c["condition_expr"],
        }
        for c in connections
    ]
    return _serialize_flow(result)


async def list_flows(
    db: AsyncSession,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """List automation flows with optional status filter."""
    params: dict[str, Any] = {"lim": limit, "off": offset}
    where = "1=1"
    if status:
        where = "status = :status"
        params["status"] = status

    rows = (
        (
            await db.execute(
                text(
                    f"SELECT id, name, trigger_event, status, "
                    f"  created_at, updated_at "
                    f"FROM marketing.automation_flows "
                    f"WHERE {where} "
                    f"ORDER BY created_at DESC LIMIT :lim OFFSET :off"
                ),
                params,
            )
        )
        .mappings()
        .all()
    )

    return [_serialize_flow(dict(r)) for r in rows]


async def update_flow(
    db: AsyncSession,
    flow_id: str,
    **updates: Any,
) -> dict | None:
    """Update a flow's properties. Only works for draft/paused flows."""
    allowed = {
        "name",
        "description",
        "trigger_event",
        "trigger_conditions",
        "goal_event",
        "goal_window_days",
        "allow_reentry",
        "exit_tag",
    }
    set_parts = []
    params: dict[str, Any] = {"fid": flow_id}

    for key, value in updates.items():
        if key in allowed and value is not None:
            if key == "trigger_conditions":
                set_parts.append(f"{key} = CAST(:{key} AS jsonb)")
                params[key] = json.dumps(value)
            else:
                set_parts.append(f"{key} = :{key}")
                params[key] = value

    if not set_parts:
        return await get_flow(db, flow_id)

    await db.execute(
        text(
            f"UPDATE marketing.automation_flows "
            f"SET {', '.join(set_parts)} "
            f"WHERE id = :fid AND status IN ('draft', 'paused')"
        ),
        params,
    )
    await db.commit()
    return await get_flow(db, flow_id)


async def delete_flow(db: AsyncSession, flow_id: str) -> bool:
    """Delete a draft flow and all its steps/connections (CASCADE)."""
    result = await db.execute(
        text(
            "DELETE FROM marketing.automation_flows "
            "WHERE id = :fid AND status = 'draft'"
        ),
        {"fid": flow_id},
    )
    await db.commit()
    return result.rowcount > 0


# ---------------------------------------------------------------------------
# Step CRUD
# ---------------------------------------------------------------------------


async def add_step(
    db: AsyncSession,
    flow_id: str,
    step_type: str,
    config: dict,
    step_order: int | None = None,
) -> dict:
    """Add a step to a flow."""
    if step_order is None:
        max_row = (
            (
                await db.execute(
                    text(
                        "SELECT COALESCE(MAX(step_order), -1) + 1 as next_order "
                        "FROM marketing.automation_flow_steps WHERE flow_id = :fid"
                    ),
                    {"fid": flow_id},
                )
            )
            .mappings()
            .first()
        )
        step_order = max_row["next_order"] if max_row else 0

    row = (
        (
            await db.execute(
                text(
                    "INSERT INTO marketing.automation_flow_steps "
                    "(flow_id, step_type, step_order, config) "
                    "VALUES (:fid, :stype, :sorder, CAST(:config AS jsonb)) "
                    "RETURNING id, flow_id, step_type, step_order, config, created_at"
                ),
                {
                    "fid": flow_id,
                    "stype": step_type,
                    "sorder": step_order,
                    "config": json.dumps(config),
                },
            )
        )
        .mappings()
        .first()
    )

    await db.commit()
    return _serialize_step(dict(row)) if row else {}


async def update_step(
    db: AsyncSession,
    step_id: str,
    config: dict | None = None,
    step_order: int | None = None,
) -> dict | None:
    """Update a step's config or order."""
    set_parts = []
    params: dict[str, Any] = {"sid": step_id}

    if config is not None:
        set_parts.append("config = CAST(:config AS jsonb)")
        params["config"] = json.dumps(config)
    if step_order is not None:
        set_parts.append("step_order = :sorder")
        params["sorder"] = step_order

    if not set_parts:
        return None

    row = (
        (
            await db.execute(
                text(
                    f"UPDATE marketing.automation_flow_steps "
                    f"SET {', '.join(set_parts)} "
                    f"WHERE id = :sid "
                    f"RETURNING id, flow_id, step_type, step_order, config, created_at"
                ),
                params,
            )
        )
        .mappings()
        .first()
    )

    await db.commit()
    return _serialize_step(dict(row)) if row else None


async def delete_step(db: AsyncSession, step_id: str) -> bool:
    """Delete a step (also removes connections via CASCADE)."""
    result = await db.execute(
        text("DELETE FROM marketing.automation_flow_steps WHERE id = :sid"),
        {"sid": step_id},
    )
    await db.commit()
    return result.rowcount > 0


# ---------------------------------------------------------------------------
# Connection CRUD
# ---------------------------------------------------------------------------


async def add_connection(
    db: AsyncSession,
    flow_id: str,
    from_step_id: str,
    to_step_id: str,
    condition_label: str | None = None,
    condition_expr: dict | None = None,
) -> dict:
    """Add a connection between two steps."""
    row = (
        (
            await db.execute(
                text(
                    "INSERT INTO marketing.automation_flow_connections "
                    "(flow_id, from_step_id, to_step_id, condition_label, condition_expr) "
                    "VALUES (:fid, :from_id, :to_id, :label, CAST(:expr AS jsonb)) "
                    "ON CONFLICT (flow_id, from_step_id, to_step_id) DO UPDATE SET "
                    "  condition_label = EXCLUDED.condition_label, "
                    "  condition_expr = EXCLUDED.condition_expr "
                    "RETURNING id, from_step_id, to_step_id, condition_label"
                ),
                {
                    "fid": flow_id,
                    "from_id": from_step_id,
                    "to_id": to_step_id,
                    "label": condition_label,
                    "expr": json.dumps(condition_expr) if condition_expr else None,
                },
            )
        )
        .mappings()
        .first()
    )

    await db.commit()
    return dict(row) if row else {}


async def delete_connection(db: AsyncSession, connection_id: str) -> bool:
    """Delete a connection."""
    result = await db.execute(
        text("DELETE FROM marketing.automation_flow_connections WHERE id = :cid"),
        {"cid": connection_id},
    )
    await db.commit()
    return result.rowcount > 0


# ---------------------------------------------------------------------------
# Activation + Validation
# ---------------------------------------------------------------------------


async def activate_flow(db: AsyncSession, flow_id: str) -> dict:
    """Validate and activate a flow.

    Checks:
    1. Flow has at least one step
    2. No cycles in the step graph
    3. Chain depth is within limit
    4. All connections reference valid steps in this flow
    """
    flow = await get_flow(db, flow_id)
    if not flow:
        raise ValueError("Flow not found")

    if flow["status"] not in ("draft", "paused"):
        raise ValueError(f"Cannot activate flow in status: {flow['status']}")

    steps = flow.get("steps", [])
    if not steps:
        raise ValueError("Flow must have at least one step")

    connections = flow.get("connections", [])

    # Build adjacency list for cycle detection
    step_ids = {s["id"] for s in steps}
    adj: dict[str, list[str]] = {sid: [] for sid in step_ids}

    for conn in connections:
        from_id = conn["from_step_id"]
        to_id = conn["to_step_id"]
        if from_id not in step_ids or to_id not in step_ids:
            raise ValueError(f"Connection references invalid step: {from_id} → {to_id}")
        adj[from_id].append(to_id)

    # DFS cycle detection
    if _has_cycle(adj, step_ids):
        raise ValueError("Flow contains a cycle — cannot activate")

    # Check chain depth
    max_depth = _compute_max_depth(adj, step_ids)
    chain_limit = flow.get("max_chain_depth", _MAX_CHAIN_DEPTH)
    if max_depth > chain_limit:
        raise ValueError(f"Flow depth ({max_depth}) exceeds limit ({chain_limit})")

    # Activate
    await db.execute(
        text(
            "UPDATE marketing.automation_flows " "SET status = 'active' WHERE id = :fid"
        ),
        {"fid": flow_id},
    )
    await db.commit()

    return {"status": "activated", "flow_id": flow_id, "max_depth": max_depth}


async def pause_flow(db: AsyncSession, flow_id: str) -> dict:
    """Pause an active flow."""
    await db.execute(
        text(
            "UPDATE marketing.automation_flows "
            "SET status = 'paused' WHERE id = :fid AND status = 'active'"
        ),
        {"fid": flow_id},
    )
    await db.commit()
    return {"status": "paused", "flow_id": flow_id}


async def archive_flow(db: AsyncSession, flow_id: str) -> dict:
    """Archive a flow (stops all enrollments)."""
    await db.execute(
        text(
            "UPDATE marketing.automation_flows "
            "SET status = 'archived' WHERE id = :fid"
        ),
        {"fid": flow_id},
    )
    # Exit all active enrollments
    await db.execute(
        text(
            "UPDATE marketing.flow_enrollments "
            "SET status = 'exited', exit_reason = 'flow_archived', "
            "  completed_at = NOW() "
            "WHERE flow_id = :fid AND status = 'active'"
        ),
        {"fid": flow_id},
    )
    await db.commit()
    return {"status": "archived", "flow_id": flow_id}


# ---------------------------------------------------------------------------
# Graph utilities
# ---------------------------------------------------------------------------


def _has_cycle(adj: dict[str, list[str]], nodes: set[str]) -> bool:
    """DFS-based cycle detection."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in nodes}

    def dfs(node: str) -> bool:
        color[node] = GRAY
        for neighbor in adj.get(node, []):
            if color[neighbor] == GRAY:
                return True  # Back edge = cycle
            if color[neighbor] == WHITE and dfs(neighbor):
                return True
        color[node] = BLACK
        return False

    for node in nodes:
        if color[node] == WHITE:
            if dfs(node):
                return True
    return False


def _compute_max_depth(adj: dict[str, list[str]], nodes: set[str]) -> int:
    """Compute the longest path (max depth) in the DAG."""
    memo: dict[str, int] = {}

    def depth(node: str) -> int:
        if node in memo:
            return memo[node]
        children = adj.get(node, [])
        if not children:
            memo[node] = 1
        else:
            memo[node] = 1 + max(depth(c) for c in children)
        return memo[node]

    if not nodes:
        return 0
    return max(depth(n) for n in nodes)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def _serialize_flow(row: dict) -> dict:
    """Serialize a flow row for API response."""
    result: dict[str, Any] = {}
    for key, value in row.items():
        if key == "id" or key.endswith("_id"):
            result[key] = str(value) if value else None
        elif key in ("created_at", "updated_at"):
            result[key] = value.isoformat() if value else None
        elif key == "trigger_conditions" and isinstance(value, str):
            result[key] = json.loads(value)
        else:
            result[key] = value
    return result


def _serialize_step(row: dict) -> dict:
    """Serialize a step row for API response."""
    result: dict[str, Any] = {}
    for key, value in row.items():
        if key == "id" or key.endswith("_id"):
            result[key] = str(value) if value else None
        elif key == "created_at":
            result[key] = value.isoformat() if value else None
        elif key == "config" and isinstance(value, str):
            result[key] = json.loads(value)
        else:
            result[key] = value
    return result
