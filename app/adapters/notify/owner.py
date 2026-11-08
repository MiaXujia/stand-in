"""给本人的通知：控制台 + 可选 webhook。只发不判，失败不影响主流程。"""

from __future__ import annotations

from collections.abc import Callable

import httpx

from app.core.models import DeliveryStatus


class OwnerNotifier:
    def __init__(self, *, webhook: str = "", sink: Callable[[str], None] | None = None) -> None:
        self._webhook = webhook.strip()
        self._sink = sink or print

    def notify(self, kind: str, text: str) -> DeliveryStatus:
        self._sink(f"[notify:{kind}]")
        if not self._webhook:
            return DeliveryStatus.PENDING
        try:
            httpx.post(
                self._webhook,
                json={"kind": kind, "text": text},
                timeout=5.0,
            ).raise_for_status()
        except httpx.HTTPStatusError:
            self._sink("[notify:failed] webhook rejected request")
            return DeliveryStatus.FAILED
        except httpx.RequestError:
            self._sink("[notify:unknown] webhook result unavailable")
            return DeliveryStatus.UNKNOWN
        return DeliveryStatus.ACCEPTED
