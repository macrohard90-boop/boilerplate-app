"""Microsoft / Azure AD OAuth2 provider adapter."""

import os
from urllib.parse import urlencode

import httpx

from modules.auth.interfaces.auth_provider import AuthProvider, OAuthUserInfo

_TENANT = "common"
_AUTHORIZATION_ENDPOINT = f"https://login.microsoftonline.com/{_TENANT}/oauth2/v2.0/authorize"
_TOKEN_ENDPOINT = f"https://login.microsoftonline.com/{_TENANT}/oauth2/v2.0/token"
_USERINFO_ENDPOINT = "https://graph.microsoft.com/v1.0/me"
_DEFAULT_SCOPES = "openid email profile User.Read"


class MicrosoftAuthProvider(AuthProvider):

    def __init__(self) -> None:
        self._client_id = os.environ.get("MICROSOFT_CLIENT_ID", "")
        self._client_secret = os.environ.get("MICROSOFT_CLIENT_SECRET", "")

    @property
    def name(self) -> str:
        return "microsoft"

    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": _DEFAULT_SCOPES,
            "state": state,
            "response_mode": "query",
        }
        return f"{_AUTHORIZATION_ENDPOINT}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> dict:
        payload = {
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "scope": _DEFAULT_SCOPES,
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(_TOKEN_ENDPOINT, data=payload)
            resp.raise_for_status()
            return resp.json()

    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(_USERINFO_ENDPOINT, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        return OAuthUserInfo(
            provider=self.name,
            provider_user_id=data["id"],
            email=data.get("mail") or data.get("userPrincipalName", ""),
            first_name=data.get("givenName"),
            last_name=data.get("surname"),
            avatar_url=None,
            email_verified=True,
        )
