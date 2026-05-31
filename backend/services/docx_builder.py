import io
from docx import Document
from typing import List, Dict

def rebuild_docx_from_outline(outline: List[Dict]) -> io.BytesIO:
    """
    Creates a new Word document containing only the headings defined in the new outline.
    """
    doc = Document()
    
    for item in outline:
        title = item.get("title", "")
        level = item.get("level", 1)
        
        # Word styles: Heading 1, Heading 2, etc. (up to Heading 9)
        # If level is out of bounds, default to Normal or max heading
        if level < 1:
            level = 1
        elif level > 9:
            level = 9
            
        style_name = f"Heading {level}"
        
        # Add the paragraph with the specified heading style
        try:
            doc.add_paragraph(title, style=style_name)
        except KeyError:
            # If the style doesn't exist in the default template, just add normal paragraph
            p = doc.add_paragraph(title)
            # and try to set outlineLvl manually if needed, 
            # but usually 'Heading X' exists in the default python-docx template.
            
    # Save to an in-memory buffer
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    
    return buffer
