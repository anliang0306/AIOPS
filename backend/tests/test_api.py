"""端到端 API 集成测试（TestClient，无真实模型，全程 Mock 降级）。

注意：必须在 import app.main 之前把数据库指向临时文件，避免测试污染仓库内的
aiops.db（get_settings 有 lru_cache，首次 build_app 即固化配置）。
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

_p2_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_p2_tmp.close()
os.environ["AIOPS_DATABASE_URL"] = f"sqlite:///{_p2_tmp.name}"
import atexit  # noqa: E402
import gc  # noqa: E402


@atexit.register
def _cleanup_p2_db() -> None:
    gc.collect()
    try:
        Path(_p2_tmp.name).unlink(missing_ok=True)
    except PermissionError:
        pass  # 主释放见 client fixture teardown


import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import build_app  # noqa: E402


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = build_app()
    with TestClient(app) as c:
        yield c
    app.state.database.engine.dispose()
    gc.collect()


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


# ---------------- Phase 2：ITSM 工单引擎 + 故障自愈 ----------------

def test_itsm_ticket_crud_and_transition(client: TestClient) -> None:
    r = client.post("/api/v1/itsm", json={
        "ticket_type": "incident", "title": "接口 502", "description": "后端不可用",
    })
    assert r.status_code == 200
    tid = r.json()["id"]
    assert r.json()["status"] == "open"

    r = client.get(f"/api/v1/itsm/{tid}")
    assert r.status_code == 200 and r.json()["title"] == "接口 502"

    r = client.post(f"/api/v1/itsm/{tid}/transition", json={"to_status": "resolved", "actor": "sre"})
    assert r.status_code == 200 and r.json()["status"] == "resolved"

    # 非法状态 -> 400
    r = client.post(f"/api/v1/itsm/{tid}/transition", json={"to_status": "nonsense"})
    assert r.status_code == 400


def test_itsm_approval_flow(client: TestClient) -> None:
    # 通过故障自愈生成待审批任务
    r = client.post("/api/v1/autoheal/run", json={"incident": "服务发生 502 错误"})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "needs_human"
    assert data["ticket_id"] is not None

    # 待审批
    r = client.get("/api/v1/itsm/approvals/pending")
    assert r.status_code == 200
    approvals = r.json()["approvals"]
    assert len(approvals) >= 1
    ap_id = approvals[0]["id"]

    # 批准
    r = client.post(f"/api/v1/itsm/approvals/{ap_id}/decide",
                    json={"approve": True, "actor": "ops", "comment": "确认"})
    assert r.status_code == 200 and r.json()["status"] == "approved"

    # 重复决策 -> 409
    r = client.post(f"/api/v1/itsm/approvals/{ap_id}/decide",
                    json={"approve": False, "actor": "ops"})
    assert r.status_code == 409


def test_autoheal_run_lifecycle(client: TestClient) -> None:
    r = client.post("/api/v1/autoheal/run", json={"incident": "磁盘 disk_full 空间不足"})
    assert r.status_code == 200
    data = r.json()
    assert data["run_id"] is not None
    assert data["status"] == "needs_human"
    assert data["diagnosis"] != ""

    r = client.get(f"/api/v1/autoheal/runs/{data['run_id']}")
    assert r.status_code == 200 and r.json()["incident"].startswith("磁盘")


def test_itsm_knowledge_feedback(client: TestClient) -> None:
    r = client.post("/api/v1/itsm", json={"title": "沉淀知识", "source": "manual"})
    tid = r.json()["id"]
    r = client.post(f"/api/v1/itsm/{tid}/knowledge", json={"text": "处置过程与结论"})
    assert r.status_code == 200 and r.json()["ok"] is True
    # 验证已入库
    r = client.post("/api/v1/rag/search", json={"query": "处置过程", "top_k": 3})
    assert any(h["doc_id"] == f"ticket-{tid}" for h in r.json()["hits"])
