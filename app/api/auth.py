"""入口与后台登录：长 token 换 Cookie；口令用 HMAC Cookie，不落明文。"""

from __future__ import annotations

import hmac
import threading
import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from app.api.deps import (
    OWNER_COOKIE,
    SESSION_COOKIE,
    SESSION_MAX_AGE,
    get_ctx,
    owner_token,
    require_owner,
)
from app.api.pages import bad_token_page
from app.api.schemas import LoginIn, LoginOut

router = APIRouter()

_COOKIE_MAX_AGE = SESSION_MAX_AGE
_WINDOW = 60.0
_LIMIT = 5
_failures: dict[str, list[float]] = {}
_lock = threading.Lock()


def _too_many(host: str) -> bool:
    with _lock:
        now = time.monotonic()
        bucket = [t for t in _failures.get(host, []) if now - t < _WINDOW]
        _failures[host] = bucket
        return len(bucket) >= _LIMIT


def _record_failure(host: str) -> None:
    with _lock:
        _failures.setdefault(host, []).append(time.monotonic())


@router.get("/c/{token}", include_in_schema=False)
def enter(token: str, request: Request) -> Response:
    ctx = get_ctx(request)
    expected = ctx.settings.chat_token
    if not expected or not hmac.compare_digest(token, expected):
        return HTMLResponse(bad_token_page(), status_code=403)
    response = RedirectResponse("/", status_code=302)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )
    return response


@router.post("/api/owner/login", response_model=LoginOut)
def owner_login(payload: LoginIn, request: Request, response: Response) -> LoginOut:
    ctx = get_ctx(request)
    if not ctx.settings.owner_password:
        raise HTTPException(status_code=503, detail="owner password not configured")
    host = request.client.host if request.client else "unknown"
    if _too_many(host):
        raise HTTPException(status_code=429, detail="too many attempts")
    if not hmac.compare_digest(payload.password, ctx.settings.owner_password):
        _record_failure(host)
        raise HTTPException(status_code=401, detail="wrong password")
    response.set_cookie(
        OWNER_COOKIE,
        owner_token(ctx.settings),
        max_age=_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )
    return LoginOut(ok=True)


@router.get("/api/owner/session", response_model=LoginOut)
def owner_session(_: None = Depends(require_owner)) -> LoginOut:
    return LoginOut(ok=True)


@router.post("/api/owner/logout", response_model=LoginOut)
def owner_logout(response: Response, _: None = Depends(require_owner)) -> LoginOut:
    response.delete_cookie(OWNER_COOKIE, path="/")
    return LoginOut(ok=True)
