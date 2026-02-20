"""Shared test fixtures: database, Stripe mocks, and user contexts.

Database strategy:
  - Session-scoped: create test DB, run migrations (sync psycopg2)
  - Function-scoped: each test gets a fresh async engine + session
    wrapped in a transaction that rolls back after the test

Stripe strategy:
  - All stripe.* SDK calls are mocked at the module level
  - Each mock returns sensible defaults from factories
  - Tests can override mock return values as needed
"""

import glob
import hashlib
import os
import uuid as _uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import psycopg2
import pytest
import pytest_asyncio
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def tid(label: str) -> str:
    """Generate a deterministic UUID from a short label for use in tests.

    This allows tests to use readable IDs like tid('p-sc1') instead of raw UUIDs
    while producing valid UUID values for PostgreSQL UUID columns.
    """
    h = hashlib.md5(label.encode()).hexdigest()
    return str(_uuid.UUID(h))

from tests.factories import (
    make_stripe_account,
    make_stripe_account_link,
    make_stripe_checkout_session,
    make_stripe_coupon,
    make_stripe_customer,
    make_stripe_login_link,
    make_stripe_payment_intent,
    make_stripe_price,
    make_stripe_product,
    make_stripe_promotion_code,
    make_stripe_refund,
    make_stripe_subscription,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_DB_NAME = "boilerplate_test_db"
PG_USER = "boilerplate"
PG_PASSWORD = "change-me"
PG_HOST = "localhost"
PG_PORT = 5432
PG_MAIN_DB = "boilerplate_db"

ASYNC_TEST_DB_URL = (
    f"postgresql+asyncpg://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{TEST_DB_NAME}"
)
SYNC_PG_DSN = f"dbname={PG_MAIN_DB} user={PG_USER} password={PG_PASSWORD} host={PG_HOST} port={PG_PORT}"

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


# ---------------------------------------------------------------------------
# Override app settings for tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True, scope="session")
def _override_settings():
    """Patch global settings for the entire test session."""
    from backend.core.config import settings

    original = {
        "stripe_secret_key": settings.stripe_secret_key,
        "stripe_publishable_key": settings.stripe_publishable_key,
        "stripe_webhook_secret": settings.stripe_webhook_secret,
        "database_url": settings.database_url,
    }
    settings.stripe_secret_key = "sk_test_fake_key_for_tests"
    settings.stripe_publishable_key = "pk_test_fake_key_for_tests"
    settings.stripe_webhook_secret = "whsec_test_secret_for_tests"
    settings.database_url = ASYNC_TEST_DB_URL
    yield
    for k, v in original.items():
        setattr(settings, k, v)


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------


def _create_test_db():
    """Create the test database using sync psycopg2 (CREATE DATABASE can't run in a transaction)."""
    conn = psycopg2.connect(SYNC_PG_DSN)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute(f"SELECT 1 FROM pg_database WHERE datname = '{TEST_DB_NAME}'")
    if not cur.fetchone():
        cur.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
    cur.close()
    conn.close()


def _drop_test_db():
    """Drop the test database."""
    conn = psycopg2.connect(SYNC_PG_DSN)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    # Terminate all connections to test DB
    cur.execute(
        f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        f"WHERE datname = '{TEST_DB_NAME}' AND pid <> pg_backend_pid()"
    )
    cur.execute(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}"')
    cur.close()
    conn.close()


def _run_migrations_sync():
    """Run all migration SQL files using sync psycopg2.

    Each file is split at '-- DOWN' to only run the UP portion.
    The UP portion is executed as a single statement to preserve
    $$ dollar-quoted functions.
    """
    dsn = f"dbname={TEST_DB_NAME} user={PG_USER} password={PG_PASSWORD} host={PG_HOST} port={PG_PORT}"
    conn = psycopg2.connect(dsn)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    migration_files = sorted(glob.glob(str(MIGRATIONS_DIR / "*.sql")))
    for mig_file in migration_files:
        sql = Path(mig_file).read_text()
        # Only run the UP portion (before "-- DOWN")
        up_sql = sql.split("-- DOWN")[0].strip()
        if up_sql:
            try:
                cur.execute(up_sql)
            except Exception as e:
                # Log but continue — some migrations may conflict
                import logging
                logging.getLogger(__name__).warning("Migration %s failed: %s", mig_file, e)
    cur.close()
    conn.close()


@pytest.fixture(scope="session", autouse=True)
def _setup_test_db():
    """Create test DB and run migrations once per session (sync)."""
    _create_test_db()
    _run_migrations_sync()
    yield
    # Don't drop — keep test DB for inspection; recreate next run anyway


@pytest_asyncio.fixture()
async def db():
    """Per-test database session with transaction rollback.

    Creates a fresh engine + connection per test to avoid event loop
    issues with pytest-asyncio. Uses NullPool to prevent connection reuse.
    The outer transaction is rolled back after the test for clean state.
    """
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(ASYNC_TEST_DB_URL, echo=False, poolclass=NullPool)

    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)

        async def _fake_commit():
            await session.flush()

        session.commit = _fake_commit

        yield session

        await session.close()
        await trans.rollback()

    await engine.dispose()


# ---------------------------------------------------------------------------
# Stripe mock fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_stripe():
    """Mock all Stripe SDK calls with sensible defaults.

    Returns a dict of all mock objects for tests to customize.
    Usage:
        def test_something(mock_stripe):
            mock_stripe["PaymentIntent"].create.return_value = custom_pi
    """
    mocks = {}

    patches = {
        "PaymentIntent.create": make_stripe_payment_intent(),
        "PaymentIntent.retrieve": make_stripe_payment_intent(status="succeeded"),
        "PaymentIntent.cancel": None,
        "PaymentIntent.list": MagicMock(data=[]),
        "Refund.create": make_stripe_refund(),
        "Customer.create": make_stripe_customer(),
        "Subscription.create": make_stripe_subscription(),
        "Subscription.modify": MagicMock(),
        "Subscription.cancel": MagicMock(),
        "Subscription.retrieve": make_stripe_subscription(status="active"),
        "Coupon.create": make_stripe_coupon(),
        "Coupon.delete": MagicMock(),
        "PromotionCode.create": make_stripe_promotion_code(),
        "Product.create": make_stripe_product(),
        "Product.modify": make_stripe_product(),
        "Price.create": make_stripe_price(),
        "Price.modify": MagicMock(),
        "checkout.Session.create": make_stripe_checkout_session(),
        "Account.create": make_stripe_account(),
        "Account.create_login_link": make_stripe_login_link(),
        "AccountLink.create": make_stripe_account_link(),
        "Webhook.construct_event": MagicMock(
            return_value={
                "id": "evt_test",
                "type": "payment_intent.succeeded",
                "data": {"object": {"id": "pi_test"}},
            }
        ),
    }

    active_patches = []
    for dotted_path, return_value in patches.items():
        p = patch(f"stripe.{dotted_path}", return_value=return_value)
        mock_obj = p.start()
        active_patches.append(p)

        # Store by last part of path for easy access
        # e.g. "PaymentIntent.create" -> mocks["PaymentIntent.create"]
        mocks[dotted_path] = mock_obj

        # Also store parent objects for convenience
        # e.g. "PaymentIntent" -> allows mocks["PaymentIntent"].create
        parent = dotted_path.split(".")[0]
        if parent not in mocks:
            mocks[parent] = MagicMock()

    yield mocks

    for p in active_patches:
        p.stop()


@pytest.fixture()
def stripe_provider():
    """Return a fresh StripeProvider instance."""
    from modules.payments.adapters.stripe_provider import StripeProvider

    return StripeProvider()


# ---------------------------------------------------------------------------
# User context fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_user():
    return {
        "user_id": "00000000-0000-4000-a000-000000000001",
        "role": "customer",
        "permissions": [],
        "session_id": "test-session-1",
        "auth_type": "jwt",
        "email": "testuser@example.com",
    }


@pytest.fixture()
def mock_admin():
    return {
        "user_id": "00000000-0000-4000-a000-000000000002",
        "role": "admin",
        "permissions": ["*"],
        "session_id": "test-session-admin",
        "auth_type": "jwt",
        "email": "admin@example.com",
    }


@pytest.fixture()
def mock_merchant():
    return {
        "user_id": "00000000-0000-4000-a000-000000000003",
        "role": "merchant",
        "permissions": [],
        "session_id": "test-session-merchant",
        "auth_type": "jwt",
        "email": "merchant@example.com",
    }


# ---------------------------------------------------------------------------
# DB seeding helpers
# ---------------------------------------------------------------------------


async def seed_user(db: AsyncSession, user_id: str, email: str, role: str = "customer") -> None:
    """Insert a minimal user + role for FK constraints."""
    # Ensure role exists
    await db.execute(
        text(
            "INSERT INTO core.roles (name, description) VALUES (:name, :desc) "
            "ON CONFLICT (name) DO NOTHING"
        ),
        {"name": role, "desc": f"{role} role"},
    )
    role_row = (
        await db.execute(
            text("SELECT id FROM core.roles WHERE name = :name"), {"name": role}
        )
    ).mappings().first()

    await db.execute(
        text(
            "INSERT INTO core.users (id, email, password_hash, role_id, is_active, is_verified) "
            "VALUES (:id, :email, 'fakehash', :rid, TRUE, TRUE) "
            "ON CONFLICT (id) DO NOTHING"
        ),
        {"id": user_id, "email": email, "rid": str(role_row["id"])},
    )
    await db.flush()


async def seed_product(db: AsyncSession, product: dict) -> dict:
    """Insert a product row and return it."""
    row = (
        await db.execute(
            text(
                "INSERT INTO ecommerce.products "
                "(id, name, slug, description, sku, base_price, currency, type, status, "
                " pricing_type, stripe_product_id, stripe_price_id, "
                " stripe_sync_status, synced_provider, "
                " recurring_interval, recurring_interval_count, trial_period_days) "
                "VALUES (:id, :name, :slug, :description, :sku, :base_price, :currency, :type, :status, "
                " :pricing_type, :stripe_product_id, :stripe_price_id, "
                " :stripe_sync_status, :synced_provider, "
                " :recurring_interval, :recurring_interval_count, :trial_period_days) "
                "RETURNING *"
            ),
            product,
        )
    ).mappings().first()
    await db.flush()
    return dict(row)


async def seed_variant(db: AsyncSession, variant: dict) -> dict:
    """Insert a product variant row."""
    row = (
        await db.execute(
            text(
                "INSERT INTO ecommerce.product_variants "
                "(id, product_id, name, sku, price_override, stock_quantity, "
                " stripe_price_id, stripe_sync_status) "
                "VALUES (:id, :product_id, :name, :sku, :price_override, :stock_quantity, "
                " :stripe_price_id, :stripe_sync_status) "
                "RETURNING *"
            ),
            variant,
        )
    ).mappings().first()
    await db.flush()
    return dict(row)


async def seed_cart_with_items(
    db: AsyncSession,
    user_id: str,
    items: list[dict],
) -> dict:
    """Create a cart with items. Each item dict needs product_id, variant_id, quantity."""
    cart_row = (
        await db.execute(
            text(
                "INSERT INTO ecommerce.cart (user_id, status) "
                "VALUES (:uid, 'active') RETURNING *"
            ),
            {"uid": user_id},
        )
    ).mappings().first()
    cart_id = str(cart_row["id"])

    for item in items:
        # Look up the product price for unit_price_at_add
        price_row = (await db.execute(
            text("SELECT base_price FROM ecommerce.products WHERE id = :pid"),
            {"pid": item["product_id"]},
        )).mappings().first()
        unit_price = item.get("unit_price", price_row["base_price"] if price_row else 0)
        await db.execute(
            text(
                "INSERT INTO ecommerce.cart_items (cart_id, product_id, variant_id, quantity, unit_price_at_add) "
                "VALUES (:cid, :pid, :vid, :qty, :price)"
            ),
            {
                "cid": cart_id,
                "pid": item["product_id"],
                "vid": item["variant_id"],
                "qty": item.get("quantity", 1),
                "price": unit_price,
            },
        )

    await db.flush()
    return dict(cart_row)


async def seed_order(db: AsyncSession, order: dict) -> dict:
    """Insert an order row."""
    row = (
        await db.execute(
            text(
                "INSERT INTO ecommerce.orders "
                "(id, user_id, order_number, status, subtotal, discount_amount, "
                " tax_amount, total, currency) "
                "VALUES (:id, :user_id, :order_number, :status, :subtotal, "
                " :discount_amount, :tax_amount, :total, :currency) "
                "RETURNING *"
            ),
            order,
        )
    ).mappings().first()
    await db.flush()
    return dict(row)


async def seed_payment_record(db: AsyncSession, record: dict) -> dict:
    """Insert a payment_records row."""
    row = (
        await db.execute(
            text(
                "INSERT INTO ecommerce.payment_records "
                "(order_id, provider, provider_payment_id, status, amount, currency, method) "
                "VALUES (:order_id, :provider, :provider_payment_id, :status, "
                " :amount, :currency, :method) "
                "RETURNING *"
            ),
            record,
        )
    ).mappings().first()
    await db.flush()
    return dict(row)


async def seed_discount(db: AsyncSession, discount: dict) -> dict:
    """Insert a discount_codes row."""
    row = (
        await db.execute(
            text(
                "INSERT INTO ecommerce.discount_codes "
                "(id, code, type, value, currency, min_order_amount, max_uses, "
                " uses_count, active, valid_from, valid_until, applies_to, "
                " stripe_coupon_id, stripe_promotion_code_id, "
                " stripe_duration, stripe_duration_in_months) "
                "VALUES (:id, :code, :type, :value, :currency, :min_order_amount, :max_uses, "
                " :uses_count, :active, :valid_from, :valid_until, :applies_to, "
                " :stripe_coupon_id, :stripe_promotion_code_id, "
                " :stripe_duration, :stripe_duration_in_months) "
                "RETURNING *"
            ),
            discount,
        )
    ).mappings().first()
    await db.flush()
    return dict(row)


async def seed_subscription(db: AsyncSession, sub: dict) -> dict:
    """Insert a subscriptions row."""
    row = (
        await db.execute(
            text(
                "INSERT INTO ecommerce.subscriptions "
                "(id, user_id, product_id, variant_id, stripe_subscription_id, "
                " stripe_customer_id, status, current_period_start, current_period_end, "
                " trial_start, trial_end, cancel_at_period_end, canceled_at, discount_code_id) "
                "VALUES (:id, :user_id, :product_id, :variant_id, :stripe_subscription_id, "
                " :stripe_customer_id, :status, :current_period_start, :current_period_end, "
                " :trial_start, :trial_end, :cancel_at_period_end, :canceled_at, :discount_code_id) "
                "RETURNING *"
            ),
            sub,
        )
    ).mappings().first()
    await db.flush()
    return dict(row)


async def seed_merchant(db: AsyncSession, merchant: dict) -> dict:
    """Insert a merchant_accounts row."""
    row = (
        await db.execute(
            text(
                "INSERT INTO ecommerce.merchant_accounts "
                "(user_id, stripe_account_id, status, charges_enabled, payouts_enabled, business_name) "
                "VALUES (:user_id, :stripe_account_id, :status, :charges_enabled, "
                " :payouts_enabled, :business_name) "
                "RETURNING *"
            ),
            merchant,
        )
    ).mappings().first()
    await db.flush()
    return dict(row)


async def seed_stripe_customer(db: AsyncSession, user_id: str, stripe_customer_id: str) -> None:
    """Insert a stripe_customers row."""
    await db.execute(
        text(
            "INSERT INTO ecommerce.stripe_customers (user_id, stripe_customer_id) "
            "VALUES (:uid, :cid) ON CONFLICT (user_id) DO NOTHING"
        ),
        {"uid": user_id, "cid": stripe_customer_id},
    )
    await db.flush()
