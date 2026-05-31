# Dify Workflow API 参考文档

本文档基于 Dify 官方最新文档，作为本项目接入和调用 Dify Workflow 的标准规范指南。

## 1. 核心接入点

- **Base URL**: Dify 实例的 API 基础地址（通常由 `.env` 中的变量指定，如 `DIFY_API_URL` 或直接为 `https://api.dify.ai/v1`）
- **Authentication**: 所有请求必须在 HTTP Header 中包含 API Key：
  ```http
  Authorization: Bearer {YOUR_API_KEY}
  ```
- **注意**：API Key 应当严格保密，**绝对不能**在前端或客户端代码中暴露。所有调用必须通过后端服务器（如本项目中的 FastAPI 后端）进行转发或代理。

## 2. 触发 Workflow 执行

**Endpoint:** `POST /workflows/run`

用于触发并执行一个指定的 Workflow。如果是特定的应用，也可以使用类似 `/v1/workflows/<workflow_id>/run`（具体取决于应用配置，通常使用统一的 `/workflows/run` 搭配对应的 App API Key 即可定位到具体应用）。

### 2.1 请求 Payload (Body)

- **`inputs`** *(object, 必填)*: 包含工作流中定义的所有输入变量的键值对。例如 `{"query": "用户的输入"}`。如果工作流不需要任何输入，应传递空对象 `{}`。
- **`response_mode`** *(string, 必填)*: 指定 API 返回结果的方式。可选值为：
  - `"blocking"`: 阻塞模式。请求会一直等待，直到工作流执行完毕并一次性返回完整的 JSON 结果。
  - `"streaming"`: 流式模式。API 会通过 Server-Sent Events (SSE) 返回工作流执行过程中的增量更新。
- **`user`** *(string, 必填)*: 终端用户的唯一标识符。用于在 Dify 侧追踪请求来源、统计分析或计费。

**请求示例 (JSON):**

```json
{
  "inputs": {
    "query": "你好，请帮我生成一份文档"
  },
  "response_mode": "blocking",
  "user": "user-12345"
}
```

## 3. 查询 Workflow 执行状态（可选/长时任务）

**Endpoint:** `GET /workflows/run/{workflow_run_id}`

如果在 `POST /workflows/run` 中遇到超时，或者在设计异步系统时，可以通过此接口获取特定执行的详细状态和输出。

- **URL 参数**: `workflow_run_id` 为触发工作流时返回的执行 ID。
- 同样需要 `Authorization: Bearer {YOUR_API_KEY}`。

## 4. 常见问题与注意事项

1. **超时处理**: Workflow 可能涉及多个耗时的大模型调用和工具执行，`blocking` 模式极易导致 HTTP 超时。如果预期执行时间较长，建议使用 `streaming` 模式，或在后端处理好网络超时设置。
2. **环境变量管理**: Dify 的 Base URL 和 API Key 应统一在 `.env` 中配置，并通过后端的配置管理模块（如 `pydantic-settings`）加载，避免硬编码。
3. **输入参数校验**: 传给 `inputs` 的参数名必须与 Dify 工作流编排面板中定义的“开始节点 (Start)”的变量名**完全一致**，否则会导致执行失败或忽略输入。

---
*本文档为 AI Agent (Antigravity) 指导和开发规范，后续关于 Dify Workflow 的所有开发都将以此为准，禁止使用过时或臆想的 API 格式。*
