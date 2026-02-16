"""Payment module route aggregator."""

from fastapi import APIRouter

from modules.payments.routes.checkout_routes import router as checkout_router
from modules.payments.routes.webhook_routes import router as webhook_router
from modules.payments.routes.merchant_routes import router as merchant_router

router = APIRouter()
router.include_router(checkout_router, tags=["payments-checkout"])
router.include_router(webhook_router, tags=["payments-webhook"])
router.include_router(merchant_router)
