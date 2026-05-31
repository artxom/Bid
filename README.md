# Bid (智能标书生成助手)

本项目是一个基于“主脑-执行者”双层 AI 架构的智能标书生成系统，旨在解决银行业及其他复杂商业场景下的长文本标书自动生成、格式还原与并发编排难题。

## 核心架构设计：主脑与执行者 (Commander & Executor)

系统采用高度解耦的双层并发架构，充分发挥不同 LLM 的优势，并有效控制成本与速度：

- **Commander (主脑)：基于 FastAPI + Gemini Pro**
  - **职责**：全局理解、任务拆解与并发调度。
  - **流程**：解析标书目录树 -> 结合用户意图生成“调度清单” -> 挂载上下文 -> 并发触发多个执行者任务。
  - **优势**：利用高智力模型把控整体逻辑一致性。

- **Executor (执行者)：基于 Dify Workflow + DeepSeek**
  - **职责**：细分章节内容的填充与多模态元素的生成。
  - **流程**：接收 Commander 传来的单章节上下文和指令 -> 执行检索/生成 -> 按照“多模态内容协议”返回 JSON 格式结果。
  - **优势**：极大地提高了长文本生成的并发速度，同时通过工作流实现了高度定制化的 Prompt 节点。

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

### 解析与组装策略
1. **纯文本 (`text`)**：直接通过 `python-docx` 添加段落。
2. **表格 (`table/markdown`)**：后端解析 Markdown 语法，使用 `python-docx` 创建原生 Word 表格。
3. **图表 (`chart/mermaid`)**：后端调用 `mermaid.ink`（或本地 `mermaid-cli`）将代码转换为 PNG 图片，然后插入文档。

## 技术栈

- **前端**：Next.js + Tailwind CSS + shadcn/ui
- **后端**：FastAPI + python-docx (异步调度，并发控制)
- **AI 编排**：Dify
- **环境部署**：Docker Compose

## 状态管理与并发控制

为了保证并发请求的稳定性，后端引入了信号量 (Semaphore) 限制最高并发数。针对每一章节的任务状态流转（`PENDING` -> `RUNNING` -> `SUCCESS` / `FAILED`），系统提供实时反馈接口供前端进度条读取，并支持单章级的一键重试。
