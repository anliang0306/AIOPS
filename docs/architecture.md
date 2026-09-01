# 架构设计说明（Phase 1 骨架）

本文档记录 Phase 1 可运行骨架的设计决策、模块职责与 Phase 2 演进方向，供研发据此评审 API、接口与验收标准。

## 1. 总体说明

Phase 1 目标是验证「智能体基础设施 + 单点 Agent」技术可行性（对应 PRD Phase 1 里程碑）。实现采用**单体 FastAPI 应用 + 进程内模块**，而非分布式微服务，以便快速启动与验证；模块边界（gateway / tools / agents / rag）刻意独立，后续可平滑拆分为独立服务。

## 2. 五层架构对齐

五层逻辑架构中，本骨架聚焦 **AI 能力层** 与 **应用层（最小 Agent）**，其余层（基础设施层 K8s/Prometheus/ELK、数据层时序库等）后续阶段补齐。

| PRD 层 | 本骨架对应 | 状态 |
|---|---|---|
| 基础设施层 | `config.py` 预设多模型接入、沙箱配置字段 | 部分（未接真实 K8s/监控） |
| 数据层 | `rag/service.py` 进程内知识存储 | 简化实现 |
| AI 能力层 | `gateway/`（多模型路由、Agent 编排、CLI 工具封装） | 已实现核心 |
| 应用层 | `agents/env_install_agent.py`（环境安装 Agent） | Demo |
| 交互层 | `api/routes_*` REST 入口 | REST 已就绪，Web/ChatOps/CLI 后续 |

## 3. 模块设计

### 3.1 多模型网关（`gateway/`）

- **后端抽象**（`base.py`）：`ModelBackend` 统一 `chat()` 接口与 `ModelResponse`（含 token 与成本单价）。`OpenAIModelBackend` 适配 OpenAI / Ollama / vLLM 等 `/v1/chat/completions`；`MockModelBackend` 提供确定性离线兜底。
- **路由**（`router.py`）：`classify_task()` 以关键词规则将用户输入映射到任务类别（simple_qa / complex_reasoning / tool_call / code_gen / sensitive），对应 PRD「多模型路由」中的任务分类；`ModelRouter.route()` 按 `route_defaults`（任务 → 默认模型）+ 可用性排序得到降级优先级；`chat()` 首选失败时自动降级并置 backoff 标记。
- **缓存**：进程内 TTL 缓存（替代 Redis），命中则不发模型请求，对应 PRD「高频查询 Redis 缓存」。
- **成本统计**（`usage.py`）：按模型累计 input/output tokens、估算成本（按元/百万 token 单价），供预算告警使用。
- **与 PRD 差异**：任务分类暂用规则而非模型；本地量化/蒸馏（INT8/INT4、教师蒸馏）属部署侧工作，Phase 2 落地。

### 3.2 CLI 工具封装引擎与沙箱（`tools/`）

- **工具抽象**（`base.py`）：`ToolSpec` 携带风险等级（low/medium/high）与参数 schema；`BaseTool.run(**kwargs)` 实现执行逻辑；**中高风险工具默认强制人工审批**（`require_approval`）。
- **注册表**（`registry.py`）：注册、查询、按风险上限过滤。
- **沙箱**（`sandbox.py`）：`LocalSubprocessSandbox` 通过命令白名单 + 超时限制执行（骨架阶段）。**生产必须替换为容器沙箱**（限制文件系统/网络/CPU/内存），本仓库在文件中明确留出该适配点。
- **内置工具**（`builtin.py`）：`shell`（白名单内执行）、`check_installed`（which 检测）、`install_package`（**模拟安装**，生成计划，MEDIUM 风险需审批）。

### 3.3 Agent 编排（`agents/`）

- **基类与生命周期**（`base.py` / `registry.py`）：`BaseAgent` 状态机（registered → running → stopped → failed）；`AgentRegistry` 提供注册、start/stop、run；仅 `RUNNING` 状态允许执行。
- **环境安装 Agent**（`env_install_agent.py`）：依赖 `check_installed` →（未安装则）`install_package` 生成计划 → 验证，组合多个 CLI 工具完成任务。体现「Agent 编排 + 工具封装」核心链路。

### 3.4 RAG 知识库（`rag/`）

- `KnowledgeService` 进程内存储 + 字符 n-gram 相似度检索（Jaccard），支持分块入库、Top-K 检索、上下文拼接注入。
- **演进**：替换为 Milvus/ChromaDB（embedding 向量检索），PRD 已预留 `vector_store` 配置字段。

## 4. API 概览

Base path：`/api/v1`。详见 `docs/api.md`。

| 端点 | 说明 |
|---|---|
| `GET /healthz`、`GET /info` | 健康检查 / 系统信息 |
| `GET /models`、`POST /models/chat`、`POST /models/usage/reset` | 模型列表 / 对话路由 / 用量重置 |
| `GET /tools`、`POST /tools/execute` | 工具列表 / 执行（含审批门禁） |
| `GET /agents`、`POST /agents/{id}/start|stop|run` | Agent 生命周期 / 执行 |
| `POST /rag/documents`、`POST /rag/search`、`POST /rag/context` | 知识入库 / 检索 / 上下文注入 |

## 5. 安全设计要点（对应 PRD 第 7、8 章）

- **Agent 操作安全**：风险分级 + 中高风险人工审批（接口层 `approved` 门禁）+ 沙箱白名单 + 超时限制。审计落库为 Phase 2。
- **数据隐私**：敏感任务路由到本地私有模型（骨架阶段为 mock 兜底）；真实模型接入见 `.env` 配置说明。

## 6. Phase 2 演进清单

1. RBAC 权限体系 + 审计持久化（含审批记录）。
2. 沙箱容器化（Docker），限制文件/网络/CPU/内存；真实包管理工具替换模拟安装。
3. 本地模型 INT8/INT4 量化（GPTQ/AWQ）+ 云端教师蒸馏；多模型成本预算告警与自动切换。
4. 知识库接入 ChromaDB/Milvus（embedding 检索）。
5. AIOps 平台（故障自愈 / 巡检 Agent）、AI+ITSM 平台（工单引擎 / 智能客服 / ChatOps）、DevOps 平台。
6. 统一交互层 Web 控制台（React/Vue3）。
