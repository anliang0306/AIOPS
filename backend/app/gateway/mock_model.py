"""Mock 模型后端：未配置真实密钥时保证 Demo 可离线运行。

行为设计为"确定性"：返回固定模板 + 回显任务分类，便于测试路由逻辑。
"""
from __future__ import annotations

from .base import ChatMessage, ModelBackend, ModelResponse


class MockModelBackend(ModelBackend):
    def __init__(self, model_id: str = "mock") -> None:
        super().__init__(
            id=model_id,
            kind="mock",
            input_price_per_mtok=0.0,
            output_price_per_mtok=0.0,
        )

    def chat(self, messages: list[ChatMessage], temperature: float = 0.0) -> ModelResponse:
        self.stats["calls"] += 1
        self.stats.setdefault("input_tokens", 0)
        self.stats.setdefault("output_tokens", 0)
        user_msg = next((m.content for m in reversed(messages) if m.role == "user"), "")
        self.stats["input_tokens"] += len(user_msg) // 4
        self.stats["output_tokens"] += 16
        return ModelResponse(
            model_id=self.id,
            content=f"[mock] 收到请求（{len(messages)} 条消息）。摘要：{user_msg[:80]}",
            input_tokens=len(user_msg) // 4,
            output_tokens=16,
            raw={"mock": True},
        )
