"""OAuth 2.1 resource-server auth for the hosted Channel Brains deployment.

ChatGPT plugins must authenticate users. This module turns the HTTP server into
an RFC 9728 protected resource backed by an external authorization server
(Auth0): it publishes ``/.well-known/oauth-protected-resource`` metadata and
validates bearer tokens against the issuer's JWKS.

Dual-path model:
- the operator's secret path (CHANNEL_BRAINS_HTTP_PATH) stays no-auth;
- the public ``/mcp`` path requires a valid bearer token when an issuer is
  configured, and the verified token subject becomes the per-user identity.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

import anyio
import jwt
from jwt import PyJWKClient
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

PROTECTED_RESOURCE_PATH = "/.well-known/oauth-protected-resource"

OPENAI_APPS_CHALLENGE_PATH = "/.well-known/openai-apps-challenge"

current_sub: ContextVar[str | None] = ContextVar("channel_brains_sub", default=None)


@dataclass(frozen=True)
class AuthConfig:
    issuer: str
    audience: str

    @property
    def jwks_url(self) -> str:
        return f"{self.issuer.rstrip('/')}/.well-known/jwks.json"


def load_auth_config() -> AuthConfig | None:
    from channel_brains_mcp.config import get_auth_audience, get_auth_issuer

    issuer = get_auth_issuer()
    if not issuer:
        return None
    return AuthConfig(issuer=issuer, audience=get_auth_audience())


def protected_resource_metadata(config: AuthConfig) -> dict[str, Any]:
    return {
        "resource": config.audience,
        "authorization_servers": [config.issuer.rstrip("/")],
        "scopes_supported": [],
        "resource_documentation": "https://github.com/Pu11en/channel-brains",
        "bearer_methods_supported": ["header"],
    }


class TokenValidator:
    """Validate RS256 bearer tokens issued for this resource.

    PyJWKClient caches signing keys and refreshes them when a token references
    an unknown kid; its blocking HTTP is confined to a worker thread.
    """

    def __init__(self, config: AuthConfig) -> None:
        self._config = config
        self._jwk_client = PyJWKClient(config.jwks_url, cache_keys=True, lifespan=43200)

    def _verify_sync(self, token: str) -> dict[str, Any] | None:
        try:
            signing_key = self._jwk_client.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self._config.audience,
                issuer=self._config.issuer,
                options={"require": ["exp", "iss", "sub", "aud"]},
            )
        except jwt.PyJWTError:
            return None
        return claims

    async def verify(self, token: str) -> dict[str, Any] | None:
        try:
            return await anyio.to_thread.run_sync(self._verify_sync, token)
        except Exception:
            return None


class BearerAuthMiddleware:
    """Require a valid bearer token on public paths; pass exempt paths through."""

    def __init__(self, app: ASGIApp, validator: TokenValidator, exempt_prefixes: tuple[str, ...]) -> None:
        self.app = app
        self._validator = validator
        self._exempt_prefixes = exempt_prefixes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path: str = scope.get("path", "")
        if (
            path
            in (
                PROTECTED_RESOURCE_PATH,
                OPENAI_APPS_CHALLENGE_PATH,
                "/demo.mp4",
                "/healthz",
                "/privacy",
                "/terms",
                "/",
            )
            or any(path.startswith(prefix) for prefix in self._exempt_prefixes)
        ):
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        authorization = headers.get("authorization", "")
        if not authorization.lower().startswith("bearer "):
            await self._reject(scope, receive, send, "missing bearer token")
            return
        claims = await self._validator.verify(authorization[7:].strip())
        if claims is None:
            await self._reject(scope, receive, send, "invalid or expired token")
            return
        scope.setdefault("state", {})
        scope["state"]["channel_brains_sub"] = str(claims.get("sub", ""))
        # Contextvars propagate into the request's task tree, so tool handlers
        # downstream of the transport can resolve the caller's identity.
        current_sub.set(str(claims.get("sub", "")) or None)
        await self.app(scope, receive, send)

    @staticmethod
    async def _reject(scope: Scope, receive: Receive, send: Send, error: str) -> None:
        response = JSONResponse(
            {"error": "invalid_token", "error_description": error},
            status_code=401,
            headers={"WWW-Authenticate": f'Bearer error="invalid_token", error_description="{error}"'},
        )
        await response(scope, receive, send)
