import os
import json
from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import List

class OutlineItemModel(BaseModel):
    id: str
    title: str
    level: int
    index: int

class RewriteResponse(BaseModel):
    outline: list[OutlineItemModel]

async def rewrite_outline_with_gemini(user_instruction: str, current_outline: List[dict], active_chapter_id: str = None) -> List[dict]:
    """
    Call Gemini 3.1 Pro to rewrite the document outline based on user instructions.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY is not set in environment variables")
        
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.1-pro-preview")
    
    # Initialize the new google-genai client
    client = genai.Client(api_key=api_key)
    
    # Convert current outline to a readable string format for the model
    outline_str = json.dumps(current_outline, ensure_ascii=False, indent=2)
    
    context_msg = ""
    if active_chapter_id:
        context_msg = f"\nThe user is currently focusing on chapter/section with ID: '{active_chapter_id}'. "
        
    prompt = f"""
You are an expert Bid Architect (Commander).{context_msg}
The user wants to modify the following Bid Document Outline based on their instructions.

CURRENT OUTLINE:
{outline_str}

USER INSTRUCTION:
{user_instruction}

TASK:
Generate a completely new outline structure that incorporates the user's instructions.
Ensure that the output forms a logical document structure.
Levels usually go from 1 to 4. Level 1 is Chapter, Level 2 is Section, etc.
The 'id' should reflect the hierarchy, e.g., '1', '1.1', '1.1.1'.
The 'index' can just be a sequential number starting from 0.

OUTPUT FORMAT:
Return ONLY a JSON dictionary with a single key "outline" containing a list of objects matching the OutlineItemModel schema.
For example:
{{
  "outline": [
    {{"id": "1", "title": "第一章...", "level": 1, "index": 0}},
    {{"id": "1.1", "title": "1.1...", "level": 2, "index": 1}}
  ]
}}
"""
    
    # Generate content with structured output
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )
    
    # Parse the response
    try:
        if not response.text:
            raise ValueError("Empty response from Gemini")
            
        result = json.loads(response.text)
        return result.get("outline", [])
    except Exception as e:
        print(f"Error parsing Gemini response: {e}")
        print(f"Raw response: {response.text}")
        raise e

import time

async def stream_rewrite_outline_with_gemini(user_instruction: str, current_outline: List[dict], active_chapter_id: str = None):
    """
    Call Gemini 3.1 Pro to rewrite the document outline, returning an async stream of chunks.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY is not set in environment variables")
        
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.1-pro-preview")
    
    # Initialize the new google-genai client
    client = genai.Client(api_key=api_key)
    
    # Convert current outline to a readable string format for the model
    outline_str = json.dumps(current_outline, ensure_ascii=False, indent=2)
    
    context_msg = ""
    if active_chapter_id:
        context_msg = f"\nThe user is currently focusing on chapter/section with ID: '{active_chapter_id}'. "
        
    prompt = f"""
You are an expert Bid Architect (Commander).{context_msg}
The user wants to modify the following Bid Document Outline based on their instructions.

CURRENT OUTLINE:
{outline_str}

USER INSTRUCTION:
{user_instruction}

TASK:
1. FIRST, analyze the user's instructions and think step-by-step about how to modify the outline.
2. THEN, generate a completely new outline structure that incorporates the user's instructions.
Ensure that the output forms a logical document structure.
Levels usually go from 1 to 4. Level 1 is Chapter, Level 2 is Section, etc.
The 'id' should reflect the hierarchy, e.g., '1', '1.1', '1.1.1'.
The 'index' can just be a sequential number starting from 0.

OUTPUT FORMAT:
Provide your step-by-step reasoning first. Then, you MUST output the final outline inside a markdown json block:
```json
{{
  "outline": [
    {{"id": "1", "title": "第一章...", "level": 1, "index": 0}},
    {{"id": "1.1", "title": "1.1...", "level": 2, "index": 1}}
  ]
}}
```
"""
    
    start_time = time.time()
    
    # Use the async client `client.aio` for streaming in FastAPI
    response_stream = client.aio.models.generate_content_stream(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
        ),
    )
    
    async for chunk in response_stream:
        if chunk.text:
            yield chunk.text
            
    elapsed = time.time() - start_time
    yield f"\n\n[TOTAL_TIME:{elapsed:.1f}s]"
