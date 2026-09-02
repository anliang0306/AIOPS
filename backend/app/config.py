"""全局配置（pydantic-settings）。

- 模型密钥一律通过环境变量 / .env 注入，不写入代码。
- 未配置任何模型密钥时，网关自动降级为 Mock 模型，保证 Demo 可离线跑通。
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelEndpoint(BaseSettings):
    """单个 OpenAI 兼容模型端点的配置。"""

    model_config = SettingsConfigDict(env_prefix="AIOPS_", env_nested_delimiter="__")

    id: str = ""            # 模型标识，如 gpt-4o / qwen2.5:7b
    base_url: str = ""      # OpenAI 兼容 base_url
    api_key: str = ""
    kind: Literal["cloud", "local", "mock"] = "cloud"
    # 单位：美元 / 百万 token（OpenAI 计费口径）；本地模型通常为 0
    input_price_per_mtok: float = 0.0
    output_price_per_mtok: float = 0.0
    enabled: bool = True


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="AIOPS_",
        extra="ignore",
    )

    app_name: str = "AIOps Platform"
    app_version: str = "0.1.0"

    # 模型端点列表：JSON 字符串，例如
    # AIOPS_MODEL_ENDPOINTS='[{"id":"qwen2.5:7b","base_url":"http://127.0.0.1:11434/v1","kind":"local","input_price_per_mtok":0,"output_price_per_mtok":0}]'
    model_endpoints: list[ModelEndpoint] = []

    # 未配置任何真实模型时是否启用 Mock 降级（默认启用，保证可离线运行）
    mock_fallback_enabled: bool = True
    # 任务分类 -> 默认模型路由表（可在环境变量中覆盖）
    route_defaults: dict[str, str] = {
        "simple_qa": "mock",        # 简单问答 -> 本地量化模型（骨架阶段默认 mock）
        "complex_reasoning": "mock",
        "tool_call": "mock",
        "code_gen": "mock",
        "sensitive": "mock",        # 敏感操作 -> 本地私有模型（骨架阶段默认 mock）
    }

    # 请求超时（秒）
    http_timeout_seconds: float = 60.0

    # ---- 数据持久化（Phase 2：SQLite + SQLAlchemy）----
    # SQLite 文件路径；":memory:" 可用于无状态测试/演示
    database_url: str = "sqlite:///./aiops.db"
    # 故障自愈 Agent 审批策略：流程驱动（工单式），HIGH 风险强制审批
    autoheal_high_risk_requires_approval: bool = True

    # 沙箱：允许的命令白名单前缀（骨架阶段；生产环境请切换为容器沙箱）
    sandbox_allowed_commands: list[str] = [
        "echo", "ls", "cat", "uname", "df", "free", "uptime", "whoami",
        "python --version", "pip --version", "git --version",
    ]
    sandbox_timeout_seconds: float = 30.0

    # RAG：骨架阶段使用进程内简化检索；预留向量库类型字段
    vector_store: Literal["in_memory", "chromadb", "milvus"] = "in_memory"
    rag_top_k: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()
