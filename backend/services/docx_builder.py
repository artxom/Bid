import io
import re
import base64
import zlib
import requests
import json
from docx import Document
from docx.shared import Inches
from typing import List, Dict, Any

def compress_mermaid(mermaid_code: str) -> str:
    """Encode mermaid string to base64 for Kroki"""
    compressed = zlib.compress(mermaid_code.encode('utf-8'), 9)
    return base64.urlsafe_b64encode(compressed).decode('utf-8')

def render_mermaid_to_image(mermaid_code: str) -> io.BytesIO:
    """Fetch PNG from kroki.io given mermaid code"""
    payload = compress_mermaid(mermaid_code)
    url = f"https://kroki.io/mermaid/png/{payload}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return io.BytesIO(response.content)
    except Exception as e:
        print(f"Failed to render mermaid: {e}")
        return None

def parse_markdown_table(table_text: str) -> List[List[str]]:
    """Parse markdown table text into 2D array of strings"""
    lines = table_text.strip().split('\n')
    rows = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Check if it's a separator row like |---|---|
        if re.match(r'^\|?[\s\-:]+\|', line):
            continue
        # Split by pipe
        parts = line.strip('|').split('|')
        rows.append([p.strip() for p in parts])
    return rows

def parse_content_to_segments(content_str: str) -> List[Dict[str, Any]]:
    """Parse Markdown (or JSON) to segments: text, chart, table"""
    if not content_str:
        return []
        
    try:
        # Try JSON format first if applicable
        data = json.loads(content_str)
        if isinstance(data, dict) and "segments" in data:
            return data["segments"]
    except Exception:
        pass
        
    segments = []
    
    lines = content_str.split('\n')
    current_text = []
    
    in_mermaid = False
    mermaid_code = []
    
    in_table = False
    table_text = []
    
    def flush_text():
        if current_text:
            text_val = '\n'.join(current_text).strip()
            if text_val:
                segments.append({"type": "text", "value": text_val})
            current_text.clear()
            
    for line in lines:
        stripped = line.strip()
        
        # Handle mermaid blocks
        if not in_mermaid and stripped.startswith('```mermaid'):
            flush_text()
            in_mermaid = True
            continue
        elif in_mermaid:
            if stripped.startswith('```'):
                in_mermaid = False
                segments.append({"type": "chart", "format": "mermaid", "value": '\n'.join(mermaid_code)})
                mermaid_code.clear()
            else:
                mermaid_code.append(line)
            continue
            
        # Handle table blocks (simple heuristic: starts with | and contains |)
        if stripped.startswith('|') and stripped.endswith('|'):
            if not in_table:
                flush_text()
                in_table = True
            table_text.append(line)
            continue
        elif in_table:
            # End of table
            in_table = False
            segments.append({"type": "table", "format": "markdown", "value": '\n'.join(table_text)})
            table_text.clear()
            
        # If normal text
        current_text.append(line)
        
    flush_text()
    if in_table:
        segments.append({"type": "table", "format": "markdown", "value": '\n'.join(table_text)})
        
    return segments

def rebuild_docx_from_outline(outline: List[Dict]) -> io.BytesIO:
    doc = Document()
    
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
            segments = parse_content_to_segments(content)
            for seg in segments:
                t = seg.get("type")
                val = seg.get("value", "")
                
                if t == "text":
                    doc.add_paragraph(val)
                elif t == "chart" and seg.get("format") == "mermaid":
                    img_stream = render_mermaid_to_image(val)
                    if img_stream:
                        doc.add_picture(img_stream, width=Inches(5.0))
                    else:
                        doc.add_paragraph(f"[图表渲染失败]\n```mermaid\n{val}\n```")
                elif t == "table" and seg.get("format") == "markdown":
                    rows = parse_markdown_table(val)
                    if rows:
                        try:
                            table = doc.add_table(rows=len(rows), cols=len(rows[0]))
                            table.style = 'Table Grid'
                            for row_idx, row_data in enumerate(rows):
                                for col_idx, cell_text in enumerate(row_data):
                                    if col_idx < len(table.columns):
                                        table.cell(row_idx, col_idx).text = cell_text
                        except Exception as e:
                            print(f"Table generation error: {e}")
                            doc.add_paragraph(val)
    
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    
    return buffer
