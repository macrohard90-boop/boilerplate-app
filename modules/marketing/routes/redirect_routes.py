"""Short URL redirect routes for SMS/WhatsApp click tracking.

GET /r/{code} — resolves short URL, records click, redirects to original.
Public (no auth) — recipients click these links from their phones.
"""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["marketing-redirects"])


@router.get("/r/{code}")
async def redirect_short_url(code: str, request: Request):
    """Resolve a short URL and redirect to the original destination.

    Records the click for attribution tracking before redirecting.
    """
    from modules.marketing.services.short_url_service import resolve_short_url

    data = await resolve_short_url(code)

    if not data or not data.get("url"):
        # Unknown code — redirect to homepage
        from backend.core.config import settings

        return RedirectResponse(url=settings.frontend_url, status_code=302)

    original_url = data["url"]
    campaign_id = data.get("campaign_id")
    recipient_id = data.get("recipient_id")

    # Record the click asynchronously (don't block the redirect)
    if campaign_id and recipient_id:
        import asyncio

        asyncio.create_task(
            _record_click(
                campaign_id=campaign_id,
                recipient_id=recipient_id,
                url=original_url,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
        )

    return RedirectResponse(url=original_url, status_code=302)


async def _record_click(
    campaign_id: str,
    recipient_id: str,
    url: str,
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    """Record a short URL click in campaign_link_clicks."""
    try:
        from backend.core.database import get_session_factory
        from sqlalchemy import text

        factory = get_session_factory()
        async with factory() as db:
            # Get the user_id from the recipient
            row = (
                (
                    await db.execute(
                        text(
                            "SELECT user_id FROM marketing.campaign_recipients "
                            "WHERE id = :rid"
                        ),
                        {"rid": recipient_id},
                    )
                )
                .mappings()
                .first()
            )
            user_id = str(row["user_id"]) if row else None

            await db.execute(
                text(
                    "INSERT INTO marketing.campaign_link_clicks "
                    "(recipient_id, campaign_id, user_id, url, "
                    " ip_address, user_agent, clicked_at) "
                    "VALUES (:rid, :cid, :uid, :url, :ip, :ua, NOW())"
                ),
                {
                    "rid": recipient_id,
                    "cid": campaign_id,
                    "uid": user_id,
                    "url": url,
                    "ip": ip_address,
                    "ua": user_agent,
                },
            )

            # Also update the recipient status to 'clicked' if not already
            await db.execute(
                text(
                    "UPDATE marketing.campaign_recipients "
                    "SET status = 'clicked', clicked_at = NOW() "
                    "WHERE id = :rid AND status NOT IN ('clicked', 'bounced', 'complained')"
                ),
                {"rid": recipient_id},
            )
            await db.commit()
    except Exception:
        logger.exception(
            "Failed to record click for campaign=%s recipient=%s",
            campaign_id,
            recipient_id,
        )
