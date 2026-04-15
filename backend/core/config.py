"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    app_name: str = "BoilerplateApp"
    app_env: str = "development"
    debug: bool = True
    secret_key: str = "change-me-to-a-random-secret"

    # Domain
    domain: str = "localhost"
    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"
    public_url: str = ""  # Public-facing URL for assets (e.g. https://mysite.com). When empty, image URLs are not sent to payment providers.

    # Database
    database_url: str = "postgresql+asyncpg://boilerplate:change-me@postgres:5432/boilerplate_db"
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30

    # Redis
    redis_url: str = "redis://redis:6379/0"
    redis_pool_size: int = 10
    session_ttl: int = 604800
    cart_ttl: int = 86400
    rate_limit_window: int = 60

    # Auth
    jwt_secret: str = "change-me-to-a-long-random-string"
    jwt_algorithm: str = "HS256"
    jwt_expiry: int = 900
    refresh_token_ttl: int = 604800
    max_sessions_per_user: int = 5

    @property
    def jwt_issuer(self) -> str:
        return f"https://api.{self.domain}"

    @property
    def jwt_audience(self) -> str:
        return f"https://api.{self.domain}"

    # Currency
    default_currency: str = "USD"

    # Payments (Stripe)
    payment_provider: str = "stripe"
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    platform_fee_percent: int = 10

    # Module toggles
    enable_payments: bool = True
    enable_tracking: bool = True
    enable_chatbot: bool = False
    enable_marketing: bool = True
    enable_recommendations: bool = True
    app_template: str = "ecommerce"

    # Feature toggles (within ecommerce module)
    enable_products: bool = True
    enable_subscriptions: bool = True
    enable_coupons: bool = True

    # Tracking & Analytics
    tracking_session_timeout: int = 30  # minutes of inactivity
    geo_provider: str = "placeholder"
    tracking_exclude_paths: str = "/api/health,/api/docs,/api/openapi.json"

    # SEO
    site_name: str = "Boilerplate App"
    default_og_image: str = "/images/og-default.png"
    social_handles: str = ""
    sitemap_cache_ttl: int = 3600
    enable_seo_scoring: bool = True
    enable_seo_crawler: bool = False
    seo_rescore_interval: int = 86400

    # GDPR
    gdpr_grace_period_days: int = 30
    gdpr_export_expiry_days: int = 7

    # Checkout & Cart
    checkout_timeout: int = 60  # minutes before a processing order expires
    cart_abandon_timeout: int = 60
    recommendation_provider: str = "default"
    rfm_compute_schedule: str = "daily"

    # Email / Notifications
    email_provider: str = "placeholder"
    from_email: str = "noreply@localhost"
    from_name: str = "Boilerplate App"

    # Scaling
    uvicorn_workers: int = 2

    # Logging
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "case_sensitive": False, "extra": "ignore"}


settings = Settings()
