"""转接请求：先持久记录，再尝试通知，并返回可证实的投递状态。"""

from __future__ import annotations

from datetime import datetime

from app.core.models import DeliveryStatus
from app.ports import InboxRepo, Notifier


def status_reply(status: DeliveryStatus) -> str:
    if status is DeliveryStatus.ACCEPTED:
        return "通知服务已接收消息，但还不能确认他看到了。你也可以直接联系他。"
    if status is DeliveryStatus.FAILED:
        return "通知没能发出。请直接联系他。"
    if status is DeliveryStatus.UNKNOWN:
        return "通知结果暂时无法确认。请直接联系他。"
    return "我记下了你的请求，但还没有把消息发给他。请直接联系他。"


class HandoffService:
    def __init__(self, *, inbox: InboxRepo, notifier: Notifier) -> None:
        self._inbox = inbox
        self._notifier = notifier

    def request(self, kind: str, body: str, *, now: datetime) -> DeliveryStatus:
        message_id = self._inbox.add(kind=kind, body=body, now=now)
        try:
            status = self._notifier.notify(kind, body)
        except Exception:  # 外部适配器异常不能被误报为送达
            status = DeliveryStatus.UNKNOWN
        try:
            self._inbox.set_delivery_status(message_id, status, now=now)
        except Exception:  # 已发出的 webhook 不能重试；保留 pending 回执
            return DeliveryStatus.UNKNOWN
        return status
