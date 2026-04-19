"""GitHub OAuth provider adapter."""

import os
from urllib.parse import urlencode

import httpx

from modules.auth.interfaces.auth_provider import AuthProvider, OAuthUserInfo

_AUTHORIZATION_ENDPOINT = "https://github.com/login/oauth/authorize"
_TOKEN_ENDPOINT = "https://github.com/login/oauth/access_token"
_USERINFO_ENDPOINT = "https://api.github.com/user"
_EMAILS_ENDPOINT = "https://api.github.com/user/emails"
_DEFAULT_SCOPES = "read:user user:email"


class GitHubAuthProvider(AuthProvider):

    def __init__(self) -> None:
        self._client_id = os.environ.get("GITHUB_CLIENT_ID", "")
        self._client_secret = os.environ.get("GITHUB_CLIENT_SECRET", "")

    @property
    def name(self) -> str:
        return "github"

    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "scope": _DEFAULT_SCOPES,
            "state": state,
        }
        return f"{_AUTHORIZATION_ENDPOINT}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> dict:
        payload = {
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }
        headers = {"Accept": "application/json"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(_TOKEN_ENDPOINT, data=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()

    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(_USERINFO_ENDPOINT, headers=headers)
            resp.raise_for_status()
            profile = resp.json()

            email = profile.get("email") or ""
            email_verified = False

            resp_emails = await client.get(_EMAILS_ENDPOINT, headers=headers)
            if resp_emails.status_code == 200:
                for entry in resp_emails.json():
                    if entry.get("primary") and entry.get("verified"):
                        email = entry["email"]
                        email_verified = True
                        break

        full_name: str = profile.get("name") or ""
        parts = full_name.split(maxsplit=1)
        first_name = parts[0] if parts else None
        last_name = parts[1] if len(parts) > 1 else None

        return OAuthUserInfo(
            provider=self.name,
            provider_user_id=str(profile["id"]),
            email=email,
            first_name=first_name,
            last_name=last_name,
            avatar_url=profile.get("avatar_url"),
            email_verified=email_verified,
        )
