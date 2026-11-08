"""浏览器能看懂的提示页：直接开根地址、token 不对时，别只丢一串 JSON。"""

from __future__ import annotations

_STYLE = """
  :root { color-scheme: dark }
  body { margin: 0; min-height: 100vh; display: grid; place-items: center;
         background: #0b0d11; color: #e9edf4;
         font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif; }
  .box { max-width: 34rem; padding: 2rem; line-height: 1.75 }
  h1 { font-size: 1.2rem; margin: 0 0 .8rem }
  p { color: #aab3c4; margin: .5rem 0 }
  code { background: #161b23; padding: .15rem .45rem; border-radius: .35rem;
         color: #cfe0ff; font-size: .92em }
"""


def page(title: str, body: str) -> str:
    return (
        "<!doctype html><meta charset='utf-8'>"
        f"<title>{title}</title><style>{_STYLE}</style>"
        f"<div class='box'><h1>{title}</h1>{body}</div>"
    )


def need_token_page() -> str:
    return page(
        "这个地址不能直接打开",
        "<p>入口是一条带口令的链接，形如 <code>/c/&lt;token&gt;</code>。</p>"
        "<p>完整链接在启动日志里；也可以运行 "
        "<code>uv run python -m app.bootstrap</code> 查看。</p>",
    )


def bad_token_page() -> str:
    return page(
        "这条链接不对",
        "<p>口令无效或者已经换了新的。</p><p>向他要一条新的链接。</p>",
    )
