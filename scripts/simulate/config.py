"""Simulation configuration — target URL, DB connection, Stripe, user count."""

import os
from dataclasses import dataclass, field


@dataclass
class SimConfig:
    """All simulation settings. Override via CLI flags or env vars."""

    # Target API
    target: str = "http://localhost"

    # Database (direct connection for reset + verify)
    db_host: str = ""
    db_port: int = 5432
    db_name: str = "boilerplate_db"
    db_user: str = "boilerplate"
    db_password: str = ""

    # Stripe
    stripe_secret_key: str = ""

    # Simulation parameters
    user_count: int = 100
    admin_email: str = "simadmin@test.com"
    admin_password: str = "Test1234!"
    user_email_pattern: str = "sim{num:03d}@test.com"
    user_password: str = "Test1234!"

    # Sections to run (empty = full)
    only_sections: list[str] = field(default_factory=list)

    # Report output
    report_dir: str = "reports"

    @property
    def api_url(self) -> str:
        return f"{self.target.rstrip('/')}/api"

    @classmethod
    def from_env(cls) -> "SimConfig":
        """Load config from environment variables."""
        return cls(
            db_host=os.getenv("DB_HOST", "localhost"),
            db_port=int(os.getenv("DB_PORT", "5432")),
            db_name=os.getenv("DB_NAME", "boilerplate_db"),
            db_user=os.getenv("DB_USER", "boilerplate"),
            db_password=os.getenv("DB_PASSWORD", ""),
            stripe_secret_key=os.getenv("STRIPE_SECRET_KEY", ""),
        )
