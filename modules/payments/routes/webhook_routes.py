"""Stripe webhook receiver.

This endpoint is excluded from CSRF protection — Stripe uses its own
signature scheme (Stripe-Signature header) for verification.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from modules.payments.services import webhook_service

router = APIRouter()


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive and process Stripe webhook events.

    No auth required — verification is via Stripe-Signature header.
    Always returns 200 to prevent Stripe from retrying.
    """
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature", "")

    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    try:
        result = await webhook_service.verify_and_process_webhook(db, payload, sig_header)
        return {"received": True, **result}
    except ValueError as e:
        # Signature verification failed
        raise HTTPException(status_code=400, detail=str(e))
