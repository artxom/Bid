import re
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from docx import Document
import uvicorn
import io
import asyncio
import httpx
import os
from pydantic import BaseModel
from typing import List, Optional
from dotenv import load_dotenv
import json
from google import genai
import time

from services.commander import rewrite_outline_with_gemini, stream_rewrite_outline_with_gemini
from services.docx_builder import rebuild_docx_from_outline
from sqlalchemy.orm import Session
from database import engine, get_db
import models
from services.logger import log_llm_request_async
from fastapi import Depends

# Initialize database
models.Base.metadata.create_all(bind=engine)

# 加载环境变量
load_dotenv()

app = FastAPI(title="Bid Assistant API")

# 允许前端跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 匹配更精确的标题格式
TITLE_RE = re.compile(
    r'^('
    r'第[一二三四五六七八九十百零]+[章节篇部分]|'  # 第X章
    r'[一二三四五六七八九十百]+[、\.]\s*|'       # 一、
    r'\d+\.\d+(\.\d+)*\s+|'                    # 1.1 或 1.1.1 
    r'\d+[、\.]\s+'                            # 1、或 1. 
    r')'
)

def get_outline_level(paragraph):
    """尝试获取段落的大纲级别"""
    text = paragraph.text.strip()
    if not text:
        return None
        
    style_name = paragraph.style.name.lower()
    
    # 0. 忽略目录 (TOC)
    if style_name.startswith('toc') or 'toc' in style_name:
        return None
        
    # 1. 检查样式名
    if style_name.startswith('heading'):
        try:
            return int(style_name.split(' ')[-1])
        except (ValueError, IndexError):
            pass
            
    if style_name.startswith('标题'):
        try:
            return int(style_name.split(' ')[-1])
        except (ValueError, IndexError):
            pass
    
    # 2. 检查 XML 中的 outlineLevel
    p_pr = paragraph._element.get_or_add_pPr()
    outline_lvl = p_pr.xpath('./w:outlineLvl')
    if outline_lvl:
        try:
            val = int(outline_lvl[0].get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val'))
            if val < 9: # 9 表示正文 (body text)
                return val + 1
        except (ValueError, TypeError):
            pass
    
    # 3. 如果文本较短且符合标题正则，尝试根据前缀推断级别
    if len(text) < 100:
        match = TITLE_RE.match(text)
        if match:
            if re.match(r'^第[一二三四五六七八九十百零]+[章节篇部分]', text):
                return 1
            if re.match(r'^[一二三四五六七八九十百]+[、\.]', text):
                return 2
            num_match = re.match(r'^(\d+(?:\.\d+)+)', text)
            if num_match:
                return num_match.group(1).count('.') + 1
            if re.match(r'^\d+[、\.]', text):
                return 3
                
    return None

@app.get("/")
async def root():
    return {"message": "Bid Assistant API is running"}

@app.get("/models")
async def get_models():
    try:
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("No API key found in environment variables.")
        client = genai.Client(api_key=api_key)
        models_list = client.models.list()
        result = []
        for m in models_list:
            # Check if it's a generative model
            if hasattr(m, 'supported_generation_methods') and "generateContent" in getattr(m, 'supported_generation_methods', []):
                result.append({"name": m.name, "display_name": m.display_name})
        # If supported_generation_methods is not easily accessible in the new SDK version, fallback to just returning all or checking prefix
        if not result:
            for m in models_list:
                if "gemini" in m.name.lower():
                    result.append({"name": m.name, "display_name": m.display_name})
                    
        return {"status": "success", "models": result}
    except Exception as e:
        print(f"Failed to fetch models dynamically: {e}")
        # Fallback to standard models if API throws 501 or key missing
        fallback_models = [
            {"name": "gemini-3.1-pro-preview", "display_name": "Gemini 3.1 Pro (Preview)"},
            {"name": "gemini-3.5-flash", "display_name": "Gemini 3.5 Flash"},
            {"name": "gemini-2.5-flash", "display_name": "Gemini 2.5 Flash"},
            {"name": "gemini-1.5-pro", "display_name": "Gemini 1.5 Pro"},
            {"name": "gemini-1.5-flash", "display_name": "Gemini 1.5 Flash"},
        ]
        return {"status": "success", "models": fallback_models}

class SectionItem(BaseModel):
    id: str
    title: str
    level: int
    index: int
    context: Optional[str] = ""

class GenerateRequest(BaseModel):
    sections: List[SectionItem]
    global_guidelines: Optional[str] = ""
    flash_model: Optional[str] = "gemini-3.5-flash"

class RewriteRequest(BaseModel):
    instruction: str
    current_outline: List[dict]
    active_chapter_id: Optional[str] = None
    system_prompt: Optional[str] = None
    pro_model: Optional[str] = "gemini-3.1-pro"

MAX_CONCURRENCY = 5
global_dify_semaphore = None

async def call_dify_workflow(section: SectionItem, global_guidelines: str, flash_model: str) -> dict:
    global global_dify_semaphore
    if global_dify_semaphore is None:
        global_dify_semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
        
    dify_url = os.getenv("DIFY_API_URL", "http://38.60.91.23/v1").rstrip("/") + "/workflows/run"
    dify_key = os.getenv("DIFY_API_KEY", "")
    
    async with global_dify_semaphore:
        headers = {
            "Authorization": f"Bearer {dify_key}",
            "Content-Type": "application/json"
        }
        
        # --- Pre-process context using Gemini Flash Model ---
        detailed_context = section.context
        try:
            gemini_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
            if gemini_key:
                client = genai.Client(api_key=gemini_key)
                prompt = f"""请根据大纲标题和全局规范，为该章节生成极度详尽的指导上下文和内容骨架，以便下游系统(如DeepSeek)能够生成长篇幅、高质量的最终内容。

章节标题: {section.title}
已有上下文: {section.context}
全局规范: {global_guidelines}

核心要求:
1. 强制扩充维度：将该章节拆分为至少3-5个具体的子话题或小节。
2. 明确字数要求：在指导中明确要求下游模型在每个子话题上输出大量细节（例如“每个子点展开说明不少于300-500字”）。
3. 丰富内容形式：明确指示哪些子话题适合用 Markdown 表格进行对比分析，哪些适合用 Mermaid 流程图展示业务逻辑。
4. 【审慎原则（极为重要）】：作为上游指令生成者，不可僭越。当前如果没有充足的真实项目背景，宁可生成模棱两可或预留空白的指导，也**绝对不可**随意脑补编造不符项目真实情况的事实（如虚构项目综述、融资金额、特定客户名称等），必须严谨务实。
5. 【排版与标号限制】：明确要求下游模型在生成正文时，**禁止**带入“第一节”、“1.3”等章节自编号（因为当前处理的已经是最低级别叶子节点）。同时，明确指示下游模型**严格限制 Markdown 粗体（**）的使用频率**，回归正式严肃的公文排版风格，避免过度加粗渲染。

请输出详尽、明确的指示和内容框架要点："""
                
                flash_start_time = time.time()
                flash_response = client.models.generate_content(
                    model=flash_model or "gemini-2.5-flash",
                    contents=prompt,
                )
                flash_latency = time.time() - flash_start_time
                
                if flash_response.text:
                    detailed_context = flash_response.text
                    
                flash_usage = None
                if hasattr(flash_response, 'usage_metadata') and flash_response.usage_metadata:
                    flash_usage = {
                        "prompt_token_count": getattr(flash_response.usage_metadata, 'prompt_token_count', 0),
                        "candidates_token_count": getattr(flash_response.usage_metadata, 'candidates_token_count', 0),
                        "total_token_count": getattr(flash_response.usage_metadata, 'total_token_count', 0)
                    }
                    
                log_llm_request_async(
                    scenario="dify_pre_process",
                    model_used=flash_model,
                    input_payload={"prompt": prompt},
                    output_payload={"generated_context": detailed_context},
                    latency=flash_latency,
                    usage_data=flash_usage
                )
        except Exception as e:
            print(f"Error generating pre-context with Gemini: {e}")
            log_llm_request_async(
                scenario="dify_pre_process_error",
                model_used=flash_model,
                input_payload={"prompt": f"章节标题: {section.title}"},
                output_payload={"error": str(e)},
                latency=0.0,
                usage_data=None
            )
            # Fallback to the original context
        # ----------------------------------------------------

        # 拦截并强化传入 Dify 的全局规范
        enhanced_global_guidelines = global_guidelines + """\n\n【全局执行严格规范】：
1. 禁止自编号：你负责生成的内容属于大纲的最低叶子节点，正文中**绝对禁止**自行加入“第一章”、“第二节”、“1.3”、“1.4”等任何章节标号或大纲层级结构。
2. 严肃公文排版：**严格限制** Markdown 粗体（**）的使用频率。只有在极少数绝对核心的术语或指标上才允许加粗，严禁大段落或过度频繁的加粗行为，必须回归正式严肃的公文排版风格。"""

        payload = {
            "inputs": {
                "section_id": section.id,
                "section_title": section.title,
                "context": detailed_context,
                "global_guidelines": enhanced_global_guidelines
            },
            "response_mode": "blocking",
            "user": "fastapi-backend"
        }
        
        try:
            dify_start_time = time.time()
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(dify_url, headers=headers, json=payload)
                dify_latency = time.time() - dify_start_time
                response.raise_for_status()
                data = response.json()
                
                dify_usage = data.get("data", {}).get("outputs", {}).get("usage", {})
                
                log_llm_request_async(
                    scenario="dify_workflow",
                    model_used="dify-api",
                    input_payload=payload,
                    output_payload=data,
                    latency=dify_latency,
                    usage_data=dify_usage
                )
                
                # 解析 Dify 阻塞模式返回的数据结构
                if "data" in data and "outputs" in data["data"] and "result" in data["data"]["outputs"]:
                    result_str = data["data"]["outputs"]["result"]
                    
                    # 剔除 <think>...</think> 标签及其内容
                    result_str = re.sub(r'<think>.*?</think>', '', result_str, flags=re.DOTALL).strip()
                    
                    # 剔除整个外层可能包裹的 markdown 代码块标签
                    if result_str.startswith("```markdown") and result_str.endswith("```"):
                        result_str = result_str[11:-3].strip()
                    elif result_str.startswith("```") and result_str.endswith("```"):
                        # 处理 ``` 后面可能跟着的语言如 html, json (尽管按照约定只该输出markdown)
                        lines = result_str.split("\n")
                        if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].strip() == "```":
                            result_str = "\n".join(lines[1:-1]).strip()
                    
                    return {"section_id": section.id, "status": "success", "data": result_str}
                else:
                    return {"section_id": section.id, "status": "error", "error": f"Invalid Dify response: {data}"}
        except httpx.HTTPStatusError as e:
            return {"section_id": section.id, "status": "error", "error": f"HTTP Error {e.response.status_code}: {e.response.text}"}
        except Exception as e:
            return {"section_id": section.id, "status": "error", "error": str(e)}

@app.post("/generate")
async def generate_sections(request: GenerateRequest):
    tasks = []
    for section in request.sections:
        tasks.append(call_dify_workflow(section, request.global_guidelines, request.flash_model))
        
    results = await asyncio.gather(*tasks)
    
    return {
        "status": "completed",
        "results": results
    }

class ExportRequest(BaseModel):
    project_id: Optional[str] = None
    outline: List[dict]

@app.post("/export-outline")
async def export_outline(request: ExportRequest, db: Session = Depends(get_db)):
    try:
        template_path = None
        if request.project_id:
            project = db.query(models.Project).filter(models.Project.id == request.project_id).first()
            if project and project.template_path:
                template_path = project.template_path
                
        buffer = rebuild_docx_from_outline(request.outline, template_path=template_path)
        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": "attachment; filename=outline_skeleton.docx"}
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}

@app.post("/commander/rewrite-outline")
async def rewrite_outline(request: RewriteRequest):
    try:
        new_outline = await rewrite_outline_with_gemini(
            user_instruction=request.instruction,
            current_outline=request.current_outline,
            active_chapter_id=request.active_chapter_id,
            system_prompt=request.system_prompt,
            model_name=request.pro_model
        )
        # 也可以在这里调用 docx_builder 生成新的框架文档
        # buffer = rebuild_docx_from_outline(new_outline)
        # 例如可以存一份 skeleton.docx，或者直接返回下载
        
        # 对于返回，如果 new_outline 是 BaseModel 的实例，转成 dict
        if new_outline and hasattr(new_outline[0], 'model_dump'):
            parsed_outline = [item.model_dump() for item in new_outline]
        elif new_outline and hasattr(new_outline[0], 'dict'):
            parsed_outline = [item.dict() for item in new_outline]
        else:
            parsed_outline = new_outline
            
        return {
            "status": "success",
            "outline": parsed_outline
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}

@app.post("/commander/rewrite-stream")
async def rewrite_stream(request: RewriteRequest):
    async def event_generator():
        try:
            async for chunk in stream_rewrite_outline_with_gemini(
                user_instruction=request.instruction,
                current_outline=request.current_outline,
                active_chapter_id=request.active_chapter_id,
                system_prompt=request.system_prompt,
                model_name=request.pro_model
            ):
                yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"
        except Exception as e:
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/upload")
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    doc = Document(io.BytesIO(content))
    
    flat_outline = []
    for i, paragraph in enumerate(doc.paragraphs):
        text = paragraph.text.strip()
        if not text:
            continue
            
        level = get_outline_level(paragraph)
        if level is not None:
            flat_outline.append({
                "id": f"node-{len(flat_outline) + 1}",
                "title": text,
                "level": level,
                "index": i # 保留原始段落索引
            })
            
    # Save to database
    db_project = models.Project(
        filename=file.filename,
        outline=flat_outline
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    
    # Save the physical file as template
    uploads_dir = os.path.join(os.path.dirname(__file__), "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    template_path = os.path.join(uploads_dir, f"{db_project.id}.docx")
    with open(template_path, "wb") as f:
        f.write(content)
        
    db_project.template_path = template_path
    db.commit()
    db.refresh(db_project)
    
    return {
        "project_id": db_project.id,
        "filename": db_project.filename, 
        "status": "processed",
        "outline": flat_outline
    }


@app.get("/project/latest")
async def get_latest_project(db: Session = Depends(get_db)):
    project = db.query(models.Project).order_by(models.Project.updated_at.desc()).first()
    if not project:
        return {"status": "empty"}
    return {
        "status": "success",
        "project_id": project.id,
        "filename": project.filename,
        "outline": project.outline
    }

class UpdateOutlineRequest(BaseModel):
    outline: List[dict]

@app.put("/project/{project_id}/outline")
async def update_project_outline(project_id: str, request: UpdateOutlineRequest, db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        return {"status": "error", "error": "Project not found"}
        
    project.outline = request.outline
    db.commit()
    return {"status": "success"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
