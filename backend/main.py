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

from services.commander import rewrite_outline_with_gemini, stream_rewrite_outline_with_gemini
from services.docx_builder import rebuild_docx_from_outline
from sqlalchemy.orm import Session
from database import engine, get_db
import models
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

class SectionItem(BaseModel):
    id: str
    title: str
    level: int
    index: int
    context: Optional[str] = ""

class GenerateRequest(BaseModel):
    sections: List[SectionItem]
    global_guidelines: Optional[str] = ""

class RewriteRequest(BaseModel):
    instruction: str
    current_outline: List[dict]
    active_chapter_id: Optional[str] = None

MAX_CONCURRENCY = 5
global_dify_semaphore = None

async def call_dify_workflow(section: SectionItem, global_guidelines: str) -> dict:
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
        payload = {
            "inputs": {
                "section_id": section.id,
                "section_title": section.title,
                "context": section.context,
                "global_guidelines": global_guidelines
            },
            "response_mode": "blocking",
            "user": "fastapi-backend"
        }
        
        try:
            # 延长超时时间，生成长文本可能需要更久
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(dify_url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                
                # 解析 Dify 阻塞模式返回的数据结构
                if "data" in data and "outputs" in data["data"] and "result" in data["data"]["outputs"]:
                    result_str = data["data"]["outputs"]["result"]
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
        tasks.append(call_dify_workflow(section, request.global_guidelines))
        
    results = await asyncio.gather(*tasks)
    
    return {
        "status": "completed",
        "results": results
    }

class ExportRequest(BaseModel):
    outline: List[dict]

@app.post("/export-outline")
async def export_outline(request: ExportRequest):
    try:
        buffer = rebuild_docx_from_outline(request.outline)
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
            active_chapter_id=request.active_chapter_id
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
                active_chapter_id=request.active_chapter_id
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
