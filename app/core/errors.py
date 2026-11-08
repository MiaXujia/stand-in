"""跨层共享的异常类型（放 core，避免 services import adapters）。"""

from __future__ import annotations


class LlmError(RuntimeError):
    """模型不可用：上层返回 503，绝不返回假回复。"""


class PersonaError(RuntimeError):
    """人格文件缺关键内容（例如反例集解析失败）。"""


class TurnConflict(RuntimeError):
    """同一客户端消息 ID 对应了不同输入，或属于旧版无回合记录的消息。"""


class TurnInProgress(RuntimeError):
    """回合已由另一个请求生成；调用方应查询状态。"""


class TurnFailed(RuntimeError):
    """该回合已失败；保留其最终失败事实。"""
