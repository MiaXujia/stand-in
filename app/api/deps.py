"""鉴权依赖：她的入口 Cookie 与你的后台 Cookie 完全分开。"""

from __future__ import annotations

import hashlib
import hmac

from fastapi import HTTPException, Request

from app.context import AppContext
from app.settings import Settings

SESSION_COOKIE = "sid"
OWNER_COOKIE = "owner"
SESSION_MAX_AGE = 180 * 24 * 3600


def get_ctx(request: Request) -> AppContext:
    return request.app.state.ctx


def owner_token(settings: Settings) -> str:
    return hmac.new(
        settings.owner_password.encode("utf-8"), b"stand-in-owner-v1", hashlib.sha256
    ).hexdigest()


def require_session(request: Request) -> None:
    ctx = get_ctx(request)
    expected = ctx.settings.chat_token
    supplied = request.cookies.get(SESSION_COOKIE, "")
    if not expected or not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="unauthorized")


def require_owner(request: Request) -> None:
    ctx = get_ctx(request)
    if not ctx.settings.owner_password:
        raise HTTPException(status_code=503, detail="owner password not configured")
    supplied = request.cookies.get(OWNER_COOKIE, "")
    if not supplied or not hmac.compare_digest(supplied, owner_token(ctx.settings)):
        raise HTTPException(status_code=401, detail="unauthorized")
