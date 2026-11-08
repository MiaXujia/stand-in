"""开发/单机启动：起 uvicorn，并自动用浏览器打开带口令的入口链接。

  uv run python -m app.serve
  uv run python -m app.serve --port 8010 --no-open
"""

from __future__ import annotations

import argparse
import os
import threading
import webbrowser

import uvicorn

from app.settings import get_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.serve")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-open", action="store_true", help="不要自动打开浏览器")
    args = parser.parse_args(argv)

    base = f"http://{args.host}:{args.port}"
    os.environ["PUBLIC_URL"] = base  # 启动日志里的入口链接跟实际地址一致

    settings = get_settings()
    if settings.chat_token and not args.no_open:
        url = f"{base}/c/{settings.chat_token}"
        threading.Timer(2.0, lambda: webbrowser.open(url)).start()

    uvicorn.run(
        "app.main:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        workers=1,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
