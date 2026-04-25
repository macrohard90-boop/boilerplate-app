"""Marketing module route aggregator."""

from fastapi import APIRouter

from modules.marketing.routes.admin_routes import router as admin_router
from modules.marketing.routes.analytics_routes import router as analytics_router
from modules.marketing.routes.flow_routes import router as flow_router
from modules.marketing.routes.redirect_routes import router as redirect_router
from modules.marketing.routes.user_routes import router as user_router

router = APIRouter()
router.include_router(admin_router)
router.include_router(analytics_router)
router.include_router(flow_router)
router.include_router(user_router)
router.include_router(redirect_router)
