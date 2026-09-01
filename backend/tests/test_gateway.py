"""多模型网关：任务分类、路由、Mock 降级、缓存、成本统计。"""
from __future__ import annotations

from app.gateway.base import ChatMessage
from app.gateway.mock_model import MockModelBackend
from app.gateway.router import ModelRouter, classify_task
from app.gateway.usage import reset, snapshot


def test_classify_task() -> None:
    assert classify_task("帮我写一个 python 脚本") == "code_gen"
    assert classify_task("重启一下 nginx 服务") == "tool_call"
    assert classify_task("分析一下为什么接口变慢") == "complex_reasoning"
    assert classify_task("涉及生产密钥需要脱敏") == "sensitive"
    assert classify_task("什么是 SLA") == "simple_qa"


def test_router_uses_configured_model(settings) -> None:  # noqa: ANN001
    mr = ModelRouter(backends=[MockModelBackend("mock")],
                     route_defaults=settings.route_defaults)
    resp = mr.chat([ChatMessage(role="user", content="什么是 SLA")], task="simple_qa")
    assert resp.content.startswith("[mock]")


def test_router_fallback_on_error(settings) -> None:  # noqa: ANN001
    class BrokenBackend(MockModelBackend):
        def chat(self, messages, temperature=0.0):  # noqa: ANN001
            raise RuntimeError("boom")

    broken = BrokenBackend("broken")
    mr = ModelRouter(backends=[broken, MockModelBackend("mock")],
                     route_defaults={"simple_qa": "broken"},
                     mock_fallback_enabled=True)
    # 手动把 broken 设为优先（route_defaults 已指向它）
    resp = mr.chat([ChatMessage(role="user", content="hi")], task="simple_qa")
    assert "fallback" in resp.model_id
    assert broken.available is False


def test_router_cache_hit(settings) -> None:  # noqa: ANN001
    mock = MockModelBackend("mock")
    mr = ModelRouter(backends=[mock], route_defaults=settings.route_defaults)
    msg = [ChatMessage(role="user", content="相同问题")]
    mr.chat(msg, task="simple_qa")
    mr.chat(msg, task="simple_qa")
    assert mock.stats["calls"] == 1  # 第二次命中缓存


def test_usage_snapshot_and_reset(settings) -> None:  # noqa: ANN001
    mock = MockModelBackend("mock")
    mock.stats = {"calls": 3, "errors": 1, "input_tokens": 100, "output_tokens": 50}
    snap = snapshot([mock])
    assert snap["models"][0]["calls"] == 3
    assert snap["models"][0]["estimated_cost_usd"] == 0.0
    reset([mock])
    assert mock.stats["calls"] == 0
