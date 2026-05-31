import sys

with open('backend/main.py', 'r') as f:
    content = f.read()

# Add imports
imports = """from sqlalchemy.orm import Session
from database import engine, get_db
import models
from fastapi import Depends

# Initialize database
models.Base.metadata.create_all(bind=engine)
"""

content = content.replace("from services.docx_builder import rebuild_docx_from_outline\n", "from services.docx_builder import rebuild_docx_from_outline\n" + imports)

# Update Upload endpoint to save project
upload_old = """@app.post("/upload")
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
    }"""

upload_new = """@app.post("/upload")
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
    }"""

content = content.replace(upload_old, upload_new)

# Add Project Endpoints
project_endpoints = """
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
"""

content = content.replace("if __name__ == \"__main__\":", project_endpoints + "\nif __name__ == \"__main__\":")

with open('backend/main.py', 'w') as f:
    f.write(content)

print("Backend patched.")
