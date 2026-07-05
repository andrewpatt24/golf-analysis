"""Optional shared-secret gate for Cloud Run deployments."""

from __future__ import annotations

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from golf_analysis.api.access_tokens_store import guest_token_values
from golf_analysis.local_auth.runtime import is_cloud_runtime

COOKIE_NAME = "golf_access_token"
COOKIE_MAX_AGE = 60 * 60 * 24 * 365  # 1 year

_STATIC_PREFIXES = ("/assets/",)
_STATIC_EXACT = frozenset({"/manifest.webmanifest", "/favicon.ico"})
_STATIC_SUFFIXES = (
    ".js",
    ".css",
    ".map",
    ".woff",
    ".woff2",
    ".png",
    ".svg",
    ".ico",
    ".webmanifest",
)


def valid_access_tokens() -> frozenset[str]:
    """Primary env token, optional comma-separated extras, and revocable guest file."""

    tokens: set[str] = set()
    primary = os.environ.get("GOLF_ACCESS_TOKEN", "").strip()
    if primary:
        tokens.add(primary)
    extra = os.environ.get("GOLF_ACCESS_TOKENS", "")
    for part in extra.split(","):
        part = part.strip()
        if part:
            tokens.add(part)
    tokens.update(guest_token_values())
    return frozenset(tokens)


def access_gate_enabled() -> bool:
    """Enforce tokens on Cloud Run; skip locally unless explicitly testing auth."""

    if not valid_access_tokens():
        return False
    if is_cloud_runtime():
        return True
    flag = os.environ.get("GOLF_REQUIRE_ACCESS_TOKEN", "").strip().lower()
    return flag in ("1", "true", "yes", "on")


def _is_public_static(path: str) -> bool:
    """Built UI assets are not secret; API routes remain gated."""
    if path.startswith(_STATIC_PREFIXES):
        return True
    if path in _STATIC_EXACT:
        return True
    return any(path.endswith(suffix) for suffix in _STATIC_SUFFIXES)


def _bearer_token(authorization: str) -> str | None:
    if authorization.startswith("Bearer "):
        return authorization[7:].strip() or None
    return None


def _token_allowed(token: str | None, valid: frozenset[str]) -> bool:
    return bool(token and token in valid)


class AccessTokenMiddleware(BaseHTTPMiddleware):
    """Require a valid access token via Bearer header, ``?token=``, or session cookie."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if not access_gate_enabled():
            return await call_next(request)

        valid = valid_access_tokens()

        if request.url.path == "/api/v1/health":
            return await call_next(request)

        if _is_public_static(request.url.path):
            return await call_next(request)

        auth = request.headers.get("authorization") or ""
        query_token = request.query_params.get("token")
        cookie_token = request.cookies.get(COOKIE_NAME)
        bearer = _bearer_token(auth)

        matched = next(
            (t for t in (bearer, query_token, cookie_token) if _token_allowed(t, valid)),
            None,
        )
        if matched is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid access token"},
            )

        response = await call_next(request)
        if _token_allowed(query_token, valid) and cookie_token != query_token:
            response.set_cookie(
                COOKIE_NAME,
                query_token,
                httponly=True,
                secure=request.url.scheme == "https",
                samesite="lax",
                max_age=COOKIE_MAX_AGE,
            )
        return response
