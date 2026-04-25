"""Automation flow API routes — CRUD, lifecycle, monitoring, analytics."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.dependencies import require_role

router = APIRouter(prefix="/flows", tags=["marketing-flows"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class FlowCreate(BaseModel):
    name: str
    trigger_event: str
    description: str | None = None
    trigger_conditions: dict | None = None
    goal_event: str | None = None
    goal_window_days: int = 7
    allow_reentry: bool = False


class FlowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    trigger_event: str | None = None
    trigger_conditions: dict | None = None
    goal_event: str | None = None
    goal_window_days: int | None = None
    allow_reentry: bool | None = None
    exit_tag: str | None = None


class StepCreate(BaseModel):
    step_type: str
    config: dict
    step_order: int | None = None


class StepUpdate(BaseModel):
    config: dict | None = None
    step_order: int | None = None


class ConnectionCreate(BaseModel):
    from_step_id: str
    to_step_id: str
    condition_label: str | None = None
    condition_expr: dict | None = None


# ---------------------------------------------------------------------------
# Flow CRUD
# ---------------------------------------------------------------------------


@router.post("")
async def create_flow(
    body: FlowCreate,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    from modules.marketing.services.flow_builder_service import (
        create_flow as _create,
    )

    return await _create(
        db,
        name=body.name,
        trigger_event=body.trigger_event,
        description=body.description,
        trigger_conditions=body.trigger_conditions,
        goal_event=body.goal_event,
        goal_window_days=body.goal_window_days,
        allow_reentry=body.allow_reentry,
        created_by=user["user_id"],
    )


@router.get("")
async def list_flows(
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    from modules.marketing.services.flow_builder_service import (
        list_flows as _list,
    )

    return await _list(db, status=status, limit=limit, offset=offset)


@router.get("/{flow_id}")
async def get_flow(
    flow_id: str,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    from modules.marketing.services.flow_builder_service import (
        get_flow as _get,
    )

    result = await _get(db, flow_id)
    if not result:
        raise HTTPException(status_code=404, detail="Flow not found")
    return result


@router.put("/{flow_id}")
async def update_flow(
    flow_id: str,
    body: FlowUpdate,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    from modules.marketing.services.flow_builder_service import (
        update_flow as _update,
    )

    result = await _update(db, flow_id, **body.model_dump(exclude_none=True))
    if not result:
        raise HTTPException(status_code=404, detail="Flow not found")
    return result


@router.delete("/{flow_id}")
async def delete_flow(
    flow_id: str,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    from modules.marketing.services.flow_builder_service import (
        delete_flow as _delete,
    )

    if not await _delete(db, flow_id):
        raise HTTPException(
            status_code=400,
            detail="Only draft flows can be deleted",
        )
    return {"status": "deleted", "flow_id": flow_id}


# ---------------------------------------------------------------------------
# Flow lifecycle
# ---------------------------------------------------------------------------


@router.post("/{flow_id}/activate")
async def activate_flow(
    flow_id: str,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    from modules.marketing.services.flow_builder_service import (
        activate_flow as _activate,
    )

    try:
        return await _activate(db, flow_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{flow_id}/pause")
async def pause_flow(
    flow_id: str,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    from modules.marketing.services.flow_builder_service import (
        pause_flow as _pause,
    )

    return await _pause(db, flow_id)


@router.post("/{flow_id}/archive")
async def archive_flow(
    flow_id: str,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    from modules.marketing.services.flow_builder_service import (
        archive_flow as _archive,
    )

    return await _archive(db, flow_id)


# ---------------------------------------------------------------------------
# Step CRUD
# ---------------------------------------------------------------------------


@router.post("/{flow_id}/steps")
async def add_step(
    flow_id: str,
    body: StepCreate,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    from modules.marketing.services.flow_builder_service import (
        add_step as _add,
    )

    return await _add(
        db, flow_id, body.step_type, body.config, step_order=body.step_order
    )


@router.put("/steps/{step_id}")
async def update_step(
    step_id: str,
    body: StepUpdate,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    from modules.marketing.services.flow_builder_service import (
        update_step as _update,
    )

    result = await _update(db, step_id, config=body.config, step_order=body.step_order)
    if not result:
        raise HTTPException(status_code=404, detail="Step not found")
    return result


@router.delete("/steps/{step_id}")
async def delete_step(
    step_id: str,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    from modules.marketing.services.flow_builder_service import (
        delete_step as _delete,
    )

    if not await _delete(db, step_id):
        raise HTTPException(status_code=404, detail="Step not found")
    return {"status": "deleted"}


# ---------------------------------------------------------------------------
# Connection CRUD
# ---------------------------------------------------------------------------


@router.post("/{flow_id}/connections")
async def add_connection(
    flow_id: str,
    body: ConnectionCreate,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    from modules.marketing.services.flow_builder_service import (
        add_connection as _add,
    )

    return await _add(
        db,
        flow_id,
        body.from_step_id,
        body.to_step_id,
        condition_label=body.condition_label,
        condition_expr=body.condition_expr,
    )


@router.delete("/connections/{connection_id}")
async def delete_connection(
    connection_id: str,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    from modules.marketing.services.flow_builder_service import (
        delete_connection as _delete,
    )

    if not await _delete(db, connection_id):
        raise HTTPException(status_code=404, detail="Connection not found")
    return {"status": "deleted"}


# ---------------------------------------------------------------------------
# Flow analytics
# ---------------------------------------------------------------------------


@router.get("/{flow_id}/stats")
async def flow_stats(
    flow_id: str,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    from modules.marketing.services.flow_analytics_service import get_flow_stats

    return await get_flow_stats(db, flow_id)


@router.get("/{flow_id}/step-performance")
async def flow_step_performance(
    flow_id: str,
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    from modules.marketing.services.flow_analytics_service import (
        get_step_performance,
    )

    return await get_step_performance(db, flow_id)


@router.get("/{flow_id}/enrollment-timeline")
async def flow_enrollment_timeline(
    flow_id: str,
    days: int = Query(30, ge=1, le=365),
    user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> Any:
    from modules.marketing.services.flow_analytics_service import (
        get_enrollment_timeline,
    )

    return await get_enrollment_timeline(db, flow_id, days=days)
