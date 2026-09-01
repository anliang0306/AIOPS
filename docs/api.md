# API 文档

Base URL：开发环境 `http://127.0.0.1:8000`
业务接口前缀：`/api/v1`（`/healthz`、`/info` 除外）。
返回均为 JSON。

## 系统

### `GET /healthz`
健康检查。
```json
{"status": "ok"}
```

### `GET /info`
系统信息：版本、模型/工具/Agent/知识块数量。

## 多模型网关 `/api/v1/models`

### `GET /api/v1/models`
模型列表 + Token/成本统计。
```json
{"models": [{"model_id":"mock","kind":"mock","enabled":true,"available":true,"calls":0,"errors":0,"input_tokens":0,"output_tokens":0,"estimated_cost_usd":0.0,"input_price_per_mtok":0.0,"output_price_per_mtok":0.0}],"total_estimated_cost_usd":0.0}
```

### `POST /api/v1/models/chat`
按任务路由到模型，失败自动降级。

请求体：
```json
{
  "messages": [{"role":"user","content":"什么是SLA"}],
  "task": "simple_qa",     // 可选；省略时自动分类
  "use_cache": true,
  "temperature": 0.0
}
```
返回：`ModelResponse`（含 `model_id`、`content`、Token）。模型全不可用时返回 503。

### `POST /api/v1/models/usage/reset`
重置 Token/成本统计。返回 `{"ok": true}`。

## CLI 工具 `/api/v1/tools`

### `GET /api/v1/tools?max_risk=medium`
工具列表（可按风险等级过滤）。

### `POST /api/v1/tools/execute`
执行工具。中高风险工具必须 `approved: true`，否则 403。
```json
{"tool_id":"install_package","params":{"package":"git"},"approved":true}
```
缺参数返回 400；工具不存在返回 404。

## Agent `/api/v1/agents`

### `GET /api/v1/agents?status=running`
Agent 列表（可按状态过滤）。

### `POST /api/v1/agents/{agent_id}/start` / `/stop`
启动 / 停止 Agent。

### `POST /api/v1/agents/{agent_id}/run`
执行 Agent 任务（Agent 须已 `start`）。
```json
{"payload":{"packages":["python","git"]}}
```
返回 `AgentRunResult`（`ok`、`summary`、`details`）。

**环境安装 Agent（`env-install-agent`）payload**：
```json
{"packages":["python","git"]}
```
流程：检查是否已安装 → 未安装生成模拟安装计划 → 验证。

## RAG / 知识库 `/api/v1/rag`

### `POST /api/v1/rag/documents`
分块入库。
```json
{"doc_id":"m1","text":"Nginx 502 通常表示后端服务不可用","metadata":{"type":"troubleshoot"}}
```
返回：`{"doc_id":"m1","chunks":1,"chunk_ids":["m1#0"]}`。

### `POST /api/v1/rag/search`
Top-K 检索。
```json
{"query":"Nginx 502","top_k":1}
```
返回 `{"hits":[{"chunk_id","doc_id","text","score"}]}`。

### `POST /api/v1/rag/context`
把检索结果拼成可注入提示词的上下文字符串。
返回 `{"context":"[知识库 1] ..."}`。
