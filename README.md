# AIOps + AI+ITSM 智能运维系统 · AIOps + AI+ITSM Intelligent Operations Platform

> **中文**：基于 PRD 的下一代智能运维系统。核心设计理念 **Agent Native（智能体原生）**——从 "AI First" 向 "Agent Native" 演进，实现 AIOps 与 ITSM 深度融合、DevOps/SRE 一体化协同。
>
> **English**: A next-generation intelligent operations platform built from a product PRD. Its core philosophy is **Agent Native** — evolving from *AI First* to *Agent Native* — to deeply integrate AIOps with ITSM and enable unified DevOps/SRE collaboration.

---

## 当前状态 · Current Status

**中文**：Phase 1 最小可运行骨架已完成，Phase 2 核心能力已落地（数据持久化 / ITSM 工单引擎 / 故障自愈 Agent）。

- **Phase 1 — 智能体基础设施核心**：多模型网关（任务路由 + OpenAI 兼容接入 + Mock 降级 + Token/成本统计）、CLI 工具封装引擎（注册表 + 风险分级 + 沙箱执行）、Agent 编排引擎（生命周期管理 + 注册表）、简化版 RAG 知识库；并交付**单点 Agent Demo：环境安装 Agent**，跑通“Agent 编排 + 工具封装”链路。
- **Phase 2 — 已落地核心**：SQLite + SQLAlchemy 数据持久化；ITSM 工单引擎（事件/变更工单全生命周期 + 中高风险审批状态机）；故障自愈 Agent（检测 → 诊断 → 审批门禁 → 执行 → 验证 → 回滚 → 知识沉淀）。
- **待实现（Roadmap）**：RBAC 权限体系、沙箱容器化（Docker）、真实 LLM 微调/蒸馏、审批界面、ChatOps。

**English**: The Phase 1 minimal runnable skeleton is complete, and Phase 2 core capabilities have landed (persistence / ITSM ticket engine / auto-healing agent).

- **Phase 1 — Agent infrastructure core**: multi-model gateway (task-based routing + OpenAI-compatible backends + Mock fallback + token/cost tracking), CLI tool-wrapping engine (registry + risk levels + sandboxed execution), agent orchestration engine (lifecycle management + registry), and a lightweight RAG knowledge base. Ships a **single-agent demo: Environment-Install Agent** that validates the “agent orchestration + tool wrapping” pipeline.
- **Phase 2 — core delivered**: SQLite + SQLAlchemy persistence; an ITSM ticket engine (full incident/change ticket lifecycle + an approval state machine for medium/high-risk actions); an auto-healing agent (detect → diagnose → approval gate → act → verify → roll back → knowledge distillation).
- **Roadmap**: RBAC, containerized (Docker) sandbox, real-LLM fine-tuning/distillation, approval UI, ChatOps.

> 本文档面向研发团队（接口 / 验收标准 / 运行方式）与决策层（范围 / 里程碑 / 局限）。**完整 PRD** 见 `docs/PRD.md`，**架构与设计决策**见 `docs/architecture.md`。
> This README targets both R&D (interfaces / acceptance criteria / how to run) and decision makers (scope / milestones / limitations). **Full PRD** → `docs/PRD.md`; **architecture & design decisions** → `docs/architecture.md`.

---

## 目录结构 · Repository Layout

```
backend/
  app/
    main.py            # FastAPI 入口：组装数据库/网关/工具/Agent/ITSM/RAG · app bootstrap
    config.py          # 全局配置（pydantic-settings，.env 注入）· settings (.env-driven)
    deps.py            # 依赖注入（从 app.state 取单例）· dependency injection
    db/                # 数据持久化（SQLite + SQLAlchemy 2.x）· persistence layer
      session.py       #   engine / Session 工厂 / 建表入口 · engine, session factory, create_all
    gateway/           # 多模型网关 · multi-model gateway
      base.py          #   模型后端抽象 + 统一响应 · backend abstraction + unified response
      mock_model.py    #   Mock 后端（离线可跑）· mock backend (runs offline)
      openai_model.py  #   OpenAI 兼容后端（Ollama/vLLM/OpenAI）· OpenAI-compatible backend
      router.py        #   任务分类 + 路由 + 失败降级 + 进程内缓存 · routing + fallback + cache
      usage.py         #   Token/成本统计 · token & cost tracking
    tools/             # CLI 工具封装引擎 · CLI tool engine
      base.py          #   工具抽象 + 风险分级 + 参数校验 · tool abstraction + risk levels
      registry.py      #   工具注册表 · tool registry
      sandbox.py       #   沙箱执行（白名单 + 超时）· allowlist sandbox + timeout
      builtin.py       #   内置工具（shell/检查/模拟安装）· built-in tools
    agents/            # Agent 编排 · agent orchestration
      base.py          #   Agent 基类 + 生命周期 · base agent + lifecycle
      registry.py      #   Agent 注册表 · agent registry
      env_install_agent.py  # 环境安装 Agent Demo · environment-install agent demo
    itsm/              # ITSM 工单引擎 · ITSM ticket engine
      models.py        #   工单 / 审批任务 ORM 模型 · Ticket / ApprovalTask models
      service.py       #   工单 CRUD + 审批状态机 + 自动建单 · ticket service + approval state machine
    autoheal/          # 故障自愈 Agent · auto-healing agent
      models.py        #   自愈执行记录（AutohealRun）· run-record model
      agent.py         #   检测→诊断→审批→执行→验证→回滚→知识沉淀 · detect→…→learn pipeline
    rag/               # 简化版 RAG 服务 · lightweight RAG service
      service.py       #   进程内分块 + n-gram 相似度检索 · in-process chunking + n-gram search
    api/               # REST 接口（routes_*）· REST routes
  tests/               # pytest 测试套件 · pytest test suite
docs/                  # 文档（PRD / 架构设计 / API）· PRD / architecture / API docs
```

---

## 快速开始 · Quick Start

前置：Python 3.11+。 · Prerequisites: Python 3.11+.

```bash
# 1. 创建虚拟环境并安装依赖 · create venv & install dependencies
python -m venv .venv
.venv/Scripts/python -m pip install -U pip
.venv/Scripts/python -m pip install -e ".[dev]"   # Windows 下也可直接 -e . · `-e .` also works on Windows

# 2.（可选）配置真实模型端点，写入 backend/.env
#    (optional) configure a real model endpoint in backend/.env:
#    AIOPS_MODEL_ENDPOINTS='[{"id":"qwen2.5:7b","base_url":"http://127.0.0.1:11434/v1","kind":"local","input_price_per_mtok":0,"output_price_per_mtok":0}]'
#    未配置任何真实模型时，网关自动降级为 Mock 模型，可离线运行。
#    Without any real model the gateway falls back to the Mock model and runs offline.

# 3. 启动服务 · start the server（需在 backend/ 目录下 · run inside backend/）
.venv/Scripts/python -m uvicorn app.main:app --port 8000

# 4. 运行测试 · run tests
.venv/Scripts/python -m pytest -q
```

---

## 核心能力 · Core Capabilities

| 模块 · Module | 能力 · Capability | 演示示例 · Demo |
|---|---|---|
| 多模型网关<br>Multi-model gateway | 按任务分类路由、失败自动降级、Mock 兜底<br>Task-based routing, automatic fallback, Mock backup | `GET /api/v1/models`、`POST /api/v1/models/chat` |
| CLI 工具引擎<br>CLI tool engine | 工具注册、风险分级、白名单沙箱<br>Tool registration, risk levels, allowlist sandbox | `POST /api/v1/tools/execute`（中高风险需 `approved=true` · medium/high risk requires `approved=true`） |
| Agent 编排<br>Agent orchestration | 生命周期管理 + 任务执行<br>Lifecycle management + task execution | `POST /api/v1/agents/env-install-agent/start` → `/run` |
| ITSM 工单引擎<br>ITSM ticket engine | 事件/变更工单全生命周期 + 中高风险审批流<br>Incident/change ticket lifecycle + approval workflow | 建单 `POST /api/v1/itsm`、待审批 `GET /api/v1/itsm/approvals/pending`、决策 `POST /api/v1/itsm/approvals/{id}/decide` |
| 故障自愈 Agent<br>Auto-healing agent | 检测→诊断→审批→执行→验证→回滚→知识沉淀<br>detect→diagnose→approve→act→verify→roll back→learn | 触发 `POST /api/v1/autoheal/run`、查询 `GET /api/v1/autoheal/runs/{run_id}` |
| RAG 知识库<br>RAG knowledge base | 分块入库 + Top-K 检索 + 上下文注入<br>Chunking + Top-K retrieval + context injection | `POST /api/v1/rag/documents`、`/search`、`/context` |

示例（须先 start Agent）· Example (start the agent first):

```bash
# 启动环境安装 Agent · start the env-install agent
curl -X POST http://127.0.0.1:8000/api/v1/agents/env-install-agent/start
# 执行：检查 python、git 是否安装 · run: check whether python & git are installed
curl -X POST http://127.0.0.1:8000/api/v1/agents/env-install-agent/run \
  -H "Content-Type: application/json" -d '{"payload":{"packages":["python","git"]}}'
```

> 完整接口见 `docs/api.md`；`docs/architecture.md` 给出各模块设计与演进点。
> Full API reference → `docs/api.md`; module design & evolution notes → `docs/architecture.md`.

---

## 开发规范 · Development Guidelines

- **测试 · Testing**：`pytest`，覆盖网关、工具/沙箱、Agent、RAG、ITSM/自愈与端到端 API。Covers gateway, tools/sandbox, agents, RAG, ITSM/auto-heal, and end-to-end APIs.
- **文档驱动 · Documentation-driven**：需求 / 设计 / API 文档先行（见 `docs/`）。PRD / design / API docs come first (see `docs/`).
- **后续路线（Phase 2+）· Roadmap**：RBAC 权限体系、沙箱容器化（Docker）、真实 LLM 微调/蒸馏、审批界面、ChatOps。RBAC, Docker-based sandbox, real-LLM fine-tuning/distillation, approval UI, ChatOps.

---

## 已知局限与建议 · Known Limitations & Notes

- **沙箱 · Sandbox**：当前为**本地白名单子进程**，仅用于演示/测试；生产环境须切换为容器沙箱并限制文件 / 网络 / CPU / 内存。Currently an allowlisted local subprocess for demo/testing only; switch to a container sandbox with file/network/CPU/memory limits in production.
- **模拟安装 · Simulated install**：`install_package` 为**模拟安装**（生成计划），不会真正改动系统。It generates a plan only and never modifies the real system.
- **成本统计 · Cost tracking**：Token/成本统计目前为进程内，后续落库并增加预算告警。Token/cost stats are in-process for now; DB persistence and budget alerts are planned.
- **知识库 · Knowledge base**：当前为进程内 n-gram 检索（非 embedding），规模化时可替换为 Milvus / ChromaDB。Currently in-process n-gram retrieval (not embeddings); replace with Milvus / ChromaDB at scale.