"""Marketing module route aggregator."""

from fastapi import APIRouter

from modules.marketing.routes.admin_routes import router as admin_router
from modules.marketing.routes.user_routes import router as user_router

router = APIRouter()
router.include_router(admin_router)
router.include_router(user_router)
