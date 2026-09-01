"""任务分类与多模型路由：按任务类型路由，失败自动降级，高频查询进程内缓存。"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from .base import ChatMessage, ModelBackend, ModelResponse


# ---- 任务分类（骨架版规则分类；后续可替换为模型分类）----
_TASK_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("sensitive", ("密码", "密钥", "token", "脱敏", "权限", "审计", "删除生产", "敏感")),
    ("code_gen", ("写代码", "代码", "脚本", "生成函数", "重构", "python 代码")),
    ("tool_call", ("执行", "调用工具", "安装", "重启", "启动", "停止", "查端口", "跑命令", "巡检", "部署", "升级")),
    ("complex_reasoning", ("为什么", "根因", "分析", "排查", "诊断", "对比", "设计", "如何修复")),
    ("simple_qa", ("是什么", "怎么用", "如何", "帮助", "介绍", "?", "？")),
]


def classify_task(user_input: str) -> str:
    """简单规则任务分类，返回 route_defaults 中的任务类别。"""
    for task, keywords in _TASK_RULES:
        if any(k in user_input for k in keywords):
            return task
    return "simple_qa"


# ---- 进程内 TTL 缓存（骨架阶段替代 Redis；高频查询命中）----
@dataclass
class _CacheEntry:
    expires_at: float
    response: ModelResponse


class TTLCache:
    def __init__(self, ttl_seconds: float = 300.0, max_entries: int = 256) -> None:
        self._ttl = ttl_seconds
        self._max = max_entries
        self._store: dict[str, _CacheEntry] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> ModelResponse | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if time.monotonic() > entry.expires_at:
                self._store.pop(key, None)
                return None
            return entry.response

    def set(self, key: str, response: ModelResponse) -> None:
        with self._lock:
            if len(self._store) >= self._max:
                # 简单淘汰：清掉已过期，若仍超限则清空最旧一半
                now = time.monotonic()
                expired = [k for k, v in self._store.items() if now > v.expires_at]
                for k in expired:
                    self._store.pop(k, None)
                if len(self._store) >= self._max:
                    for k in list(self._store)[: self._max // 2]:
                        self._store.pop(k, None)
            self._store[key] = _CacheEntry(time.monotonic() + self._ttl, response)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


class ModelRouter:
    """按任务分类选择模型；首选模型失败时按优先级降级，最终落到 mock。"""

    def __init__(
        self,
        backends: list[ModelBackend],
        route_defaults: dict[str, str],
        mock_fallback_enabled: bool = True,
        cache_ttl: float = 300.0,
    ) -> None:
        self._backends = {b.id: b for b in backends}
        self._route_defaults = route_defaults
        self._mock_fallback_enabled = mock_fallback_enabled
        self._cache = TTLCache(ttl_seconds=cache_ttl)
        self._order: list[str] = []
        self._rebuild_order()

    def _rebuild_order(self) -> None:
        """降级优先级：默认路由模型 -> 其余 enabled 模型 -> mock。"""
        preferred = [
            b.id for b in self._backends.values()
            if b.enabled and b.available and b.kind != "mock"
        ]
        mock_ids = [b.id for b in self._backends.values() if b.kind == "mock"]
        self._order = preferred + mock_ids

    def route(self, task: str) -> ModelBackend | None:
        """返回该任务当前应使用的模型后端（按降级优先级取第一个可用）。"""
        default_id = self._route_defaults.get(task, "mock")
        order = [default_id] if default_id in self._backends else []
        order += [b for b in self._order if b != default_id]
        for mid in order:
            b = self._backends.get(mid)
            if b and b.enabled and b.available:
                return b
        return None

    def chat(self, messages: list[ChatMessage], task: str | None = None,
             use_cache: bool = True, temperature: float = 0.0) -> ModelResponse:
        user_input = next((m.content for m in reversed(messages) if m.role == "user"), "")
        task = task or classify_task(user_input)
        cache_key = f"{task}|{user_input[:256]}"

        if use_cache:
            hit = self._cache.get(cache_key)
            if hit is not None:
                return hit

        backend = self.route(task)
        if backend is None:
            raise RuntimeError("no available model backend")

        try:
            resp = backend.chat(messages, temperature=temperature)
        except Exception as exc:  # noqa: BLE001 - 统一按"不可用"处理并降级
            backend.stats["errors"] += 1
            backend.available = False
            self._rebuild_order()
            fallback = self.route(task)
            if fallback is None or fallback is backend:
                raise RuntimeError(f"model {backend.id} failed and no fallback: {exc}") from exc
            resp = fallback.chat(messages, temperature=temperature)
            resp.model_id = f"{resp.model_id} (fallback from {backend.id})"

        if use_cache:
            self._cache.set(cache_key, resp)
        return resp

    @property
    def backends(self) -> list[ModelBackend]:
        return list(self._backends.values())
