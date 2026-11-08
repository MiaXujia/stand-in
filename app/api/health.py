"""健康检查：给容器编排与你自己看。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app import __version__
from app.api.deps import get_ctx
from app.api.schemas import HealthOut

router = APIRouter()


@router.get("/healthz", response_model=HealthOut)
def healthz(request: Request) -> HealthOut:
    ctx = get_ctx(request)
    try:
        with ctx.engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        db = "ok"
    except Exception as exc:  # noqa: BLE001
        db = f"error: {exc}"
    return HealthOut(ok=db == "ok", db=db, jobs=0, version=__version__)
