import io
import os
import re
import base64
import zlib
import requests
import json
import mistune
from docx import Document
from docx.shared import Inches
from docx.oxml.shared import OxmlElement
from docx.oxml.ns import qn
from typing import List, Dict, Any
import time
import asyncio
import uuid
import httpx

def render_mermaid_to_image(mermaid_code: str) -> io.BytesIO:
    """Fetch PNG from kroki using POST method for large payloads"""
    url = os.getenv("KROKI_URL", "http://kroki:8000/mermaid/png")
    headers = {
        "Content-Type": "text/plain",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    for attempt in range(3):
        try:
            response = requests.post(url, data=mermaid_code.strip().encode('utf-8'), headers=headers, timeout=15)
            response.raise_for_status()
            return io.BytesIO(response.content)
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                error_msg = e.response.text
            print(f"Failed to render mermaid (attempt {attempt + 1}): {error_msg}")
            if attempt < 2:
                time.sleep(1)
    return None

def clear_document(doc: Document):
    for paragraph in doc.paragraphs:
        p = paragraph._element
        p.getparent().remove(p)
        paragraph._p = paragraph._element = None
    for table in doc.tables:
        tbl = table._element
        tbl.getparent().remove(tbl)
        table._tbl = table._element = None

def set_table_width_100(table):
    tbl = table._tbl
    tblPr = tbl.tblPr
    tblW = OxmlElement('w:tblW')
    tblW.set(qn('w:w'), '5000') # 5000 pct = 100% width
    tblW.set(qn('w:type'), 'pct')
    tblPr.append(tblW)

def render_inline(runs_container, children, bold=False, italic=False):
    if not children:
        return
    for child in children:
        ctype = child.get("type")
        if ctype == "text":
            run = runs_container.add_run(child.get("raw", ""))
            if bold: run.bold = True
            if italic: run.italic = True
        elif ctype == "strong":
            render_inline(runs_container, child.get("children", []), bold=True, italic=italic)
        elif ctype == "emphasis":
            render_inline(runs_container, child.get("children", []), bold=bold, italic=True)
        elif ctype == "codespan":
            run = runs_container.add_run(child.get("raw", ""))
            if bold: run.bold = True
            if italic: run.italic = True
        else:
            if "raw" in child:
                run = runs_container.add_run(child.get("raw", ""))
            elif "children" in child:
                render_inline(runs_container, child.get("children", []), bold=bold, italic=italic)

def render_ast_to_docx(doc, ast_nodes, mermaid_cache=None):
    for node in ast_nodes:
        ctype = node.get("type")
        
        if ctype == "paragraph":
            p = doc.add_paragraph()
            render_inline(p, node.get("children", []))
            
        elif ctype == "heading":
            # 降级渲染正文中的 Markdown 标题，防止污染 Word 官方 TOC 目录
            p = doc.add_paragraph()
            render_inline(p, node.get("children", []), bold=True)
            
        elif ctype == "list":
            children = node.get("children", [])
            is_ordered = node.get("attrs", {}).get("ordered", False)
            for li in children:
                if li.get("type") == "list_item":
                    style = 'List Number' if is_ordered else 'List Bullet'
                    try:
                        p = doc.add_paragraph(style=style)
                    except KeyError:
                        p = doc.add_paragraph()
                    li_children = li.get("children", [])
                    for lc in li_children:
                        if lc.get("type") == "block_text":
                            render_inline(p, lc.get("children", []))
                        
        elif ctype == "table":
            table_children = node.get("children", [])
            all_rows = []
            for child in table_children:
                child_type = child.get("type")
                if child_type == "table_head":
                    cells = []
                    for tc in child.get("children", []):
                        if tc.get("type") == "table_cell":
                            cells.append(tc.get("children", []))
                    if cells:
                        all_rows.append(cells)
                elif child_type == "table_body":
                    for tr in child.get("children", []):
                        if tr.get("type") == "table_row":
                            cells = []
                            for tc in tr.get("children", []):
                                if tc.get("type") == "table_cell":
                                    cells.append(tc.get("children", []))
                            if cells:
                                all_rows.append(cells)
            
            if all_rows and all_rows[0]:
                try:
                    table = doc.add_table(rows=len(all_rows), cols=len(all_rows[0]))
                    try:
                        table.style = 'Table Grid'
                    except KeyError:
                        pass
                    set_table_width_100(table)
                    for r_idx, row_data in enumerate(all_rows):
                        for c_idx, cell_ast in enumerate(row_data):
                            if c_idx < len(table.columns):
                                cell = table.cell(r_idx, c_idx)
                                cell.text = "" # Clear default paragraph text
                                p = cell.paragraphs[0]
                                render_inline(p, cell_ast)
                except Exception as e:
                    print(f"Table generation error: {e}")
                    
        elif ctype == "block_code":
            info = node.get("attrs", {}).get("info", "")
            val = node.get("raw", "")
            if info and info.strip().lower() == "mermaid":
                img_stream = None
                if mermaid_cache and val in mermaid_cache:
                    img_data = mermaid_cache[val]
                    if img_data:
                        img_stream = io.BytesIO(img_data)
                else:
                    img_stream = render_mermaid_to_image(val)
                if img_stream:
                    doc.add_picture(img_stream, width=Inches(5.0))
                else:
                    doc.add_paragraph(f"[图表渲染失败: 大模型生成的 Mermaid 语法错误或网络异常]\n```mermaid\n{val}\n```")
            else:
                doc.add_paragraph(val)

def rebuild_docx_from_outline(outline: List[Dict], template_path: str = None) -> io.BytesIO:
    if template_path and os.path.exists(template_path):
        try:
            doc = Document(template_path)
            clear_document(doc)
        except Exception as e:
            print(f"Failed to load template {template_path}: {e}")
            doc = Document()
    else:
        doc = Document()
    
    md_parser = mistune.create_markdown(renderer='ast', plugins=['table'])
    
    for item in outline:
        title = item.get("title", "")
        level = item.get("level", 1)
        content = item.get("content", "")
        
        if level < 1: level = 1
        elif level > 9: level = 9
            
        style_name = f"Heading {level}"
        
        try:
            doc.add_paragraph(title, style=style_name)
        except KeyError:
            doc.add_paragraph(title)
            
        if content:

            ast_nodes = md_parser(content)
            render_ast_to_docx(doc, ast_nodes)
    
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    
    return buffer

async def fetch_mermaid_async(client: httpx.AsyncClient, code: str, sem: asyncio.Semaphore = None):
    async def _do_fetch():
        url = os.getenv("KROKI_URL", "http://kroki:8000/mermaid/png")
        headers = {
            "Content-Type": "text/plain",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        for attempt in range(3):
            try:
                response = await client.post(url, content=code.strip().encode('utf-8'), headers=headers, timeout=25.0)
                response.raise_for_status()
                return code, response.content
            except Exception as e:
                if attempt < 2:
                    await asyncio.sleep(2)
        return code, None

    if sem:
        async with sem:
            return await _do_fetch()
    return await _do_fetch()

def extract_mermaid_codes(ast_nodes):
    codes = set()
    for node in ast_nodes:
        if node.get("type") == "block_code":
            info = node.get("attrs", {}).get("info", "")
            if info and info.strip().lower() == "mermaid":
                codes.add(node.get("raw", ""))
    return codes

async def rebuild_docx_from_outline_stream(outline: List[Dict], template_path: str = None):
    yield json.dumps({"type": "progress", "percent": 2, "message": "正在解析文档大纲与语法树..."}) + "\n\n"
    
    def init_doc():
        if template_path and os.path.exists(template_path):
            try:
                doc = Document(template_path)
                clear_document(doc)
                return doc
            except Exception as e:
                print(f"Failed to load template {template_path}: {e}")
        return Document()
        
    doc = await asyncio.to_thread(init_doc)
    md_parser = mistune.create_markdown(renderer='ast', plugins=['table'])
    
    # 1. Parse AST sequentially (very fast, < 0.1s)
    parsed_outlines = []
    mermaid_codes = set()
    for item in outline:
        content = item.get("content", "")
        if content:
            ast_nodes = md_parser(content)
            mermaid_codes.update(extract_mermaid_codes(ast_nodes))
            parsed_outlines.append((item, ast_nodes))
        else:
            parsed_outlines.append((item, []))

    yield json.dumps({"type": "progress", "percent": 5, "message": f"语法树解析完成，发现 {len(mermaid_codes)} 个架构图..."}) + "\n\n"
    
    # 2. Concurrently fetch all Mermaid diagrams
    mermaid_cache = {}
    if mermaid_codes:
        sem = asyncio.Semaphore(3)
        async with httpx.AsyncClient() as client:
            tasks = [fetch_mermaid_async(client, code, sem) for code in mermaid_codes]
            total_mermaids = len(tasks)
            completed_mermaids = 0
            for coro in asyncio.as_completed(tasks):
                code, img_data = await coro
                mermaid_cache[code] = img_data
                completed_mermaids += 1
                percent = 5 + int((completed_mermaids / total_mermaids) * 45) # 5% to 50%
                yield json.dumps({"type": "progress", "percent": percent, "message": f"并发请求架构图 ({completed_mermaids}/{total_mermaids})..."}) + "\n\n"
    else:
        yield json.dumps({"type": "progress", "percent": 50, "message": "无需下载架构图，准备排版..."}) + "\n\n"

    # 3. Assemble DOCX sequentially (CPU bound but fast with cached images)
    total_nodes = len(parsed_outlines)
    for idx, (item, ast_nodes) in enumerate(parsed_outlines):
        title = item.get("title", "")
        level = item.get("level", 1)
        if level < 1: level = 1
        elif level > 9: level = 9
            
        style_name = f"Heading {level}"
        
        percent = 50 + int((idx / total_nodes) * 49) # 50% to 99%
        yield json.dumps({"type": "progress", "percent": percent, "message": f"正在排版: {title}"}) + "\n\n"
        
        def render_node(doc_obj, t, s_name, nodes, cache):
            try:
                doc_obj.add_paragraph(t, style=s_name)
            except KeyError:
                doc_obj.add_paragraph(t)
            if nodes:
                render_ast_to_docx(doc_obj, nodes, cache)
                
        await asyncio.to_thread(render_node, doc, title, style_name, ast_nodes, mermaid_cache)
        await asyncio.sleep(0.01)
        
    yield json.dumps({"type": "progress", "percent": 99, "message": "正在保存并落盘..."}) + "\n\n"
    
    def save_doc():
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        
        uploads_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
        os.makedirs(uploads_dir, exist_ok=True)
        file_id = f"export_{uuid.uuid4().hex[:8]}.docx"
        file_path = os.path.join(uploads_dir, file_id)
        
        with open(file_path, "wb") as f:
            f.write(buffer.getvalue())
            
        return file_id
        
    file_id = await asyncio.to_thread(save_doc)
    yield json.dumps({"type": "complete", "download_url": f"/download/{file_id}"}) + "\n\n"
