"""Abstract base class for OAuth/OIDC providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class OAuthUserInfo:
    """Normalized user info returned by all OAuth providers."""
    provider: str
    provider_user_id: str
    email: str
    first_name: str | None = None
    last_name: str | None = None
    avatar_url: str | None = None
    email_verified: bool = False


class AuthProvider(ABC):
    """Interface contract for OAuth provider adapters."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'google', 'github')."""
        ...

    @abstractmethod
    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        """Return the URL to redirect the user to for OAuth consent."""
        ...

    @abstractmethod
    async def exchange_code(self, code: str, redirect_uri: str) -> dict:
        """Exchange the authorization code for tokens.

        Returns a dict with at least ``access_token``.
        """
        ...

    @abstractmethod
    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """Fetch user profile from the provider API."""
        ...
