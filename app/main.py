"""应用装配：唯一把 adapters / services / api 接起来的地方。"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import auth, chat, health, web
from app.api.csrf import CsrfMiddleware
from app.context import build_context
from app.settings import Settings, get_settings

log = logging.getLogger("stand_in")


def _error(status: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status, content={"error": {"code": status, "message": message}}
    )


def _configure_logging(level: str) -> None:
    resolved = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(level=resolved, format="%(levelname)s:     %(message)s")
    log.setLevel(resolved)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    _configure_logging(settings.log_level)
    ctx = build_context(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        card = ctx.persona.load()
        if card.missing:
            log.warning("人格卡还有 %d 处未填：%s", len(card.missing), "、".join(card.missing))
        if not card.fewshots:
            log.warning("缺少 persona/fewshot.jsonl：少样本段会是空的")
        if settings.use_fake_model:
            log.warning(
                "LLM_PROVIDER=%s：当前是假模型，只用于跑通流程", settings.llm_provider
            )
        if not settings.chat_token:
            log.error("CHAT_TOKEN 为空：先跑 python -m app.bootstrap")
        else:
            log.info("聊天入口已配置；入口链接只由本地 bootstrap 命令显示")
        yield

    app = FastAPI(
        title="stand-in",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.ctx = ctx
    app.add_middleware(CsrfMiddleware)

    if settings.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.allowed_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "X-Stand-In"],
        )

    @app.exception_handler(HTTPException)
    async def _http_error(_: Request, exc: HTTPException) -> JSONResponse:
        return _error(exc.status_code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, __: RequestValidationError) -> JSONResponse:
        return _error(422, "invalid request")

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(chat.router)
    app.include_router(web.router)

    assets = settings.web_dist_path / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")
    icons = settings.web_dist_path / "icons"
    if icons.is_dir():
        app.mount("/icons", StaticFiles(directory=icons), name="icons")

    return app
