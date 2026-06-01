# Bid (智能标书生成助手)

本项目是一个基于“主脑-执行者”双层 AI 架构的智能标书生成系统，旨在解决银行业及其他复杂商业场景下的长文本标书自动生成、格式还原与并发编排难题。

## 核心架构设计：主脑与执行者 (Commander & Executor)

系统采用高度解耦的双层并发架构，充分发挥不同 LLM 的优势，并有效控制成本与速度：

- **Commander (主脑)：基于 FastAPI + Gemini Pro (支持模型配置)**
  - **职责**：全局理解、任务拆解与并发调度。
  - **流程**：解析标书目录树 -> 结合用户意图使用高智力的 `Pro` 模型生成“调度清单” -> 挂载上下文 -> 并发触发多个执行者任务。
  - **优势**：利用高智力模型把控整体逻辑一致性。

- **Executor (执行者)：基于 Gemini Flash + Dify Workflow + 任意推理模型 (如 DeepSeek)**
  - **职责**：细分章节内容的填充与多模态元素的生成。
  - **流程**：
    1. **智能预处理**：后端拦截单章节上下文，先通过速度快、成本低的 `Flash` 模型生成具有强引导性的结构化指令。
    2. **工作流执行**：将结构化指令发往 Dify 工作流，由 DeepSeek 等推理模型执行高并发的具体内容生成。
    3. **净化器**：后端接收返回结果，精准拦截并切除模型的 `<think>` 思维链标签，确保输出纯净的 JSON 协议数据。
  - **优势**：极大地提高了长文本生成的并发速度，并在降低成本的同时通过预处理解决了推理模型易“跑偏”的缺点。

## 多模态内容协议 (Content Protocol)

为解决大语言模型生成图表、表格并最终拼装进 Word (`.docx`) 的技术难题，本系统定义了统一的数据交互协议。Dify 的输出必须是严格的 JSON，格式如下：

```json
{
  "section_id": "2.1",
  "content_type": "mixed",
  "segments": [
    {
      "type": "text", 
      "value": "本项目的技术架构如下："
    },
    {
      "type": "chart", 
      "format": "mermaid", 
      "value": "graph TD;\n A[用户] --> B[前端];\n B --> C{后端};"
    },
    {
      "type": "table", 
      "format": "markdown", 
      "value": "| 模块 | 描述 |\n|---|---|\n| 前端 | Next.js |\n| 后端 | FastAPI |"
    }
  ]
}
```

### 解析与组装策略 (高容错设计)
1. **优先解析 JSON / 智能降级 Markdown**：系统优先尝试将 Dify 的返回值解析为标准 JSON；若解析失败，则自动降级为 Markdown 解析模式，通过正则表达式分离文本、表格和代码块，极大提升了模型生成的容错率。
2. **纯文本 (`text`)**：直接通过 `python-docx` 添加段落。
3. **表格 (`table/markdown`)**：后端解析 Markdown 语法，使用 `python-docx` 绘制带有 `Table Grid` 样式的原生 Word 表格。
4. **图表 (`chart/mermaid`)**：后端调用云端渲染引擎 `kroki.io`，将 Mermaid 代码经 Zlib+Base64 压缩后转换为高清 PNG 图片插入文档中。

## 技术栈

- **前端**：Next.js + Tailwind CSS + shadcn/ui + react-markdown
- **后端**：FastAPI + python-docx + SQLAlchemy (SQLite)
- **AI 编排**：Dify + DeepSeek / Gemini Pro
- **环境部署**：Docker Compose

## 状态管理与并发控制

为了保证并发请求的稳定性，后端引入了全局信号量 (Semaphore) 限制最高并发数。针对每一章节的任务状态流转（`queued` -> `generating` -> `success` / `error`），系统在前端右下角提供了**抽屉式 (Drawer) 悬浮监控面板**，用户可以实时查看进度并支持单章级的一键重试和一键取消。

同时，系统引入了 **SQLite 本地数据库** 作为持久化底座。用户的标书目录结构与生成进度会自动增量落盘，即使刷新页面或重启系统，也能一秒恢复至最后的工作状态。此外，系统还会将每一次的大模型交互（包括输入提示词、输出结果、耗时、Token 消耗等）存入数据库中。在本地调试时，开发人员可以直接访问 `/Users/artxom/code/Bid/backend/bid.db`，并在 `llm_request_logs` 数据表中进行全方位的数据查询与问题排查。
