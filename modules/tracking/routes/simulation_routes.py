"""Admin endpoints for viewing simulation results."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.dependencies import require_admin

router = APIRouter(prefix="/tracking/admin/simulation", tags=["simulation"])


@router.get("/runs")
async def list_simulation_runs(
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List past simulation runs (most recent first)."""
    result = await db.execute(
        text(
            "SELECT id, started_at, completed_at, target_url, user_count, "
            "status, sections_run, summary "
            "FROM analytics.simulation_runs "
            "ORDER BY created_at DESC LIMIT 50"
        )
    )
    rows = result.fetchall()
    return [
        {
            "id": str(row[0]),
            "started_at": row[1].isoformat() if row[1] else None,
            "completed_at": row[2].isoformat() if row[2] else None,
            "target_url": row[3],
            "user_count": row[4],
            "status": row[5],
            "sections_run": row[6],
            "summary": row[7],
        }
        for row in rows
    ]


@router.get("/runs/{run_id}")
async def get_simulation_run(
    run_id: UUID,
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get full detail for a simulation run including user results."""
    # Get run
    result = await db.execute(
        text(
            "SELECT id, started_at, completed_at, target_url, user_count, "
            "status, sections_run, summary, phase_results, check_results "
            "FROM analytics.simulation_runs WHERE id = :run_id"
        ),
        {"run_id": str(run_id)},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Simulation run not found")

    run_data = {
        "id": str(row[0]),
        "started_at": row[1].isoformat() if row[1] else None,
        "completed_at": row[2].isoformat() if row[2] else None,
        "target_url": row[3],
        "user_count": row[4],
        "status": row[5],
        "sections_run": row[6],
        "summary": row[7],
        "phase_results": row[8],
        "check_results": row[9],
    }

    # Get user results
    user_result = await db.execute(
        text(
            "SELECT id, user_email, persona, actions, "
            "events_expected, events_recorded, result "
            "FROM analytics.simulation_user_results "
            "WHERE run_id = :run_id ORDER BY user_email"
        ),
        {"run_id": str(run_id)},
    )
    user_rows = user_result.fetchall()
    run_data["user_results"] = [
        {
            "id": str(ur[0]),
            "user_email": ur[1],
            "persona": ur[2],
            "actions": ur[3],
            "events_expected": ur[4],
            "events_recorded": ur[5],
            "result": ur[6],
        }
        for ur in user_rows
    ]

    return run_data
