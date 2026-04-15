"""Background SEO re-scorer — periodically scores all pages.

Follows the same pattern as modules/payments/services/order_reaper.py:
asyncio task started in main.py lifespan, while-True loop with sleep.
"""

import asyncio
import logging

from backend.core.config import settings
from backend.core.database import get_session_factory

logger = logging.getLogger(__name__)


async def rescorer_loop() -> None:
    """Background loop that periodically re-scores all pages."""
    logger.info(
        "SEO rescorer started (interval=%ds)",
        settings.seo_rescore_interval,
    )
    while True:
        await asyncio.sleep(settings.seo_rescore_interval)
        try:
            count = await rescore_all_pages()
            logger.info("SEO rescorer: scored %d pages", count)
        except Exception:
            logger.exception("SEO rescorer iteration failed")


async def rescore_all_pages() -> int:
    """Score all known pages and create snapshots for changes."""
    from modules.seo.services.scoring_service import score_page, _collect_all_paths
    from modules.seo.services.snapshot_service import take_snapshot

    factory = get_session_factory()
    async with factory() as db:
        paths = await _collect_all_paths(db)
        scored = 0
        for path in paths:
            try:
                await score_page(db, path)
                await take_snapshot(db, path, trigger="scheduled")
                scored += 1
            except Exception:
                logger.exception("Failed to score path: %s", path)
            # Small delay to avoid hammering the DB
            await asyncio.sleep(0.1)
        return scored
