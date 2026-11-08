"""轻量 CSRF 防线：所有 /api 写请求必须带 X-Stand-In: 1（同源前端会自动带）。"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class CsrfMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:  # noqa: ANN001
        if (
            request.method in _WRITE_METHODS
            and request.url.path.startswith("/api/")
            and request.headers.get("x-stand-in") != "1"
        ):
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "code": "csrf",
                        "message": "missing X-Stand-In header",
                    }
                },
            )
        return await call_next(request)
