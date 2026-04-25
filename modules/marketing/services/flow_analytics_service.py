"""Flow analytics service — enrollment funnel, step performance, completion rates."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_flow_stats(db: AsyncSession, flow_id: str) -> dict[str, Any]:
    """Get overall statistics for an automation flow."""
    # Enrollment counts by status
    status_rows = (
        (
            await db.execute(
                text(
                    "SELECT status, COUNT(*) as cnt "
                    "FROM marketing.flow_enrollments "
                    "WHERE flow_id = :fid "
                    "GROUP BY status"
                ),
                {"fid": flow_id},
            )
        )
        .mappings()
        .all()
    )

    by_status = {r["status"]: r["cnt"] for r in status_rows}
    total = sum(by_status.values())

    return {
        "flow_id": flow_id,
        "total_enrollments": total,
        "active": by_status.get("active", 0),
        "completed": by_status.get("completed", 0),
        "goal_reached": by_status.get("goal_reached", 0),
        "exited": by_status.get("exited", 0),
        "error": by_status.get("error", 0),
        "completion_rate": round(
            (by_status.get("completed", 0) + by_status.get("goal_reached", 0))
            / max(total, 1),
            4,
        ),
        "goal_rate": round(by_status.get("goal_reached", 0) / max(total, 1), 4),
    }


async def get_step_performance(db: AsyncSession, flow_id: str) -> list[dict[str, Any]]:
    """Get per-step execution metrics for a flow."""
    rows = (
        (
            await db.execute(
                text(
                    "SELECT afs.id as step_id, afs.step_type, afs.step_order, "
                    "  COUNT(fse.id) as total_executions, "
                    "  COUNT(fse.id) FILTER (WHERE fse.status = 'executed') as executed, "
                    "  COUNT(fse.id) FILTER (WHERE fse.status = 'waiting') as waiting, "
                    "  COUNT(fse.id) FILTER (WHERE fse.status = 'failed') as failed, "
                    "  COUNT(fse.id) FILTER (WHERE fse.status = 'skipped') as skipped "
                    "FROM marketing.automation_flow_steps afs "
                    "LEFT JOIN marketing.flow_step_executions fse ON fse.step_id = afs.id "
                    "WHERE afs.flow_id = :fid "
                    "GROUP BY afs.id, afs.step_type, afs.step_order "
                    "ORDER BY afs.step_order"
                ),
                {"fid": flow_id},
            )
        )
        .mappings()
        .all()
    )

    return [
        {
            "step_id": str(r["step_id"]),
            "step_type": r["step_type"],
            "step_order": r["step_order"],
            "total_executions": r["total_executions"],
            "executed": r["executed"],
            "waiting": r["waiting"],
            "failed": r["failed"],
            "skipped": r["skipped"],
            "success_rate": round(r["executed"] / max(r["total_executions"], 1), 4),
        }
        for r in rows
    ]


async def get_enrollment_timeline(
    db: AsyncSession,
    flow_id: str,
    days: int = 30,
) -> list[dict[str, Any]]:
    """Get daily enrollment counts for a flow."""
    rows = (
        (
            await db.execute(
                text(
                    "SELECT DATE_TRUNC('day', enrolled_at) as day, "
                    "  COUNT(*) as enrollments, "
                    "  COUNT(*) FILTER (WHERE status = 'completed') as completed, "
                    "  COUNT(*) FILTER (WHERE status = 'goal_reached') as goals "
                    "FROM marketing.flow_enrollments "
                    "WHERE flow_id = :fid "
                    "AND enrolled_at > NOW() - INTERVAL '1 day' * :days "
                    "GROUP BY 1 ORDER BY 1"
                ),
                {"fid": flow_id, "days": days},
            )
        )
        .mappings()
        .all()
    )

    return [
        {
            "day": r["day"].isoformat() if r["day"] else None,
            "enrollments": r["enrollments"],
            "completed": r["completed"],
            "goals": r["goals"],
        }
        for r in rows
    ]
