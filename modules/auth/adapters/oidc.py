"""Generic OpenID Connect (OIDC) provider adapter with auto-discovery.

Required env vars: OIDC_ISSUER_URL, OIDC_CLIENT_ID, OIDC_CLIENT_SECRET.
Optional: OIDC_SCOPES (default: "openid email profile").
"""

import os
from urllib.parse import urlencode

import httpx

from modules.auth.interfaces.auth_provider import AuthProvider, OAuthUserInfo

_DEFAULT_SCOPES = "openid email profile"


class OIDCAuthProvider(AuthProvider):

    def __init__(self) -> None:
        self._issuer_url = os.environ.get("OIDC_ISSUER_URL", "").rstrip("/")
        self._client_id = os.environ.get("OIDC_CLIENT_ID", "")
        self._client_secret = os.environ.get("OIDC_CLIENT_SECRET", "")
        self._scopes = os.environ.get("OIDC_SCOPES", _DEFAULT_SCOPES)
        self._discovery: dict | None = None

    @property
    def name(self) -> str:
        return "oidc"

    async def _discover(self) -> dict:
        if self._discovery is not None:
            return self._discovery
        url = f"{self._issuer_url}/.well-known/openid-configuration"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            self._discovery = resp.json()
        return self._discovery

    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        auth_endpoint = (
            self._discovery["authorization_endpoint"]
            if self._discovery
            else f"{self._issuer_url}/authorize"
        )
        params = {
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": self._scopes,
            "state": state,
        }
        return f"{auth_endpoint}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> dict:
        discovery = await self._discover()
        token_endpoint = discovery["token_endpoint"]
        payload = {
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(token_endpoint, data=payload)
            resp.raise_for_status()
            return resp.json()

    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        discovery = await self._discover()
        userinfo_endpoint = discovery["userinfo_endpoint"]
        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(userinfo_endpoint, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        return OAuthUserInfo(
            provider=self.name,
            provider_user_id=data.get("sub", ""),
            email=data.get("email", ""),
            first_name=data.get("given_name"),
            last_name=data.get("family_name"),
            avatar_url=data.get("picture"),
            email_verified=data.get("email_verified", False),
        )
