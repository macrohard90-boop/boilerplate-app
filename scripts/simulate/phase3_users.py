"""Phase 3: User Simulation — 100 concurrent user journeys via API."""

import asyncio
import logging
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import httpx

from .fake_agents import AGENTS, DESKTOP_AGENTS, MOBILE_AGENTS, TABLET_AGENTS, FakeAgent
from .personas import Persona, assign_personas, inject_declines
from .stripe_utils import confirm_payment_intent

logger = logging.getLogger(__name__)

# Referrer sources for simulation
REFERRERS = [
    ("https://www.google.com/search?q=products", "google", "organic"),
    ("https://www.google.com/search?q=best+deals", "google", "organic"),
    ("https://www.facebook.com/", "facebook", "social"),
    ("https://t.co/abc123", "twitter", "social"),
    ("https://www.reddit.com/r/deals/", "reddit", "social"),
    ("", "direct", "none"),  # Direct visit (no referrer)
    ("", "direct", "none"),
    ("", "direct", "none"),  # Weight direct visits higher
]

# Product pages to browse (filled dynamically from Phase 2 results)
BROWSE_PAGES = ["/", "/products", "/products?tab=subscriptions"]


@dataclass
class UserAction:
    """Single action taken by a simulated user."""

    action: str
    endpoint: str = ""
    method: str = "GET"
    status_code: int = 0
    passed: bool = True
    detail: str = ""
    simulated_time: str = ""


@dataclass
class SimUser:
    """A simulated user and their journey."""

    index: int
    email: str
    password: str
    persona: Persona
    agent: FakeAgent
    session_id: str = ""
    token: str = ""
    csrf: str = ""
    user_id: str = ""
    actions: list[UserAction] = field(default_factory=list)
    referrer: tuple[str, str, str] = ("", "direct", "none")

    # Populated during journey
    products_seen: list[dict] = field(default_factory=list)
    cart_items: list[dict] = field(default_factory=list)
    orders: list[dict] = field(default_factory=list)

    @property
    def result(self) -> str:
        return "PASS" if all(a.passed for a in self.actions) else "FAIL"

    @property
    def events_expected(self) -> int:
        # Approximate based on actions taken
        return len(
            [
                a
                for a in self.actions
                if "track" in a.action.lower() or "event" in a.action.lower()
            ]
        )

    def auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Csrf-Token": self.csrf,
            "X-Session-ID": self.session_id,
            "User-Agent": self.agent.raw,
        }


async def _register_user(
    client: httpx.AsyncClient, api_url: str, user: SimUser
) -> bool:
    """Register and login a user."""
    try:
        resp = await client.post(
            f"{api_url}/auth/register",
            json={
                "email": user.email,
                "password": user.password,
                "first_name": f"Sim{user.index:03d}",
                "last_name": user.persona.name.replace("_", " ").title(),
            },
            headers={"User-Agent": user.agent.raw},
        )
        if resp.status_code == 201:
            data = resp.json()
            user.token = data["access_token"]
            user.csrf = data.get("csrf_token", "")
            user.session_id = str(uuid.uuid4())
            # Extract user_id from JWT (or from /me endpoint)
            me_resp = await client.get(
                f"{api_url}/auth/me",
                headers=user.auth_headers(),
            )
            if me_resp.status_code == 200:
                user.user_id = me_resp.json().get("user", {}).get("id", "")
            user.actions.append(
                UserAction(
                    action="register",
                    endpoint="/auth/register",
                    method="POST",
                    status_code=resp.status_code,
                    passed=True,
                )
            )
            return True
        else:
            user.actions.append(
                UserAction(
                    action="register",
                    endpoint="/auth/register",
                    method="POST",
                    status_code=resp.status_code,
                    passed=False,
                    detail=resp.text[:200],
                )
            )
            return False
    except Exception as e:
        user.actions.append(
            UserAction(
                action="register",
                endpoint="/auth/register",
                method="POST",
                passed=False,
                detail=str(e),
            )
        )
        return False


async def _grant_consent(
    client: httpx.AsyncClient, api_url: str, user: SimUser, db_url: str
) -> None:
    """Grant GDPR analytics consent via direct DB insert."""
    import psycopg2

    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()

        # Cookie preferences (for session-based consent)
        cur.execute(
            "INSERT INTO gdpr.cookie_preferences "
            "(user_id, session_id, necessary, analytics, marketing, preferences) "
            "VALUES (%s, %s, true, true, true, true) "
            "ON CONFLICT DO NOTHING",
            (user.user_id, user.session_id),
        )

        # Explicit consent record
        cur.execute(
            "INSERT INTO gdpr.consent_records "
            "(user_id, consent_type, granted) "
            "VALUES (%s, 'analytics', true) "
            "ON CONFLICT DO NOTHING",
            (user.user_id,),
        )

        cur.close()
        conn.close()

        user.actions.append(
            UserAction(
                action="grant_consent",
                passed=True,
            )
        )
    except Exception as e:
        user.actions.append(
            UserAction(
                action="grant_consent",
                passed=False,
                detail=str(e),
            )
        )


async def _track_pageview(
    client: httpx.AsyncClient,
    api_url: str,
    user: SimUser,
    path: str,
    duration_ms: int,
    trigger: str = "navigated",
) -> None:
    """Send a pageview tracking event."""
    try:
        headers = user.auth_headers()
        if user.referrer[0]:
            headers["Referer"] = user.referrer[0]

        resp = await client.post(
            f"{api_url}/tracking/pageview",
            json={
                "path": path,
                "duration_ms": duration_ms,
                "referrer": user.referrer[0] or None,
                "trigger": trigger,
            },
            headers=headers,
        )
        user.actions.append(
            UserAction(
                action=f"pageview:{path}",
                endpoint="/tracking/pageview",
                method="POST",
                status_code=resp.status_code,
                passed=resp.status_code in (200, 201),
            )
        )
    except Exception as e:
        user.actions.append(
            UserAction(
                action=f"pageview:{path}",
                passed=False,
                detail=str(e),
            )
        )


async def _track_event(
    client: httpx.AsyncClient,
    api_url: str,
    user: SimUser,
    event_type: str,
    event_data: dict | None = None,
) -> None:
    """Fire a tracking event."""
    try:
        resp = await client.post(
            f"{api_url}/tracking/events",
            json={"event_type": event_type, "event_data": event_data or {}},
            headers=user.auth_headers(),
        )
        user.actions.append(
            UserAction(
                action=f"event:{event_type}",
                endpoint="/tracking/events",
                method="POST",
                status_code=resp.status_code,
                passed=resp.status_code in (200, 201),
            )
        )
    except Exception as e:
        user.actions.append(
            UserAction(
                action=f"event:{event_type}",
                passed=False,
                detail=str(e),
            )
        )


async def _browse_products(
    client: httpx.AsyncClient,
    api_url: str,
    user: SimUser,
    catalog: list[dict],
) -> None:
    """Browse products — view pages, fire events."""
    num_to_view = random.randint(*user.persona.products_to_view)

    # Homepage
    await _track_pageview(client, api_url, user, "/", random.randint(3000, 12000))

    # Products page
    await _track_pageview(
        client, api_url, user, "/products", random.randint(5000, 15000)
    )

    # Search (if persona searches)
    for _ in range(user.persona.searches):
        query = random.choice(
            ["shoes", "electronics", "leather", "wireless", "ceramic", "shirt"]
        )
        try:
            resp = await client.get(
                f"{api_url}/ecommerce/products",
                params={"search": query},
                headers=user.auth_headers(),
            )
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                await _track_event(
                    client, api_url, user, "search_performed", {"query": query}
                )
                if not items:
                    await _track_event(
                        client, api_url, user, "search_no_results", {"query": query}
                    )
        except Exception:
            pass

    # Sort/filter
    if user.persona.uses_filter:
        await _track_event(
            client, api_url, user, "sort_changed", {"sort_value": "price_asc"}
        )
        if catalog:
            cat = random.choice(catalog)
            await _track_event(
                client,
                api_url,
                user,
                "filter_used",
                {
                    "filter_type": "category",
                    "filter_value": cat.get("name", ""),
                },
            )

    # View individual products
    available_products = [p for p in catalog if p.get("variants")]
    products_to_view = (
        random.sample(
            available_products,
            min(num_to_view, len(available_products)),
        )
        if available_products
        else []
    )

    for product in products_to_view:
        slug = product["name"].lower().replace(" ", "-")
        await _track_pageview(
            client, api_url, user, f"/products/{slug}", random.randint(8000, 45000)
        )

        await _track_event(
            client,
            api_url,
            user,
            "product_viewed",
            {
                "product_id": product["id"],
                "product_name": product["name"],
            },
        )

        # Check if out of stock
        oos_variants = [
            v for v in product.get("variants", []) if v.get("stock", 0) == 0
        ]
        if oos_variants:
            await _track_event(
                client,
                api_url,
                user,
                "out_of_stock_viewed",
                {
                    "product_id": product["id"],
                    "variant_id": oos_variants[0]["id"],
                },
            )

        # Variant selection
        if len(product.get("variants", [])) > 1:
            variant = random.choice(product["variants"])
            await _track_event(
                client,
                api_url,
                user,
                "variant_selected",
                {
                    "product_id": product["id"],
                    "variant_id": variant["id"],
                    "variant_name": variant["name"],
                },
            )

        user.products_seen.append(product)

    # Category browsing
    for _ in range(user.persona.categories_to_browse):
        if catalog:
            cat = random.choice(catalog)
            await _track_pageview(
                client,
                api_url,
                user,
                f"/categories/{cat['name'].lower()}",
                random.randint(5000, 20000),
            )
            await _track_event(
                client,
                api_url,
                user,
                "category_browsed",
                {
                    "category_id": cat.get("id", ""),
                    "category_name": cat.get("name", ""),
                },
            )


async def _cart_operations(
    client: httpx.AsyncClient,
    api_url: str,
    user: SimUser,
    catalog: list[dict],
) -> None:
    """Add items to cart, modify quantities, etc."""
    if not user.persona.adds_to_cart:
        # View empty cart
        await _track_event(client, api_url, user, "empty_cart_viewed")
        return

    # Select items to add
    buyable = [
        p
        for p in catalog
        if p.get("variants")
        and any(v.get("stock", 0) > 0 for v in p["variants"])
        and p.get("pricing_type", "one_time") == "one_time"
    ]

    if user.persona.subscribes:
        # Subscriber adds a subscription product
        subs = [p for p in catalog if p.get("pricing_type") == "recurring"]
        if subs:
            buyable = subs

    num_items = random.randint(*user.persona.cart_items) if buyable else 0
    items_to_add = random.sample(buyable, min(num_items, len(buyable)))

    for product in items_to_add:
        # Pick a variant with stock
        in_stock = [v for v in product.get("variants", []) if v.get("stock", 0) > 0]
        if not in_stock and product.get("pricing_type") != "recurring":
            continue

        variant_id = in_stock[0]["id"] if in_stock else None
        quantity = random.randint(1, 3)

        try:
            payload = {"product_id": product["id"], "quantity": quantity}
            if variant_id:
                payload["variant_id"] = variant_id

            resp = await client.post(
                f"{api_url}/ecommerce/cart",
                json=payload,
                headers=user.auth_headers(),
            )
            if resp.status_code in (200, 201):
                user.cart_items.append(
                    {
                        "product_id": product["id"],
                        "variant_id": variant_id,
                        "quantity": quantity,
                        "name": product["name"],
                    }
                )
                await _track_event(
                    client,
                    api_url,
                    user,
                    "add_to_cart",
                    {
                        "product_id": product["id"],
                        "variant_id": variant_id,
                        "quantity": quantity,
                        "price": product.get("base_price", 0),
                    },
                )
            else:
                user.actions.append(
                    UserAction(
                        action=f"add_to_cart:{product['name']}",
                        endpoint="/cart",
                        method="POST",
                        status_code=resp.status_code,
                        passed=False,
                        detail=resp.text[:200],
                    )
                )
        except Exception as e:
            user.actions.append(
                UserAction(
                    action=f"add_to_cart:{product['name']}",
                    passed=False,
                    detail=str(e),
                )
            )

    if not user.cart_items:
        return

    # View cart
    try:
        resp = await client.get(
            f"{api_url}/ecommerce/cart", headers=user.auth_headers()
        )
        if resp.status_code == 200:
            cart_data = resp.json()
            await _track_event(
                client,
                api_url,
                user,
                "cart_viewed",
                {
                    "item_count": cart_data.get("item_count", len(user.cart_items)),
                    "cart_total": cart_data.get("total", 0),
                },
            )

            # High value cart check
            if cart_data.get("total", 0) > 10000:
                await _track_event(
                    client,
                    api_url,
                    user,
                    "high_value_cart",
                    {
                        "cart_total": cart_data.get("total", 0),
                        "item_count": cart_data.get("item_count", 0),
                    },
                )
    except Exception:
        pass

    # Quantity changes
    if user.persona.changes_quantity and user.cart_items:
        item = random.choice(user.cart_items)
        old_qty = item["quantity"]
        new_qty = old_qty + 1
        await _track_event(
            client,
            api_url,
            user,
            "cart_quantity_changed",
            {
                "product_id": item["product_id"],
                "old_qty": old_qty,
                "new_qty": new_qty,
            },
        )

    # Remove item
    if user.persona.removes_item and len(user.cart_items) > 1:
        removed = user.cart_items.pop()
        try:
            await client.delete(
                f"{api_url}/ecommerce/cart/items/{removed['product_id']}",
                headers=user.auth_headers(),
            )
            await _track_event(
                client,
                api_url,
                user,
                "remove_from_cart",
                {
                    "product_id": removed["product_id"],
                },
            )
        except Exception:
            pass


async def _checkout_flow(
    client: httpx.AsyncClient,
    api_url: str,
    user: SimUser,
) -> None:
    """Checkout: create order, optionally confirm Stripe payment."""
    if not user.persona.starts_checkout or not user.cart_items:
        return

    await _track_pageview(
        client, api_url, user, "/checkout", random.randint(10000, 30000)
    )

    # Checkout step events
    for step in range(1, 4):
        await _track_event(
            client,
            api_url,
            user,
            "checkout_step_viewed",
            {
                "step": step,
            },
        )

    # Abandon checkout?
    if not user.persona.completes_payment and not user.persona.intentional_decline:
        await _track_event(
            client,
            api_url,
            user,
            "checkout_abandoned",
            {
                "step": random.randint(1, 3),
                "items_abandoned": len(user.cart_items),
            },
        )
        return

    # Create checkout
    try:
        resp = await client.post(
            f"{api_url}/payments/checkout",
            json={
                "shipping_address": {
                    "line1": f"{random.randint(100,999)} Simulation St",
                    "city": random.choice(
                        ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix"]
                    ),
                    "state": random.choice(["NY", "CA", "IL", "TX", "AZ"]),
                    "postal_code": f"{random.randint(10000, 99999)}",
                    "country": "US",
                },
            },
            headers=user.auth_headers(),
        )

        if resp.status_code not in (200, 201):
            user.actions.append(
                UserAction(
                    action="checkout",
                    endpoint="/checkout",
                    method="POST",
                    status_code=resp.status_code,
                    passed=False,
                    detail=resp.text[:300],
                )
            )
            return

        checkout_data = resp.json()
        order_id = checkout_data.get("order_id", "")
        client_secret = checkout_data.get("client_secret", "")

        user.actions.append(
            UserAction(
                action="checkout",
                endpoint="/checkout",
                method="POST",
                status_code=resp.status_code,
                passed=True,
                detail=f"order_id={order_id}",
            )
        )

        await _track_event(
            client,
            api_url,
            user,
            "payment_submitted",
            {
                "order_id": order_id,
            },
        )

        if not client_secret:
            user.actions.append(
                UserAction(
                    action="stripe_confirm",
                    passed=False,
                    detail="No client_secret returned",
                )
            )
            return

        # Confirm Stripe payment
        decline = user.persona.intentional_decline
        stripe_result = confirm_payment_intent(client_secret, decline=decline)

        if decline:
            await _track_event(
                client,
                api_url,
                user,
                "payment_failed",
                {
                    "order_id": order_id,
                    "error_code": "card_declined",
                },
            )
            user.actions.append(
                UserAction(
                    action="stripe_decline",
                    passed=True,
                    detail=f"Intentional decline: {stripe_result.get('status')}",
                )
            )
            user.orders.append(
                {"order_id": order_id, "status": "declined", "stripe": stripe_result}
            )
            return

        user.actions.append(
            UserAction(
                action="stripe_confirm",
                passed=stripe_result.get("status") == "succeeded",
                detail=f"status={stripe_result.get('status')}",
            )
        )

        # Poll for webhook to update order status
        payment_confirmed = False
        for attempt in range(30):
            await asyncio.sleep(1)
            try:
                pay_resp = await client.get(
                    f"{api_url}/payments/orders/{order_id}/payment",
                    headers=user.auth_headers(),
                )
                if pay_resp.status_code == 200:
                    pay_data = pay_resp.json()
                    if pay_data.get("payment_status") == "succeeded":
                        payment_confirmed = True
                        break
            except Exception:
                pass

        if payment_confirmed:
            await _track_event(
                client,
                api_url,
                user,
                "purchase_completed",
                {
                    "order_id": order_id,
                    "order_total": checkout_data.get("total", 0),
                },
            )
            user.orders.append(
                {"order_id": order_id, "status": "completed", "stripe": stripe_result}
            )
        else:
            user.actions.append(
                UserAction(
                    action="webhook_poll",
                    passed=False,
                    detail=f"Payment not confirmed after 30s for order {order_id}",
                )
            )
            user.orders.append(
                {"order_id": order_id, "status": "pending", "stripe": stripe_result}
            )

    except Exception as e:
        user.actions.append(
            UserAction(
                action="checkout",
                passed=False,
                detail=str(e),
            )
        )


async def _wishlist_operations(
    client: httpx.AsyncClient,
    api_url: str,
    user: SimUser,
) -> None:
    """Wishlist operations for personas that use wishlists."""
    if not user.persona.uses_wishlist or not user.products_seen:
        return

    # Add a product to wishlist
    product = random.choice(user.products_seen)
    try:
        resp = await client.post(
            f"{api_url}/ecommerce/wishlists",
            json={"product_id": product["id"]},
            headers=user.auth_headers(),
        )
        if resp.status_code not in (200, 201):
            return

        # View wishlist
        await _track_pageview(
            client, api_url, user, "/dashboard/wishlists", random.randint(5000, 15000)
        )

        if user.persona.moves_wishlist_to_cart:
            # Move to cart
            in_stock = [v for v in product.get("variants", []) if v.get("stock", 0) > 0]
            if in_stock:
                await _track_event(
                    client,
                    api_url,
                    user,
                    "wishlist_moved_to_cart",
                    {
                        "product_id": product["id"],
                        "quantity": 1,
                    },
                )
        else:
            # Remove from wishlist
            await _track_event(
                client,
                api_url,
                user,
                "wishlist_removed",
                {
                    "product_id": product["id"],
                },
            )
    except Exception:
        pass


async def _session_events(
    client: httpx.AsyncClient,
    api_url: str,
    user: SimUser,
) -> None:
    """Fire session-level engagement events."""
    duration_min = random.randint(*user.persona.session_duration_min)

    # Return visit (for power buyers)
    if user.persona.return_visits > 0:
        days_since = random.randint(1, 7)
        await _track_event(
            client,
            api_url,
            user,
            "return_visit",
            {
                "days_since_last": days_since,
            },
        )

    # Long session
    if duration_min >= 10:
        await _track_event(
            client,
            api_url,
            user,
            "long_session",
            {
                "duration_sec": 600,
            },
        )

    # Heartbeat
    try:
        await client.post(
            f"{api_url}/tracking/heartbeat",
            json={"path": "/products", "status": "active"},
            headers=user.auth_headers(),
        )
    except Exception:
        pass

    # Cookie consent event
    await _track_event(
        client,
        api_url,
        user,
        "cookie_consent_given",
        {
            "analytics": True,
            "marketing": True,
        },
    )

    # Login completed event (the backend may auto-fire this, but we fire it to be safe)
    await _track_event(
        client,
        api_url,
        user,
        "login_completed",
        {
            "method": "email",
        },
    )

    # Final pageview with trigger="closed"
    await _track_pageview(
        client, api_url, user, "/", random.randint(1000, 3000), trigger="closed"
    )


# -----------------------------------------------------------------------
# Edge case journeys — auth/profile stress tests
# -----------------------------------------------------------------------

EDGE_CASES = [
    "re_register",  # Log out → try register same email → expect error → log back in
    "wrong_password",  # Log out → 3 wrong password logins → correct login
    "forgot_password",  # Request password reset → verify 200
    "profile_update",  # Update first/last name + phone → verify changes via /me
    "consent_toggle",  # Toggle marketing consent off → back on
]

# How many users per edge case
EDGE_CASE_COUNTS = {
    "re_register": 2,
    "wrong_password": 2,
    "forgot_password": 2,
    "profile_update": 3,
    "consent_toggle": 2,
}


def _assign_edge_cases(users: list["SimUser"]) -> dict[str, list["SimUser"]]:
    """Randomly assign edge case journeys to users. Returns mapping of case → users."""
    available = [u for u in users if u.user_id]  # Only registered users
    if len(available) < sum(EDGE_CASE_COUNTS.values()):
        logger.warning("Not enough users for all edge cases, assigning what we can")

    random.shuffle(available)
    assignments: dict[str, list[SimUser]] = {}
    idx = 0
    for case in EDGE_CASES:
        count = EDGE_CASE_COUNTS[case]
        assignments[case] = available[idx : idx + count]
        idx += count
    return assignments


async def _edge_re_register(
    client: httpx.AsyncClient, api_url: str, user: SimUser
) -> None:
    """Log out → try to register with same email (expect 409) → log back in."""
    # Logout
    try:
        resp = await client.post(f"{api_url}/auth/logout", headers=user.auth_headers())
        user.actions.append(
            UserAction(
                action="edge:logout",
                endpoint="/auth/logout",
                method="POST",
                status_code=resp.status_code,
                passed=resp.status_code == 200,
            )
        )
    except Exception as e:
        user.actions.append(
            UserAction(action="edge:logout", passed=False, detail=str(e))
        )
        return

    # Try to re-register with same email — should fail with 409
    try:
        resp = await client.post(
            f"{api_url}/auth/register",
            json={
                "email": user.email,
                "password": user.password,
                "first_name": "Duplicate",
                "last_name": "User",
            },
            headers={"User-Agent": user.agent.raw},
        )
        user.actions.append(
            UserAction(
                action="edge:re_register_attempt",
                endpoint="/auth/register",
                method="POST",
                status_code=resp.status_code,
                passed=resp.status_code == 409,  # We EXPECT 409
                detail=f"Expected 409, got {resp.status_code}",
            )
        )
    except Exception as e:
        user.actions.append(
            UserAction(action="edge:re_register_attempt", passed=False, detail=str(e))
        )

    # Log back in
    await _edge_relogin(client, api_url, user)


async def _edge_wrong_password(
    client: httpx.AsyncClient, api_url: str, user: SimUser
) -> None:
    """Log out → 3 wrong password attempts → correct login."""
    # Logout
    try:
        resp = await client.post(f"{api_url}/auth/logout", headers=user.auth_headers())
        user.actions.append(
            UserAction(
                action="edge:logout",
                endpoint="/auth/logout",
                method="POST",
                status_code=resp.status_code,
                passed=resp.status_code == 200,
            )
        )
    except Exception as e:
        user.actions.append(
            UserAction(action="edge:logout", passed=False, detail=str(e))
        )
        return

    # 3 wrong password attempts
    for attempt in range(1, 4):
        try:
            resp = await client.post(
                f"{api_url}/auth/login",
                json={"email": user.email, "password": f"WrongPass{attempt}!"},
                headers={"User-Agent": user.agent.raw},
            )
            user.actions.append(
                UserAction(
                    action=f"edge:wrong_password_{attempt}",
                    endpoint="/auth/login",
                    method="POST",
                    status_code=resp.status_code,
                    passed=resp.status_code == 401,  # We EXPECT 401
                    detail=f"Expected 401, got {resp.status_code}",
                )
            )
        except Exception as e:
            user.actions.append(
                UserAction(
                    action=f"edge:wrong_password_{attempt}",
                    passed=False,
                    detail=str(e),
                )
            )

    # Correct login
    await _edge_relogin(client, api_url, user)


async def _edge_forgot_password(
    client: httpx.AsyncClient, api_url: str, user: SimUser
) -> None:
    """Request password reset — verify the endpoint returns 200."""
    try:
        resp = await client.post(
            f"{api_url}/auth/forgot-password",
            json={"email": user.email},
            headers={"User-Agent": user.agent.raw},
        )
        user.actions.append(
            UserAction(
                action="edge:forgot_password",
                endpoint="/auth/forgot-password",
                method="POST",
                status_code=resp.status_code,
                passed=resp.status_code == 200,
            )
        )
    except Exception as e:
        user.actions.append(
            UserAction(action="edge:forgot_password", passed=False, detail=str(e))
        )

    # Verify user is still logged in (forgot-password doesn't invalidate session)
    try:
        resp = await client.get(f"{api_url}/auth/me", headers=user.auth_headers())
        user.actions.append(
            UserAction(
                action="edge:verify_still_authed",
                endpoint="/auth/me",
                method="GET",
                status_code=resp.status_code,
                passed=resp.status_code == 200,
            )
        )
    except Exception as e:
        user.actions.append(
            UserAction(action="edge:verify_still_authed", passed=False, detail=str(e))
        )


async def _edge_profile_update(
    client: httpx.AsyncClient, api_url: str, user: SimUser
) -> None:
    """Update profile fields and verify changes via /me."""
    new_first = f"Updated{user.index:03d}"
    new_last = "Tester"
    new_phone = f"+1555{user.index:04d}{random.randint(100,999)}"

    # Update profile
    try:
        resp = await client.put(
            f"{api_url}/auth/profile",
            json={
                "first_name": new_first,
                "last_name": new_last,
                "phone": new_phone,
            },
            headers=user.auth_headers(),
        )
        user.actions.append(
            UserAction(
                action="edge:profile_update",
                endpoint="/auth/profile",
                method="PUT",
                status_code=resp.status_code,
                passed=resp.status_code == 200,
                detail=f"first={new_first}, last={new_last}, phone={new_phone}",
            )
        )
    except Exception as e:
        user.actions.append(
            UserAction(action="edge:profile_update", passed=False, detail=str(e))
        )
        return

    # Verify changes via /me
    try:
        resp = await client.get(f"{api_url}/auth/me", headers=user.auth_headers())
        if resp.status_code == 200:
            me = resp.json().get("user", {})
            name_ok = (
                me.get("first_name") == new_first and me.get("last_name") == new_last
            )
            user.actions.append(
                UserAction(
                    action="edge:profile_verify",
                    endpoint="/auth/me",
                    method="GET",
                    status_code=200,
                    passed=name_ok,
                    detail=f"name_match={name_ok}",
                )
            )
        else:
            user.actions.append(
                UserAction(
                    action="edge:profile_verify",
                    endpoint="/auth/me",
                    method="GET",
                    status_code=resp.status_code,
                    passed=False,
                )
            )
    except Exception as e:
        user.actions.append(
            UserAction(action="edge:profile_verify", passed=False, detail=str(e))
        )


async def _edge_consent_toggle(
    client: httpx.AsyncClient, api_url: str, user: SimUser
) -> None:
    """Toggle marketing consent off, then back on."""
    # Turn marketing off
    try:
        resp = await client.post(
            f"{api_url}/gdpr/consent",
            json={
                "consent_type": "marketing_email",
                "granted": False,
                "version": "1.0",
            },
            headers=user.auth_headers(),
        )
        user.actions.append(
            UserAction(
                action="edge:consent_marketing_off",
                endpoint="/gdpr/consent",
                method="POST",
                status_code=resp.status_code,
                passed=resp.status_code == 200,
            )
        )
    except Exception as e:
        user.actions.append(
            UserAction(action="edge:consent_marketing_off", passed=False, detail=str(e))
        )

    # Turn marketing back on
    try:
        resp = await client.post(
            f"{api_url}/gdpr/consent",
            json={"consent_type": "marketing_email", "granted": True, "version": "1.0"},
            headers=user.auth_headers(),
        )
        user.actions.append(
            UserAction(
                action="edge:consent_marketing_on",
                endpoint="/gdpr/consent",
                method="POST",
                status_code=resp.status_code,
                passed=resp.status_code == 200,
            )
        )
    except Exception as e:
        user.actions.append(
            UserAction(action="edge:consent_marketing_on", passed=False, detail=str(e))
        )

    # Verify consent state
    try:
        resp = await client.get(f"{api_url}/gdpr/consent", headers=user.auth_headers())
        if resp.status_code == 200:
            consents = resp.json().get("consents", [])
            marketing = next(
                (c for c in consents if c.get("consent_type") == "marketing_email"),
                None,
            )
            user.actions.append(
                UserAction(
                    action="edge:consent_verify",
                    endpoint="/gdpr/consent",
                    method="GET",
                    status_code=200,
                    passed=marketing is not None and marketing.get("granted") is True,
                    detail=f"marketing_granted={marketing.get('granted') if marketing else 'missing'}",
                )
            )
    except Exception as e:
        user.actions.append(
            UserAction(action="edge:consent_verify", passed=False, detail=str(e))
        )


async def _edge_relogin(client: httpx.AsyncClient, api_url: str, user: SimUser) -> None:
    """Re-login a user and update their token/csrf."""
    try:
        resp = await client.post(
            f"{api_url}/auth/login",
            json={"email": user.email, "password": user.password},
            headers={"User-Agent": user.agent.raw},
        )
        if resp.status_code == 200:
            data = resp.json()
            user.token = data["access_token"]
            user.csrf = data.get("csrf_token", "")
            user.actions.append(
                UserAction(
                    action="edge:relogin",
                    endpoint="/auth/login",
                    method="POST",
                    status_code=200,
                    passed=True,
                )
            )
        else:
            user.actions.append(
                UserAction(
                    action="edge:relogin",
                    endpoint="/auth/login",
                    method="POST",
                    status_code=resp.status_code,
                    passed=False,
                    detail=resp.text[:200],
                )
            )
    except Exception as e:
        user.actions.append(
            UserAction(action="edge:relogin", passed=False, detail=str(e))
        )


async def _run_edge_cases(
    client: httpx.AsyncClient,
    api_url: str,
    users: list["SimUser"],
) -> None:
    """Run edge case journeys on a subset of users."""
    assignments = _assign_edge_cases(users)

    edge_funcs = {
        "re_register": _edge_re_register,
        "wrong_password": _edge_wrong_password,
        "forgot_password": _edge_forgot_password,
        "profile_update": _edge_profile_update,
        "consent_toggle": _edge_consent_toggle,
    }

    tasks = []
    for case_name, case_users in assignments.items():
        func = edge_funcs[case_name]
        for u in case_users:
            logger.info(
                "Edge case %s → user %03d (%s)",
                case_name,
                u.index,
                u.email,
            )
            tasks.append(func(client, api_url, u))

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    # Verify all edge-case users end up authenticated (back on dashboard)
    for case_users in assignments.values():
        for u in case_users:
            try:
                resp = await client.get(f"{api_url}/auth/me", headers=u.auth_headers())
                u.actions.append(
                    UserAction(
                        action="edge:final_auth_check",
                        endpoint="/auth/me",
                        method="GET",
                        status_code=resp.status_code,
                        passed=resp.status_code == 200,
                    )
                )
            except Exception as e:
                u.actions.append(
                    UserAction(
                        action="edge:final_auth_check",
                        passed=False,
                        detail=str(e),
                    )
                )


async def _run_user_journey(
    client: httpx.AsyncClient,
    api_url: str,
    db_url: str,
    user: SimUser,
    catalog: list[dict],
    categories: list[dict],
) -> SimUser:
    """Execute a full user journey."""
    # Register
    if not await _register_user(client, api_url, user):
        return user

    # Grant GDPR consent
    await _grant_consent(client, api_url, user, db_url)

    # Session events (login, consent)
    await _session_events(client, api_url, user)

    # Browse products
    await _browse_products(client, api_url, user, catalog)

    # Cart operations
    await _cart_operations(client, api_url, user, catalog)

    # Wishlist
    await _wishlist_operations(client, api_url, user)

    # Checkout
    await _checkout_flow(client, api_url, user)

    # Coupon events (for power buyers)
    if user.persona.uses_coupon:
        await _track_event(client, api_url, user, "coupon_failed", {"code": "FAKECODE"})

    # Logout (some users)
    if random.random() < 0.3:
        await _track_event(client, api_url, user, "logout")

    return user


async def run(
    api_url: str,
    db_url: str,
    user_count: int,
    user_password: str,
    catalog: list[dict],
    categories: list[dict],
    email_pattern: str = "sim{num:03d}@test.com",
) -> list[SimUser]:
    """Run all user simulations concurrently.

    Returns list of SimUser objects with complete action logs.
    """
    # Assign personas
    personas = assign_personas(user_count)
    inject_declines(personas)

    # Create user objects
    users: list[SimUser] = []
    for i, persona in enumerate(personas):
        # Assign device type: 72% desktop, 23% mobile, 5% tablet
        r = random.random()
        if r < 0.72:
            agent = random.choice(DESKTOP_AGENTS)
        elif r < 0.95:
            agent = random.choice(MOBILE_AGENTS)
        else:
            agent = random.choice(TABLET_AGENTS)

        users.append(
            SimUser(
                index=i + 1,
                email=email_pattern.format(num=i + 1),
                password=user_password,
                persona=persona,
                agent=agent,
                referrer=random.choice(REFERRERS),
            )
        )

    # Run journeys concurrently in batches of 20 to avoid overwhelming the server
    batch_size = 20
    completed_users: list[SimUser] = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        for batch_start in range(0, len(users), batch_size):
            batch = users[batch_start : batch_start + batch_size]
            tasks = [
                _run_user_journey(client, api_url, db_url, user, catalog, categories)
                for user in batch
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, SimUser):
                    completed_users.append(result)
                    status = "PASS" if result.result == "PASS" else "FAIL"
                    logger.info(
                        "User %03d (%s): %s — %d actions",
                        result.index,
                        result.persona.name,
                        status,
                        len(result.actions),
                    )
                else:
                    logger.error("User journey exception: %s", result)

        # Run edge case journeys on ~11 random users
        logger.info("Running edge case journeys on subset of users...")
        await _run_edge_cases(client, api_url, completed_users)
        logger.info("Edge case journeys complete")

    return completed_users
