import os
import json
from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import List
import time
from .logger import log_llm_request_async
class OutlineItemModel(BaseModel):
    id: str
    title: str
    level: int
    index: int

class RewriteResponse(BaseModel):
    outline: list[OutlineItemModel]

async def rewrite_outline_with_gemini(user_instruction: str, current_outline: List[dict], active_chapter_id: str = None, system_prompt: str = None, model_name: str = None) -> List[dict]:
    """
    Call Gemini 3.1 Pro to rewrite the document outline based on user instructions.
    """
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY is not set in environment variables")
        
    actual_model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-3.1-pro-preview")
    
    # Initialize the new google-genai client
    client = genai.Client(api_key=api_key)
    
    # Convert current outline to a readable string format for the model
    outline_str = json.dumps(current_outline, ensure_ascii=False, indent=2)
    
    context_msg = ""
    if active_chapter_id:
        context_msg = f"\nThe user is currently focusing on chapter/section with ID: '{active_chapter_id}'. "
        
    sys_p = system_prompt if system_prompt else f"You are an expert Bid Architect (Commander).{context_msg}"
    prompt = f"""
{sys_p}
{context_msg}

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
    
    start_time = time.time()
    
    # Generate content with structured output
    response = client.models.generate_content(
        model=actual_model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )
    
    latency = time.time() - start_time
    
    usage_data = None
    if hasattr(response, 'usage_metadata') and response.usage_metadata:
        usage_data = {
            "prompt_token_count": getattr(response.usage_metadata, 'prompt_token_count', 0),
            "candidates_token_count": getattr(response.usage_metadata, 'candidates_token_count', 0),
            "total_token_count": getattr(response.usage_metadata, 'total_token_count', 0)
        }

    # Parse the response
    try:
        if not response.text:
            raise ValueError("Empty response from Gemini")
            
        result = json.loads(response.text)
        
        # Log request
        log_llm_request_async(
            scenario="outline_rewrite",
            model_used=actual_model_name,
            input_payload={"prompt": prompt},
            output_payload=result,
            latency=latency,
            usage_data=usage_data
        )
        
        return result.get("outline", [])
    except Exception as e:
        print(f"Error parsing Gemini response: {e}")
        print(f"Raw response: {response.text if hasattr(response, 'text') else str(response)}")
        
        log_llm_request_async(
            scenario="outline_rewrite_error",
            model_used=actual_model_name,
            input_payload={"prompt": prompt},
            output_payload={"error": str(e), "raw_response": response.text if hasattr(response, 'text') else str(response)},
            latency=latency,
            usage_data=usage_data
        )
        raise e

import time

async def stream_rewrite_outline_with_gemini(user_instruction: str, current_outline: List[dict], active_chapter_id: str = None, system_prompt: str = None, model_name: str = None):
    """
    Call Gemini 3.1 Pro to rewrite the document outline, returning an async stream of chunks.
    """
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY is not set in environment variables")
        
    actual_model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-3.1-pro-preview")
    
    # Initialize the new google-genai client
    client = genai.Client(api_key=api_key)
    
    # Convert current outline to a readable string format for the model
    outline_str = json.dumps(current_outline, ensure_ascii=False, indent=2)
    
    context_msg = ""
    if active_chapter_id:
        context_msg = f"\nThe user is currently focusing on chapter/section with ID: '{active_chapter_id}'. "
        
    sys_p = system_prompt if system_prompt else f"You are an expert Bid Architect (Commander).{context_msg}"
    prompt = f"""
{sys_p}
{context_msg}

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
        model=actual_model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
        ),
    )
    
    full_response = ""
    usage_data = None
    
    async for chunk in response_stream:
        if chunk.text:
            yield chunk.text
            full_response += chunk.text
            
        if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
            # The final chunk usually contains the total usage metadata
            usage_data = {
                "prompt_token_count": getattr(chunk.usage_metadata, 'prompt_token_count', 0),
                "candidates_token_count": getattr(chunk.usage_metadata, 'candidates_token_count', 0),
                "total_token_count": getattr(chunk.usage_metadata, 'total_token_count', 0)
            }
            
    elapsed = time.time() - start_time
    
    # Log stream request
    log_llm_request_async(
        scenario="outline_rewrite_stream",
        model_used=actual_model_name,
        input_payload={"prompt": prompt},
        output_payload={"response_text": full_response},
        latency=elapsed,
        usage_data=usage_data
    )
    
    yield f"\n\n[TOTAL_TIME:{elapsed:.1f}s]"
