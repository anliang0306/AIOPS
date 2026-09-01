"""Token 消耗与成本统计（多模型网关侧）。

统计口径：调用次数、input/output tokens、估算成本（按模型单价）、错误数。
骨架阶段使用进程内统计；Phase 2 起落库并接预算告警。
"""
from __future__ import annotations

from .base import ModelBackend


def snapshot(backends: list[ModelBackend]) -> dict:
    rows = []
    for b in sorted(backends, key=lambda x: x.id):
        rows.append({
            "model_id": b.id,
            "kind": b.kind,
            "enabled": b.enabled,
            "available": b.available,
            "calls": b.stats.get("calls", 0),
            "errors": b.stats.get("errors", 0),
            "input_tokens": b.stats.get("input_tokens", 0),
            "output_tokens": b.stats.get("output_tokens", 0),
            "estimated_cost_usd": round(b.cost, 6),
            "input_price_per_mtok": b.input_price_per_mtok,
            "output_price_per_mtok": b.output_price_per_mtok,
        })
    total_cost = sum(b.cost for b in backends)
    return {"models": rows, "total_estimated_cost_usd": round(total_cost, 6)}


def reset(backends: list[ModelBackend]) -> None:
    for b in backends:
        b.stats = {"calls": 0, "errors": 0, "input_tokens": 0, "output_tokens": 0}
