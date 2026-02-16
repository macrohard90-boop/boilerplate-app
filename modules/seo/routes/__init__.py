"""SEO module route aggregator."""

from fastapi import APIRouter

from modules.seo.routes.seo_routes import router as seo_router
from modules.seo.routes.admin_routes import router as admin_router

router = APIRouter()

router.include_router(seo_router)
router.include_router(admin_router)
