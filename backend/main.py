import re
from fastapi import FastAPI, UploadFile, File
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

# 匹配标题编号的正则，例如 1.1, 1.1.1, 第一章, 一、 等
TITLE_RE = re.compile(r'^(\d+(\.\d+)*|第[一二三四五六七八九十]+[章节]|[\u2460-\u2469]|[一二三四五六七八九十]+[、])')

def get_outline_level(paragraph):
    """尝试获取段落的大纲级别"""
    # 1. 检查样式名
    if paragraph.style.name.startswith('Heading'):
        try:
            return int(paragraph.style.name.split(' ')[-1])
        except (ValueError, IndexError):
            pass
    
    # 2. 检查 XML 中的 outlineLevel
    p_pr = paragraph._element.get_or_add_pPr()
    outline_lvl = p_pr.xpath('./w:outlineLvl')
    if outline_lvl:
        return int(outline_lvl[0].get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val')) + 1
    
    # 3. 如果文本符合标题正则，尝试根据点号数量推断级别
    text = paragraph.text.strip()
    match = TITLE_RE.match(text)
    if match:
        dot_count = text.split(' ')[0].count('.')
        if dot_count > 0:
            return dot_count + 1
        if '章' in text:
            return 1
        return 2 # 默认二级
        
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

MAX_CONCURRENCY = 5

async def call_dify_workflow(section: SectionItem, global_guidelines: str, semaphore: asyncio.Semaphore) -> dict:
    dify_url = os.getenv("DIFY_API_URL", "http://38.60.91.23/v1").rstrip("/") + "/workflows/run"
    dify_key = os.getenv("DIFY_API_KEY", "")
    
    async with semaphore:
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
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    
    tasks = []
    for section in request.sections:
        tasks.append(call_dify_workflow(section, request.global_guidelines, semaphore))
        
    results = await asyncio.gather(*tasks)
    
    return {
        "status": "completed",
        "results": results
    }

@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
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
    
    return {
        "filename": file.filename, 
        "status": "processed",
        "outline": flat_outline
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
