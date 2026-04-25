"""Link rewriting engine for campaign delivery.

Handles three rewriting strategies per channel:
- Email: UTM injection + zone params for heatmap tracking
- SMS: Replace all links with short redirect URLs
- WhatsApp: Append UTM params to CTA button URLs

Also extends the existing inject_utm_params with zone-based heatmap support.
"""

import logging
import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

logger = logging.getLogger(__name__)

# Match <a href="..."> tags in HTML
_HREF_RE = re.compile(r'(<a\b[^>]*\bhref\s*=\s*")([^"]+)(")', re.IGNORECASE)

_UTM_KEYS = {"utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"}


def rewrite_email_links(
    html: str,
    utm_params: dict[str, str],
    campaign_id: str,
    recipient_id: str,
    *,
    enable_heatmap: bool = False,
) -> str:
    """Rewrite all links in email HTML.

    1. Inject UTM params (skip mailto/tel/anchor/javascript)
    2. If heatmap enabled, add _zp (zone position) and _rid (recipient id)
       query params for Layer 1 click tracking

    Args:
        html: Rendered email HTML.
        utm_params: UTM parameters to inject.
        campaign_id: Campaign ID for heatmap tracking.
        recipient_id: Recipient ID for per-user click attribution.
        enable_heatmap: Whether to add zone position params.

    Returns:
        Rewritten HTML.
    """
    link_index = [0]  # Mutable counter for zone position

    def _rewrite(match: re.Match) -> str:
        prefix, url, suffix = match.group(1), match.group(2), match.group(3)
        lower = url.lower().strip()

        # Skip non-http links
        if lower.startswith(("mailto:", "javascript:", "tel:", "#")):
            return match.group(0)

        parsed = urlparse(url)
        existing_qs = parse_qs(parsed.query)

        # Skip if UTM params already present
        if any(k in existing_qs for k in _UTM_KEYS):
            return match.group(0)

        # Build new query params
        params = dict(utm_params) if utm_params else {}

        # Add heatmap zone params
        if enable_heatmap:
            link_index[0] += 1
            params["_zp"] = str(link_index[0])
            params["_rid"] = recipient_id
            params["_cid"] = campaign_id

        if not params:
            return match.group(0)

        sep = "&" if parsed.query else ""
        new_query = parsed.query + sep + urlencode(params)
        new_url = urlunparse(parsed._replace(query=new_query))
        return prefix + new_url + suffix

    return _HREF_RE.sub(_rewrite, html)


def rewrite_sms_links(
    content: str,
    campaign_id: str,
    recipient_id: str,
    short_url_base: str,
) -> str:
    """Replace all URLs in SMS text with short tracking redirect URLs.

    Args:
        content: SMS body text.
        campaign_id: Campaign ID for tracking.
        recipient_id: Recipient ID for per-user click attribution.
        short_url_base: Base URL for short links (e.g., https://mysite.com/r/).

    Returns:
        SMS text with URLs replaced by short redirect links.
    """
    # Match URLs in plain text (http/https)
    url_pattern = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)

    def _replace_url(match: re.Match) -> str:
        original_url = match.group(0)
        # Short URL will be created by the short_url_service
        # Here we just mark it for replacement — actual creation happens in delivery service
        return f"{{{{short_url:{original_url}}}}}"

    return url_pattern.sub(_replace_url, content)


def build_utm_params(
    campaign_name: str,
    medium: str = "email",
    *,
    utm_source: str | None = None,
    utm_medium: str | None = None,
    utm_campaign: str | None = None,
    utm_content: str | None = None,
    utm_term: str | None = None,
    variant_label: str | None = None,
) -> dict[str, str]:
    """Build UTM parameter dict from campaign metadata.

    Auto-generates reasonable defaults when explicit values aren't provided.
    """
    params: dict[str, str] = {}

    params["utm_source"] = utm_source or "marketing"
    params["utm_medium"] = utm_medium or medium
    params["utm_campaign"] = utm_campaign or campaign_name.lower().replace(" ", "-")

    if utm_content:
        params["utm_content"] = utm_content
    elif variant_label:
        params["utm_content"] = f"variant-{variant_label.lower()}"

    if utm_term:
        params["utm_term"] = utm_term

    return {k: v for k, v in params.items() if v}


def rewrite_whatsapp_params(
    parameters: dict | None,
    utm_params: dict[str, str],
    campaign_id: str,
    recipient_id: str,
) -> dict:
    """Add tracking params to WhatsApp template parameters.

    WhatsApp templates have fixed structure — we append UTM params to any
    URL-type parameters so CTA buttons carry tracking.
    """
    if not parameters:
        parameters = {}

    # Add tracking metadata that the template can reference
    parameters["_utm"] = urlencode(utm_params) if utm_params else ""
    parameters["_cid"] = campaign_id
    parameters["_rid"] = recipient_id

    return parameters
