import re
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from docx import Document
import uvicorn
import io

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
