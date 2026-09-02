"""共享测试夹具：无真实模型时的默认配置 + Phase 2 临时数据库。"""
from __future__ import annotations

import gc
import tempfile
from pathlib import Path

import pytest

from app.config import Settings
from app.db.session import Database
from app.itsm.service import ITSMService


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


@pytest.fixture()
def database() -> Database:
    """临时文件数据库（多 session 共享；:memory: 在多连接下不共享，故用文件）。"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db = Database(f"sqlite:///{tmp.name}")
    db.create_all()
    yield db
    db.engine.dispose()
    gc.collect()
    try:
        Path(tmp.name).unlink(missing_ok=True)
    except PermissionError:
        pass  # Windows 句柄延迟释放时容忍
    Path(tmp.name).unlink(missing_ok=True)


@pytest.fixture()
def itsm() -> ITSMService:
    return ITSMService(autoheal_high_risk_requires_approval=True)
