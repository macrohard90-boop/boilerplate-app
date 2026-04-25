"""Flow worker — advances expired wait steps every 60 seconds.

Scans flow_step_executions for 'waiting' status where scheduled_at
has passed, then advances the enrollment to the next step.
"""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def advance_expired_waits(db: AsyncSession) -> dict:
    """Find and advance all expired wait steps.

    Processes up to 100 expired waits per run to prevent
    unbounded processing time.
    """
    rows = (
        (
            await db.execute(
                text(
                    "SELECT fse.id, fse.enrollment_id, fse.step_id "
                    "FROM marketing.flow_step_executions fse "
                    "WHERE fse.status = 'waiting' "
                    "AND fse.scheduled_at <= NOW() "
                    "ORDER BY fse.scheduled_at "
                    "LIMIT 100"
                )
            )
        )
        .mappings()
        .all()
    )

    if not rows:
        return {"advanced": 0, "errors": 0}

    from modules.marketing.services.flow_execution_service import (
        advance_enrollment,
    )

    advanced = 0
    errors = 0

    for row in rows:
        exec_id = str(row["id"])
        enrollment_id = str(row["enrollment_id"])

        try:
            # Mark execution as complete
            await db.execute(
                text(
                    "UPDATE marketing.flow_step_executions "
                    "SET status = 'executed', executed_at = NOW() "
                    "WHERE id = :eid"
                ),
                {"eid": exec_id},
            )
            await db.commit()

            # Advance to next step
            await advance_enrollment(db, enrollment_id)
            advanced += 1

        except Exception:
            logger.debug(
                "Failed to advance enrollment=%s", enrollment_id, exc_info=True
            )
            errors += 1

    logger.info(
        "Flow worker: %d expired waits found, %d advanced, %d errors",
        len(rows),
        advanced,
        errors,
    )

    return {"advanced": advanced, "errors": errors}
