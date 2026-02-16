"""Checkout and payment status endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.dependencies import get_current_user, require_role, validate_csrf
from modules.payments.adapters.stripe_provider import get_stripe_provider
from modules.payments.models.schemas import (
    CheckoutRequest,
    CheckoutResponse,
    ErrorResponse,
    PaymentStatusResponse,
    RefundRequest,
    RefundResponse,
)
from modules.payments.services import checkout_service, payment_service
from modules.ecommerce.services import order_service

router = APIRouter()


@router.post(
    "/checkout",
    response_model=CheckoutResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
)
async def create_checkout(
    data: CheckoutRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    _csrf: None = Depends(validate_csrf),
):
    """Convert cart to order and create payment intent.

    Returns client_secret for frontend Stripe.js confirmation.
    """
    try:
        result = await checkout_service.checkout(
            db,
            user_id=str(user["user_id"]),
            shipping_address=data.shipping_address.model_dump(),
            billing_address=data.billing_address.model_dump() if data.billing_address else None,
            discount_code=data.discount_code,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "checkout_failed", "message": str(e), "details": None},
        )


@router.get(
    "/orders/{order_id}/payment",
    response_model=PaymentStatusResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_payment_status(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get payment status for an order."""
    order = await order_service.get_order(db, order_id, user_id=str(user["user_id"]))
    if not order:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Order not found", "details": None},
        )

    payment = await payment_service.get_payment_by_order(db, order_id)

    return PaymentStatusResponse(
        order_id=order_id,
        order_status=order["status"],
        payment_status=payment["status"] if payment else None,
        provider=payment["provider"] if payment else None,
        provider_payment_id=payment.get("provider_payment_id") if payment else None,
        amount=payment["amount"] if payment else order["total"],
        currency=payment["currency"] if payment else order.get("currency", "USD"),
        created_at=payment["created_at"] if payment else None,
    )


@router.post(
    "/orders/{order_id}/refund",
    response_model=RefundResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def refund_order(
    order_id: str,
    data: RefundRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    _csrf: None = Depends(validate_csrf),
):
    """Initiate a refund for an order. Admin can refund any order; users can refund their own."""
    # Check if user owns the order or is admin
    is_admin = user.get("role") == "admin"
    user_id = None if is_admin else str(user["user_id"])
    order = await order_service.get_order(db, order_id, user_id=user_id)
    if not order:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Order not found", "details": None},
        )

    if order["status"] not in ("completed", "accepted"):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_status",
                "message": f"Cannot refund order with status '{order['status']}'",
                "details": None,
            },
        )

    # Get payment record
    payment = await payment_service.get_payment_by_order(db, order_id)
    if not payment or payment["status"] != "succeeded":
        raise HTTPException(
            status_code=400,
            detail={
                "error": "no_payment",
                "message": "No successful payment found for this order",
                "details": None,
            },
        )

    # Process refund via Stripe
    provider = get_stripe_provider()
    try:
        result = await provider.refund(
            payment_id=payment["provider_payment_id"],
            amount=data.amount,
            reason=data.reason,
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "refund_failed", "message": str(e), "details": None},
        )

    # Record refund
    refund_amount = data.amount if data.amount else payment["amount"]
    await payment_service.create_refund_record(
        db,
        order_id=order_id,
        provider="stripe",
        provider_refund_id=result.provider_refund_id,
        amount=refund_amount,
        currency=payment["currency"],
    )

    # Update order status
    await order_service.update_order_status(db, order_id, "refunded")

    return RefundResponse(
        order_id=order_id,
        refund_id=result.provider_refund_id,
        status=result.status,
        amount=refund_amount,
        currency=payment["currency"],
    )
