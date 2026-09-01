"""模型后端抽象与统一响应结构。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str  # system | user | assistant
    content: str


class ModelResponse(BaseModel):
    model_id: str
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    cached: bool = False
    raw: dict | None = None


@dataclass
class ModelBackend(ABC):
    """模型后端基类。子类实现 chat()。"""

    id: str
    kind: str = "generic"
    input_price_per_mtok: float = 0.0
    output_price_per_mtok: float = 0.0
    enabled: bool = True
    available: bool = True
    stats: dict = field(default_factory=lambda: {"calls": 0, "errors": 0})

    @abstractmethod
    def chat(self, messages: list[ChatMessage], temperature: float = 0.0) -> ModelResponse:
        """执行一次对话补全。失败必须抛异常，由 Router 负责降级。"""

    @property
    def cost(self) -> float:
        """统计口径：调用总成本（美元）。"""
        return self.stats.get("input_tokens", 0) / 1e6 * self.input_price_per_mtok + \
            self.stats.get("output_tokens", 0) / 1e6 * self.output_price_per_mtok
