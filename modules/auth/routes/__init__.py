"""Auth module route aggregation."""

from fastapi import APIRouter

from modules.auth.routes.admin_routes import router as admin_router
from modules.auth.routes.auth_routes import router as auth_router
from modules.auth.routes.api_key_routes import router as api_key_router
from modules.auth.routes.oauth_routes import router as oauth_router
from modules.auth.services.oauth_service import init_providers

# Initialize OAuth providers on module load
init_providers()

router = APIRouter(tags=["auth"])
router.include_router(admin_router)
router.include_router(auth_router)
router.include_router(api_key_router)
router.include_router(oauth_router)
