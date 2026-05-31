# 项目交接指南 (Handover Document) - Bid 项目

你好，Antigravity IDE 的 AI 助手。我是上一任负责此项目的 Gemini CLI 助手。为了让你能快速接手并继续推进“智能标书生成助手 (Bid)”的开发，我为你梳理了目前的项目状态、核心资产以及待执行的路线图。

## 1. 项目核心愿景
本项目旨在通过 **Gemini Pro (主脑/Commander)** 与 **Dify Workflow (执行者/Executor)** 的双层架构，实现标书从“解析大纲”到“并发生成内容”再到“还原 Word 格式”的自动化闭环。

## 2. 核心架构资产 (核心共识)

### 2.1 双层模型协作模式
- **Commander (FastAPI 端)**：负责全局逻辑。它解析 Word 目录，将其转化为任务列表，并按优先级并发调度 Dify。
- **Executor (Dify 端)**：负责章节内容填充。它输出严格遵循“多模态内容协议”的 JSON，包含文本、Markdown 表格和 Mermaid 流程图。

### 2.2 多模态内容协议 (Critical)
Dify 返回的必须是如下格式，这是后端解析器 (`python-docx`) 能还原 Word 格式的前提：
```json
{
  "section_id": "章节号",
  "segments": [
    { "type": "text", "value": "..." },
    { "type": "chart", "format": "mermaid", "value": "..." },
    { "type": "table", "format": "markdown", "value": "..." }
  ]
}
```

## 3. 当前开发进度与现状

### 3.1 已完成 (Success)
- [x] **后端解析引擎**：基于 `python-docx` 的高精度大纲提取算法，可识别 `outlineLevel` 和特定正则表达式，完美支持复杂银行标书。并已修复提取规则，支持长文本过滤和中文标题样式。
- [x] **前端 UI 雏形**：使用 Next.js + Tailwind 构建，具备目录树渲染、上传状态展示和 AI 对话侧边栏。
- [x] **工程标准化**：项目已实现 Docker 化，`docker-compose.yml` 稳定配置了前后端环境（已修复本地和容器内的端口冲突问题）。
- [x] **并发调度逻辑**：后端 `main.py` 已完成向 Dify 发起并发请求的具体逻辑（基于 `asyncio.Semaphore` 和 `httpx.AsyncClient`）。
- [x] **Dify 集成**：`/generate` 接口已连通 Dify Workflow，并能处理阻塞模式的返回数据。

### 3.2 进行中 (In Progress)
- [ ] **多模态还原引擎**：后端需要将 Dify 返回的结构化数据（包含 Markdown 表格、Mermaid 代码等）拼装回 Word 文档。
- [ ] **前端状态同步**：前端尚未将每一章的生成状态与界面的实时进度条结合起来。

## 4. 你的下一步任务 (Next Actions)

1. **实现目录生成与 Dify 并发调度的联动 (核心/高优)**：
   - Gemini 重构完新的目录结构后，需支持自动识别出指定章节下的所有**最新叶子节点（即没有子章节的末端章节）**。
   - 针对这些叶子节点，并发式地向 Dify 引擎发起正文生成请求，避免对中间章节（只有标题无实质内容的父章节）发起冗余请求。
2. **构建章节级请求监控界面**：
   - 在前端提供一个可视化的监控面板或列表，专门用于实时展示每个子章节发往 Dify 的请求状态（排队中、生成中、成功、失败）。
   - 保证用户能够随时中止、重试或查看单章的进度详情。
3. **实现多模态还原引擎**：
   - 编写解析 Dify 返回的 `segments` 逻辑，处理文本、表格（转化为 `python-docx` 表格）及图表（如使用 Mermaid 生成 PNG）。

## 5. 关键文件索引
- `backend/main.py`: 后端逻辑入口。
- `backend/test_outline.py`: 标书解析逻辑的验证脚本（交接前已跑通）。
- `frontend/src/app/page.tsx`: 主交互界面。
- `GEMINI.md`: 记录了项目的开发原则（如：必须查阅最新官方文档）。
- `README.md`: 记录了对外公开的项目说明和协议。

## 6. 开发者贴士
- 用户非常看重“并发”和“非文字内容（图表/表格）”的还原能力。
- 银行业标书格式敏感，处理 Word 时请务必保持段落样式的稳定性。
- 环境启动：`docker-compose up --build`。

祝开发顺利！让我们一起把 Bid 做成最强的标书助手。
