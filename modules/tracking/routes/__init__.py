"""Tracking module route aggregator."""

from fastapi import APIRouter

from backend.core.config import settings
from modules.tracking.routes.admin_routes import router as admin_router
from modules.tracking.routes.custom_metrics_routes import router as metrics_router
from modules.tracking.routes.event_registry_routes import (
    router as event_registry_router,
)
from modules.tracking.routes.tracking_routes import router as tracking_router

router = APIRouter()

router.include_router(tracking_router, tags=["tracking"])
router.include_router(admin_router)
router.include_router(metrics_router)
router.include_router(event_registry_router)

if settings.enable_simulation:
    from modules.tracking.routes.simulation_routes import router as simulation_router

    router.include_router(simulation_router)
