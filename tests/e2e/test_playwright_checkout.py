"""Playwright browser tests for Stripe checkout flow.

These tests require:
1. The full app stack running (docker-compose up)
2. Real Stripe test API keys configured
3. Playwright installed: pip install playwright && playwright install chromium

Run with: pytest tests/e2e/test_playwright_checkout.py -m e2e --headed

The --headed flag shows the browser window so you can see the checkout flow.
Without it, tests run headless (invisible browser).

STRIPE TEST CARD: 4242 4242 4242 4242
Any future expiry, any CVC, any ZIP.
"""

import pytest

# Skip entire module if playwright is not installed
try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.slow,
    pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="Playwright not installed"),
]

# Base URL — override with PLAYWRIGHT_BASE_URL env var
BASE_URL = "http://localhost:3000"
STRIPE_TEST_CARD = "4242424242424242"
STRIPE_TEST_EXP = "12/30"
STRIPE_TEST_CVC = "123"
STRIPE_TEST_ZIP = "10001"


@pytest.fixture
async def browser_page():
    """Launch a Chromium browser and yield a page."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        yield page
        await browser.close()


class TestStripeCheckoutBrowser:
    @pytest.mark.skip(reason="Requires full app stack running with real Stripe keys")
    async def test_one_time_checkout_with_stripe_card(self, browser_page):
        """Full browser checkout: add to cart → checkout → enter card → confirm.

        This test navigates the real frontend, fills in Stripe Elements
        with the test card, and verifies the payment succeeds.
        """
        page = browser_page

        # 1. Navigate to a product page
        await page.goto(f"{BASE_URL}/products")
        await page.wait_for_selector("[data-testid='product-card']")

        # 2. Click "Add to Cart" on the first product
        await page.click("[data-testid='add-to-cart']:first-of-type")
        await page.wait_for_timeout(500)

        # 3. Go to checkout
        await page.goto(f"{BASE_URL}/checkout")
        await page.wait_for_selector("[data-testid='checkout-form']")

        # 4. Fill shipping address
        await page.fill("[name='line1']", "123 Test St")
        await page.fill("[name='city']", "New York")
        await page.fill("[name='postal_code']", "10001")
        await page.select_option("[name='country']", "US")

        # 5. Submit checkout to get payment intent
        await page.click("[data-testid='submit-checkout']")
        await page.wait_for_selector("[data-testid='stripe-elements']")

        # 6. Fill Stripe card element (inside iframe)
        stripe_frame = page.frame_locator("iframe[name*='__privateStripeFrame']").first
        await stripe_frame.locator("[name='cardnumber']").fill(STRIPE_TEST_CARD)
        await stripe_frame.locator("[name='exp-date']").fill(STRIPE_TEST_EXP)
        await stripe_frame.locator("[name='cvc']").fill(STRIPE_TEST_CVC)
        await stripe_frame.locator("[name='postal']").fill(STRIPE_TEST_ZIP)

        # 7. Confirm payment
        await page.click("[data-testid='confirm-payment']")

        # 8. Wait for success page
        await page.wait_for_url(f"{BASE_URL}/checkout/success*", timeout=15000)
        success_text = await page.text_content("[data-testid='order-confirmation']")
        assert "Order confirmed" in success_text or "Thank you" in success_text

    @pytest.mark.skip(reason="Requires full app stack running with real Stripe keys")
    async def test_subscription_checkout_redirects_to_stripe(self, browser_page):
        """Subscription checkout redirects to Stripe-hosted checkout page."""
        page = browser_page

        # Navigate to subscription product
        await page.goto(f"{BASE_URL}/pricing")
        await page.wait_for_selector("[data-testid='subscribe-button']")

        # Click subscribe
        await page.click("[data-testid='subscribe-button']:first-of-type")

        # Should redirect to Stripe Checkout
        await page.wait_for_url("*checkout.stripe.com*", timeout=10000)
        assert "checkout.stripe.com" in page.url

    @pytest.mark.skip(reason="Requires full app stack running with real Stripe keys")
    async def test_declined_card_shows_error(self, browser_page):
        """Using Stripe's decline test card shows an error message.

        Card 4000000000000002 is Stripe's "always decline" test card.
        """
        page = browser_page
        DECLINE_CARD = "4000000000000002"

        await page.goto(f"{BASE_URL}/checkout")
        await page.wait_for_selector("[data-testid='checkout-form']")

        # Fill minimal shipping
        await page.fill("[name='line1']", "1 Fail St")
        await page.fill("[name='city']", "NY")
        await page.fill("[name='postal_code']", "10001")
        await page.select_option("[name='country']", "US")

        await page.click("[data-testid='submit-checkout']")
        await page.wait_for_selector("[data-testid='stripe-elements']")

        # Fill declined card
        stripe_frame = page.frame_locator("iframe[name*='__privateStripeFrame']").first
        await stripe_frame.locator("[name='cardnumber']").fill(DECLINE_CARD)
        await stripe_frame.locator("[name='exp-date']").fill(STRIPE_TEST_EXP)
        await stripe_frame.locator("[name='cvc']").fill(STRIPE_TEST_CVC)

        await page.click("[data-testid='confirm-payment']")

        # Should show error
        error = await page.wait_for_selector("[data-testid='payment-error']", timeout=10000)
        error_text = await error.text_content()
        assert "declined" in error_text.lower() or "failed" in error_text.lower()
