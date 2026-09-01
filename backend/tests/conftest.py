"""共享测试夹具：无真实模型时的默认配置。"""
from __future__ import annotations

import pytest

from app.config import Settings


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        model_endpoints=[],
        mock_fallback_enabled=True,
        route_defaults={
            "simple_qa": "mock",
            "complex_reasoning": "mock",
            "tool_call": "mock",
            "code_gen": "mock",
            "sensitive": "mock",
        },
        sandbox_allowed_commands=["echo", "ls", "cat", "python --version"],
    )
