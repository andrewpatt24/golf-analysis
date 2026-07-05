"""Capture R-Cloud JWT via headless browser (local development only)."""

from __future__ import annotations

import re
from typing import Callable

from golf_analysis.local_auth.repo_secrets import (
    LocalAuthError,
    RapsodoLoginCredentials,
    normalize_bearer_token,
)

RAPSODO_APP_URL = "https://golf-cloud.rapsodo.com/"
MLM_HOST = "mlm.rapsodo.com"
_JWT_RE = re.compile(r"^JWT\s+(\S+)", re.I)
_BEARER_RE = re.compile(r"^Bearer\s+(\S+)", re.I)


def _extract_token_from_auth_header(value: str) -> str | None:
    v = value.strip()
    m = _JWT_RE.match(v)
    if m:
        return normalize_bearer_token(m.group(1))
    m = _BEARER_RE.match(v)
    if m:
        return normalize_bearer_token(m.group(1))
    if v.startswith("eyJ"):
        return normalize_bearer_token(v)
    return None


def _collect_storage_tokens(page: object) -> list[str]:
    script = """
    () => {
      const out = [];
      for (const store of [localStorage, sessionStorage]) {
        for (let i = 0; i < store.length; i++) {
          const v = store.getItem(store.key(i));
          if (v && /^eyJ[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+/.test(v)) out.push(v);
        }
      }
      return out;
    }
    """
    try:
        raw = page.evaluate(script)  # type: ignore[attr-defined]
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    return [normalize_bearer_token(str(x)) for x in raw if x]


def login_rapsodo_via_playwright(
    creds: RapsodoLoginCredentials,
    *,
    headless: bool = True,
    timeout_ms: int = 120_000,
) -> str:
    """
    Log into R-Cloud and return a raw JWT suitable for ``Authorization: JWT …``.

    Raises ``LocalAuthError`` on failure (including missing Playwright browsers).
    """

    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeout
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise LocalAuthError(
            "Playwright is not installed. Run: uv sync --group local-auth && playwright install chromium"
        ) from e

    captured: list[str] = []

    def remember(token: str | None) -> None:
        if token and token not in captured:
            captured.append(token)

    def on_request(request: object) -> None:
        url = getattr(request, "url", "")
        if MLM_HOST not in url:
            return
        headers = getattr(request, "headers", {}) or {}
        auth = headers.get("authorization") or headers.get("Authorization")
        if auth:
            remember(_extract_token_from_auth_header(str(auth)))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        try:
            page = browser.new_page()
            page.on("request", on_request)
            page.goto(RAPSODO_APP_URL, wait_until="domcontentloaded", timeout=timeout_ms)

            _fill_login_form(page, creds.email, creds.password, timeout_ms=timeout_ms)
            _submit_login(page, timeout_ms=timeout_ms)

            try:
                page.wait_for_url(re.compile(r"golf-cloud\.rapsodo\.com"), timeout=timeout_ms)
            except PlaywrightTimeout:
                pass

            deadline = timeout_ms
            for _ in range(40):
                if captured:
                    break
                for tok in _collect_storage_tokens(page):
                    remember(tok)
                if captured:
                    break
                page.wait_for_timeout(min(500, max(100, deadline // 80)))

            if not captured:
                raise LocalAuthError(
                    "Login finished but no JWT was captured. "
                    "Check email/password in secrets.json, or run: local-auth-login --no-headless"
                )
            return captured[-1]
        finally:
            browser.close()


def _fill_login_form(page: object, email: str, password: str, *, timeout_ms: int) -> None:
    email_locators: list[Callable[[], object]] = [
        lambda: page.get_by_label(re.compile(r"email", re.I)),  # type: ignore[attr-defined]
        lambda: page.locator('input[type="email"]'),
        lambda: page.locator('input[name*="email" i]'),
        lambda: page.locator('input[autocomplete="username"]'),
    ]
    password_locators = [
        lambda: page.get_by_label(re.compile(r"password", re.I)),
        lambda: page.locator('input[type="password"]'),
        lambda: page.locator('input[name*="password" i]'),
    ]

    if not _fill_first(page, email_locators, email, timeout_ms=timeout_ms):
        raise LocalAuthError("Could not find R-Cloud email field on login page")
    if not _fill_first(page, password_locators, password, timeout_ms=timeout_ms):
        raise LocalAuthError("Could not find R-Cloud password field on login page")


def _fill_first(page: object, locators: list[Callable[[], object]], value: str, *, timeout_ms: int) -> bool:
    per = max(3000, timeout_ms // len(locators))
    for factory in locators:
        try:
            loc = factory()
            loc.wait_for(state="visible", timeout=per)  # type: ignore[attr-defined]
            loc.fill(value, timeout=per)  # type: ignore[attr-defined]
            return True
        except Exception:
            continue
    return False


def _submit_login(page: object, *, timeout_ms: int) -> None:
    candidates = [
        lambda: page.get_by_role("button", name=re.compile(r"log\s*in|sign\s*in", re.I)),
        lambda: page.locator('button[type="submit"]'),
        lambda: page.locator('input[type="submit"]'),
    ]
    for factory in candidates:
        try:
            btn = factory()
            btn.click(timeout=timeout_ms // 3)  # type: ignore[attr-defined]
            return
        except Exception:
            continue
    page.keyboard.press("Enter")  # type: ignore[attr-defined]
