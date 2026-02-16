"""Apple Sign-In OAuth provider adapter.

Apple uses a server-signed JWT (ES256) as the client_secret. The JWT is
generated from the private key downloaded from the Apple Developer portal.

Required env vars: APPLE_CLIENT_ID, APPLE_TEAM_ID, APPLE_KEY_ID, APPLE_CLIENT_SECRET (PEM key).
"""

import os
import time
from urllib.parse import urlencode

import httpx

from modules.auth.interfaces.auth_provider import AuthProvider, OAuthUserInfo

_AUTHORIZATION_ENDPOINT = "https://appleid.apple.com/auth/authorize"
_TOKEN_ENDPOINT = "https://appleid.apple.com/auth/token"
_JWKS_ENDPOINT = "https://appleid.apple.com/auth/keys"
_DEFAULT_SCOPES = "name email"
_CLIENT_SECRET_LIFETIME = 15777000  # ~6 months


class AppleAuthProvider(AuthProvider):

    def __init__(self) -> None:
        self._client_id = os.environ.get("APPLE_CLIENT_ID", "")
        self._team_id = os.environ.get("APPLE_TEAM_ID", "")
        self._key_id = os.environ.get("APPLE_KEY_ID", "")
        raw_key = os.environ.get("APPLE_CLIENT_SECRET", "")
        self._private_key = raw_key.replace("\\n", "\n")

    @property
    def name(self) -> str:
        return "apple"

    def _generate_client_secret(self) -> str:
        """Create a short-lived JWT signed with the Apple private key."""
        from jose import jwt as jose_jwt

        now = int(time.time())
        claims = {
            "iss": self._team_id,
            "iat": now,
            "exp": now + _CLIENT_SECRET_LIFETIME,
            "aud": "https://appleid.apple.com",
            "sub": self._client_id,
        }
        return jose_jwt.encode(
            claims, self._private_key, algorithm="ES256",
            headers={"kid": self._key_id},
        )

    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": _DEFAULT_SCOPES,
            "state": state,
            "response_mode": "form_post",
        }
        return f"{_AUTHORIZATION_ENDPOINT}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> dict:
        client_secret = self._generate_client_secret()
        payload = {
            "client_id": self._client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(_TOKEN_ENDPOINT, data=payload)
            resp.raise_for_status()
            return resp.json()

    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """Extract user info from Apple's id_token (no userinfo endpoint)."""
        from jose import jwt as jose_jwt

        # Apple embeds identity in the id_token
        claims = jose_jwt.decode(access_token, None, options={"verify_signature": False})

        return OAuthUserInfo(
            provider=self.name,
            provider_user_id=claims["sub"],
            email=claims.get("email", ""),
            first_name=None,
            last_name=None,
            avatar_url=None,
            email_verified=claims.get("email_verified", False),
        )
