# AIOps + AI+ITSM 智能运维系统

> 基于 PRD 的一代智能运维系统。核心设计理念 **Agent Native（智能体原生）**，从"AI First"向"Agent Native"演进，实现 AIOps 与 ITSM 深度融合、DevOps/SRE 一体化协同。

## 当前状态：Phase 1 可运行骨架

对应 PRD Phase 1（第 1-3 月）「基础建设与单点突破」里程碑的**最小可运行版本**，重点打通：

- **智能体基础设施核心**：多模型网关（路由 + OpenAI 兼容接入 + Mock 降级 + Token/成本统计）、CLI 工具封装引擎（注册表 + 风险分级 + 沙箱执行）、Agent 编排引擎（生命周期管理 + 注册表）、简化版 RAG 知识库。
- **单点 Agent Demo**：环境安装 Agent（依赖检查 → 安装计划 → 验证），跑通"Agent 编排 + 工具封装"链路。

> 本文档面向研发团队（接口 / 验收标准 / 运行方式）与决策层（范围 / 里程碑 / 局限）。**完整 PRD** 见 `docs/PRD.md`，**架构与设计决策**见 `docs/architecture.md`。

## 目录结构

```
backend/
  app/
    main.py            # FastAPI 入口，组装网关/工具/Agent/RAG
    config.py          # 全局配置（pydantic-settings，.env 注入）
    deps.py            # 依赖注入（从 app.state 取单例）
    gateway/           # 多模型网关
      base.py          #   模型后端抽象 + 统一响应
      mock_model.py    #   Mock 后端（离线可跑）
      openai_model.py  #   OpenAI 兼容后端（Ollama/vLLM/OpenAI）
      router.py        #   任务分类 + 路由 + 失败降级 + 进程内缓存
      usage.py         #   Token/成本统计
    tools/             # CLI 工具封装引擎
      base.py          #   工具抽象 + 风险分级 + 参数校验
      registry.py      #   工具注册表
      sandbox.py       #   沙箱执行（白名单 + 超时）
      builtin.py       #   内置工具（shell/检查/模拟安装）
    agents/            # Agent 编排
      base.py          #   Agent 基类 + 生命周期
      registry.py      #   Agent 注册表
      env_install_agent.py  # 环境安装 Agent Demo
    rag/               # 简化版 RAG 服务
      service.py       #   进程内分块 + n-gram 相似度检索
    api/               # REST 接口（routes_*）
  tests/               # pytest 测试套件
docs/                  # 文档（PRD / 架构设计 / API）
```

## 快速开始

前置：Python 3.11+。

```bash
# 1. 创建虚拟环境并安装依赖
python -m venv .venv
.venv/Scripts/python -m pip install -U pip
.venv/Scripts/python -m pip install -e ".[dev]"   # Windows 下也可直接 -e .

# 2.（可选）配置真实模型端点，写入 backend/.env：
#    AIOPS_MODEL_ENDPOINTS='[{"id":"qwen2.5:7b","base_url":"http://127.0.0.1:11434/v1","kind":"local","input_price_per_mtok":0,"output_price_per_mtok":0}]'
#    未配置任何真实模型时，网关自动降级为 Mock 模型，可离线运行。

# 3. 启动服务
.venv/Scripts/python -m uvicorn app.main:app --port 8000  # 需在 backend/ 目录下

# 4. 运行测试
.venv/Scripts/python -m pytest -q
```

## 核心能力与演示链路

| 模块 | 能力 | 演示示例 |
|---|---|---|
| 多模型网关 | 按任务分类路由、失败自动降级、Mock 兜底 | `GET /api/v1/models`、`POST /api/v1/models/chat` |
| CLI 工具引擎 | 工具注册、风险分级、白名单沙箱 | `POST /api/v1/tools/execute`（中高风险需 `approved=true`） |
| Agent 编排 | 生命周期管理 + 任务执行 | `POST /api/v1/agents/env-install-agent/start` → `/run` |
| RAG 知识库 | 分块入库 + Top-K 检索 + 上下文注入 | `POST /api/v1/rag/documents`、`/search`、`/context` |

示例（须先 start Agent）：

```bash
# 启动环境安装 Agent
curl -X POST http://127.0.0.1:8000/api/v1/agents/env-install-agent/start
# 执行：检查 python、git 是否安装
curl -X POST http://127.0.0.1:8000/api/v1/agents/env-install-agent/run \
  -H "Content-Type: application/json" -d '{"payload":{"packages":["python","git"]}}'
```

完整接口见 `docs/api.md`；`docs/architecture.md` 给出各模块设计与 Phase 2 改进点。

## 开发规范

- **测试**：`pytest`；覆盖网关、工具/沙箱、Agent、RAG、端到端 API。
- **文档驱动**：需求/设计/API 文档先行（见 `docs/`）。
- **待实现（Phase 2+）**：RBAC 权限体系、沙箱容器化（Docker）、真实 LLM 微调/蒸馏、ITSM/AIOps 平台、ChatOps、审批界面。

## 已知局限与建议

- 沙箱为**本地白名单子进程**，仅用于演示/测试；生产须切换为容器沙箱并限制文件/网络/CPU/内存。
- `install_package` 为**模拟安装**（生成计划），不会真正改动系统。
- Token 成本统计为进程内，落库 + 预算告警在 Phase 2。
- 知识库为进程内 n-gram 检索（非 embedding），规模化时替换 Milvus/ChromaDB。
