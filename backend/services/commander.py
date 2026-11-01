import os
import json
from openai import AsyncOpenAI
from pydantic import BaseModel
from typing import List
import time
from .logger import log_llm_request_async

class OutlineItemModel(BaseModel):
    id: str
    title: str
    level: int
    index: int
    context: str = ""

def get_outline_context_and_target(outline: list, active_id: str):
    active_idx = next((i for i, item in enumerate(outline) if item.get('id') == active_id), -1)
    if active_idx == -1:
        return outline, outline, 0, len(outline) # fallback

    active_level = outline[active_idx].get('level', 1)
    
    active_end_idx = len(outline)
    for i in range(active_idx + 1, len(outline)):
        if outline[i].get('level', 1) <= active_level:
            active_end_idx = i
            break
            
    target_nodes = outline[active_idx : active_end_idx]
    
    parent_idx = -1
    for i in range(active_idx - 1, -1, -1):
        if outline[i].get('level', 1) < active_level:
            parent_idx = i
            break
            
    context_nodes = []
    if parent_idx != -1:
        parent_level = outline[parent_idx].get('level', 1)
        context_nodes.append(outline[parent_idx])
        
        end_idx = len(outline)
        for i in range(parent_idx + 1, len(outline)):
            if outline[i].get('level', 1) <= parent_level:
                end_idx = i
                break
                
        for i in range(parent_idx + 1, end_idx):
            if outline[i].get('level', 1) == active_level and not (active_idx <= i < active_end_idx):
                context_nodes.append(outline[i])
    else:
        for i in range(len(outline)):
            if outline[i].get('level', 1) == active_level and not (active_idx <= i < active_end_idx):
                context_nodes.append(outline[i])
                
    return context_nodes, target_nodes, active_idx, active_end_idx

class RewriteResponse(BaseModel):
    outline: list[OutlineItemModel]

async def rewrite_outline_with_deepseek(user_instruction: str, current_outline: List[dict], active_chapter_id: str = None, system_prompt: str = None, model_name: str = None) -> List[dict]:
    """
    Call DeepSeek to rewrite the document outline based on user instructions.
    """
    api_key = os.getenv("DEEPSEEK_API_KEY")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY is not set in environment variables")
        
    actual_model_name = model_name or os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
    
    # Initialize the new openai client
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    
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
    response = await client.chat.completions.create(
        model=actual_model_name,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    
    latency = time.time() - start_time
    
    usage_data = None
    if response.usage:
        usage_data = {
            "prompt_token_count": getattr(response.usage, 'prompt_tokens', 0),
            "candidates_token_count": getattr(response.usage, 'completion_tokens', 0),
            "total_token_count": getattr(response.usage, 'total_tokens', 0)
        }

    # Parse the response
    try:
        if not response.choices or not response.choices[0].message.content:
            raise ValueError("Empty response from DeepSeek")
            
        result = json.loads(response.choices[0].message.content)
        
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
        print(f"Error parsing DeepSeek response: {e}")
        raw_resp = response.choices[0].message.content if response.choices else str(response)
        print(f"Raw response: {raw_resp}")
        
        log_llm_request_async(
            scenario="outline_rewrite_error",
            model_used=actual_model_name,
            input_payload={"prompt": prompt},
            output_payload={"error": str(e), "raw_response": raw_resp},
            latency=latency,
            usage_data=usage_data
        )
        raise e

async def stream_rewrite_outline_with_deepseek(user_instruction: str, current_outline: List[dict], active_chapter_id: str = None, system_prompt: str = None, model_name: str = None):
    """
    Call DeepSeek to rewrite the document outline, returning an async stream of chunks.
    """
    api_key = os.getenv("DEEPSEEK_API_KEY")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY is not set in environment variables")
        
    actual_model_name = model_name or os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
    
    # Initialize the new openai client
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    
    # Convert current outline to a readable string format for the model
    outline_str = json.dumps(current_outline, ensure_ascii=False, indent=2)
    
    if active_chapter_id:
        context_msg = f"\nThe user is currently focusing on chapter/section with ID: '{active_chapter_id}'. "
        
    context_nodes, target_nodes, active_idx, active_end_idx = get_outline_context_and_target(current_outline, active_chapter_id)
    
    context_str = json.dumps(context_nodes, ensure_ascii=False, indent=2)
    target_str = json.dumps(target_nodes, ensure_ascii=False, indent=2)
        
    sys_p = system_prompt if system_prompt else f"You are an expert Bid Architect (Commander).{context_msg}"
    prompt = f"""
{sys_p}
{context_msg}

READ-ONLY CONTEXT (Parent and Siblings):
{context_str}

TARGET SECTION TO REWRITE (Active node and its descendants):
{target_str}

USER INSTRUCTION:
{user_instruction}

TASK:
1. FIRST, analyze the user's instructions and think step-by-step about how to modify the TARGET SECTION.
2. THEN, generate a completely new structure for the TARGET SECTION that incorporates the user's instructions.
Ensure that the output forms a logical document structure.
Levels usually go from 1 to 4. Level 1 is Chapter, Level 2 is Section, etc.
The 'id' should reflect the hierarchy, e.g., '1', '1.1', '1.1.1'.
The 'index' can just be a sequential number starting from 0.
3. CRITICAL NEW REQUIREMENT: You MUST include a `context` field for EVERY node. The `context` should be a brief initial prompt (30-50 words) that gives direction to the downstream writer model about what specific content, tables, or charts should be written in this section.

OUTPUT FORMAT:
Provide your step-by-step reasoning first. Then, you MUST output the final modified TARGET SECTION inside a markdown json block.
DO NOT return the READ-ONLY CONTEXT nodes. Your output will exactly replace the TARGET SECTION in the full document.

```json
{{
  "outline": [
    {{"id": "1.2", "title": "1.2...", "level": 2, "index": 1, "context": "本节主要介绍..."}},
    {{"id": "1.2.1", "title": "1.2.1...", "level": 3, "index": 2, "context": "使用Markdown表格对比..."}}
  ]
}}
```
"""
    
    start_time = time.time()
    
    response_stream = await client.chat.completions.create(
        model=actual_model_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        stream=True
    )
    
    full_response = ""
    usage_data = None
    
    async for chunk in response_stream:
        # Check if the chunk contains content
        if chunk.choices and chunk.choices[0].delta.content:
            text = chunk.choices[0].delta.content
            yield text
            full_response += text
            
        # In stream mode, OpenAI does not send usage stats by default unless explicitly enabled
        # or we can just ignore it for now.
            
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
