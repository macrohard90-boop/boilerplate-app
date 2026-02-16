"""GDPR module route aggregator."""

from fastapi import APIRouter

from modules.gdpr.routes.consent_routes import router as consent_router
from modules.gdpr.routes.cookie_routes import router as cookie_router
from modules.gdpr.routes.deletion_routes import router as deletion_router
from modules.gdpr.routes.email_pref_routes import router as email_pref_router
from modules.gdpr.routes.export_routes import router as export_router
from modules.gdpr.routes.admin_routes import router as admin_router

router = APIRouter()

router.include_router(consent_router)
router.include_router(cookie_router)
router.include_router(export_router)
router.include_router(deletion_router)
router.include_router(email_pref_router)
router.include_router(admin_router)
