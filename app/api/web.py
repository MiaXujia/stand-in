"""静态资源：web/dist 由后端托管。根路径不能挂 StaticFiles，否则绕过 Cookie。"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response

from app.api.deps import SESSION_COOKIE, SESSION_MAX_AGE, get_ctx, require_session
from app.api.pages import need_token_page

router = APIRouter()

_LOCAL_HOSTS = {"127.0.0.1", "::1", "::ffff:127.0.0.1"}

_MISSING = (
    "<!doctype html><meta charset='utf-8'>"
    "<h1>前端还没构建</h1>"
    "<p>在仓库根目录跑 <code>pnpm -C web install &amp;&amp; pnpm -C web build</code>，"
    "或者开发时用 <code>pnpm -C web dev</code>。</p>"
)


def _dist(request: Request) -> Path:
    return get_ctx(request).settings.web_dist_path


def _asset(request: Request, name: str, media_type: str | None = None) -> Response:
    path = _dist(request) / name
    if not path.exists():
        return Response(status_code=404)
    return FileResponse(path, media_type=media_type)


def _local_auto_login(request: Request) -> Response | None:
    """本机直连时免 token（经过反代、或从局域网访问，仍然要链接）。"""
    ctx = get_ctx(request)
    if not ctx.settings.local_auto_login or not ctx.settings.chat_token:
        return None
    if request.headers.get("x-forwarded-for") or request.headers.get("x-real-ip"):
        return None
    host = request.client.host if request.client else ""
    if host not in _LOCAL_HOSTS:
        return None
    response = RedirectResponse("/", status_code=302)
    response.set_cookie(
        SESSION_COOKIE,
        ctx.settings.chat_token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )
    return response


@router.get("/", include_in_schema=False)
def index(request: Request) -> Response:
    try:
        require_session(request)
    except HTTPException:
        auto = _local_auto_login(request)
        if auto is not None:
            return auto
        return HTMLResponse(need_token_page(), status_code=401)
    path = _dist(request) / "index.html"
    if not path.exists():
        return HTMLResponse(_MISSING, status_code=503)
    return FileResponse(path, headers={"Cache-Control": "no-store"})


@router.get("/sw.js", include_in_schema=False)
def service_worker(request: Request) -> Response:
    return _asset(request, "sw.js", "application/javascript")


@router.get("/manifest.webmanifest", include_in_schema=False)
def manifest(request: Request) -> Response:
    return _asset(request, "manifest.webmanifest", "application/manifest+json")


@router.get("/favicon.svg", include_in_schema=False)
def favicon(request: Request) -> Response:
    return _asset(request, "favicon.svg", "image/svg+xml")


@router.get("/favicon.ico", include_in_schema=False)
def favicon_ico() -> Response:
    # 图标走 /favicon.svg；这里只负责让浏览器别再报 404
    return Response(status_code=204)


@router.get("/registerSW.js", include_in_schema=False)
def register_sw(request: Request) -> Response:
    return _asset(request, "registerSW.js", "application/javascript")


@router.get("/workbox-{name}.js", include_in_schema=False)
def workbox(name: str, request: Request) -> Response:
    if not name.replace("-", "").isalnum():
        return Response(status_code=404)
    return _asset(request, f"workbox-{name}.js", "application/javascript")
