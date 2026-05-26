"""Optional shared-secret gate for Cloud Run deployments."""

from __future__ import annotations

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

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


def _is_public_static(path: str) -> bool:
    """Built UI assets are not secret; API routes remain gated."""
    if path.startswith(_STATIC_PREFIXES):
        return True
    if path in _STATIC_EXACT:
        return True
    return any(path.endswith(suffix) for suffix in _STATIC_SUFFIXES)


class AccessTokenMiddleware(BaseHTTPMiddleware):
    """Require ``GOLF_ACCESS_TOKEN`` via Bearer header, ``?token=``, or session cookie."""

    async def dispatch(self, request: Request, call_next) -> Response:
        expected = os.environ.get("GOLF_ACCESS_TOKEN", "").strip()
        if not expected:
            return await call_next(request)

        if request.url.path == "/api/v1/health":
            return await call_next(request)

        if _is_public_static(request.url.path):
            return await call_next(request)

        auth = request.headers.get("authorization") or ""
        query_token = request.query_params.get("token")
        cookie_token = request.cookies.get(COOKIE_NAME)

        if auth == f"Bearer {expected}":
            return await call_next(request)
        if query_token == expected or cookie_token == expected:
            response = await call_next(request)
            if query_token == expected and cookie_token != expected:
                response.set_cookie(
                    COOKIE_NAME,
                    expected,
                    httponly=True,
                    secure=request.url.scheme == "https",
                    samesite="lax",
                    max_age=COOKIE_MAX_AGE,
                )
            return response

        return JSONResponse(
            status_code=401,
            content={"detail": "Missing or invalid access token"},
        )
