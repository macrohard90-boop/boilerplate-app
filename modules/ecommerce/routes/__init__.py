"""E-commerce module route aggregator."""

from fastapi import APIRouter

from backend.core.config import settings
from modules.ecommerce.routes.product_routes import router as product_router
from modules.ecommerce.routes.category_routes import router as category_router
from modules.ecommerce.routes.cart_routes import router as cart_router
from modules.ecommerce.routes.order_routes import router as order_router
from modules.ecommerce.routes.wishlist_routes import router as wishlist_router
from modules.ecommerce.routes.review_routes import router as review_router
from modules.ecommerce.routes.admin_routes import router as admin_router

router = APIRouter()
router.include_router(product_router)
router.include_router(category_router)
router.include_router(cart_router)
router.include_router(order_router)
router.include_router(wishlist_router)
router.include_router(review_router)
router.include_router(admin_router)

if settings.enable_subscriptions:
    from modules.ecommerce.routes.subscription_routes import (
        router as subscription_router,
    )

    router.include_router(subscription_router)

if settings.enable_coupons:
    from modules.ecommerce.routes.discount_routes import router as discount_router

    router.include_router(discount_router)
