"""Tracking module route aggregator."""

from fastapi import APIRouter

from modules.tracking.routes.admin_routes import router as admin_router
from modules.tracking.routes.tracking_routes import router as tracking_router

router = APIRouter()

router.include_router(tracking_router, tags=["tracking"])
router.include_router(admin_router)
