"""端到端 API 集成测试（TestClient，无真实模型，全程 Mock 降级）。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import build_app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(build_app())


def test_healthz(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}


def test_info(client: TestClient) -> None:
    data = client.get("/info").json()
    assert data["model_count"] >= 1
    assert data["tool_count"] >= 3
    assert data["agent_count"] >= 1


def test_models_list_and_chat(client: TestClient) -> None:
    models = client.get("/api/v1/models").json()["models"]
    assert any(m["kind"] == "mock" for m in models)

    r = client.post("/api/v1/models/chat", json={
        "messages": [{"role": "user", "content": "什么是 SLA"}],
        "task": "simple_qa",
    })
    assert r.status_code == 200
    assert r.json()["content"].startswith("[mock]")


def test_tools_list_and_execute(client: TestClient) -> None:
    tools = client.get("/api/v1/tools").json()["tools"]
    ids = {t["id"] for t in tools}
    assert "shell" in ids and "install_package" in ids

    # LOW 风险工具无需审批
    r = client.post("/api/v1/tools/execute", json={"tool_id": "shell", "params": {"command": "echo hi"}})
    assert r.status_code == 200
    assert "hi" in r.json()["output"]

    # MEDIUM 风险工具未审批 -> 403
    r = client.post("/api/v1/tools/execute", json={"tool_id": "install_package", "params": {"package": "git"}})
    assert r.status_code == 403

    # 审批通过 -> 200
    r = client.post("/api/v1/tools/execute", json={
        "tool_id": "install_package", "params": {"package": "git"}, "approved": True})
    assert r.status_code == 200
    assert r.json()["data"]["simulated"] is True


def test_agent_lifecycle_and_run(client: TestClient) -> None:
    aid = "env-install-agent"

    # 未启动 -> run 返回 not running（200，非 404）
    r = client.post(f"/api/v1/agents/{aid}/run", json={"payload": {"packages": ["git"]}})
    assert r.status_code == 200
    assert r.json()["ok"] is False

    client.post(f"/api/v1/agents/{aid}/start").raise_for_status()
    r = client.post(f"/api/v1/agents/{aid}/run", json={"payload": {"packages": ["python", "git"]}})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert "检查" in r.json()["summary"] or "安装" in r.json()["summary"]


def test_rag_endpoints(client: TestClient) -> None:
    client.post("/api/v1/rag/documents", json={
        "doc_id": "m1",
        "text": "Nginx 502 通常表示后端服务不可用，请检查 upstream 与后端健康状态",
    })
    r = client.post("/api/v1/rag/search", json={"query": "Nginx 502", "top_k": 1})
    assert r.status_code == 200
    assert len(r.json()["hits"]) >= 1
