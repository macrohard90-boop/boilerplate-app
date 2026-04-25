"""Notifications module routes.

Webhook routes are always registered (providers send delivery status regardless).
Admin routes are gated by enable_sms / enable_whatsapp settings.
"""

from fastapi import APIRouter

from backend.core.config import settings
from modules.notifications.routes.webhook_routes import router as webhook_router

router = APIRouter()

# Webhook routes always active — providers send status callbacks regardless
router.include_router(webhook_router)

# Channel-specific admin routes (test sends, message log, automation rules)
if settings.enable_sms or settings.enable_whatsapp:
    from modules.notifications.routes.admin_routes import router as admin_router

    router.include_router(admin_router)
