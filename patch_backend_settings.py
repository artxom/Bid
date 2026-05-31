import re

# 1. Update main.py
with open('backend/main.py', 'r') as f:
    content = f.read()

model_old = """class RewriteRequest(BaseModel):
    instruction: str
    current_outline: List[dict]
    active_chapter_id: Optional[str] = None"""
model_new = """class RewriteRequest(BaseModel):
    instruction: str
    current_outline: List[dict]
    active_chapter_id: Optional[str] = None
    system_prompt: Optional[str] = None"""
content = content.replace(model_old, model_new)

call_old = """new_outline = await rewrite_outline_with_gemini(
            user_instruction=request.instruction,
            current_outline=request.current_outline,
            active_chapter_id=request.active_chapter_id
        )"""
call_new = """new_outline = await rewrite_outline_with_gemini(
            user_instruction=request.instruction,
            current_outline=request.current_outline,
            active_chapter_id=request.active_chapter_id,
            system_prompt=request.system_prompt
        )"""
content = content.replace(call_old, call_new)

stream_old = """async for chunk in stream_rewrite_outline_with_gemini(
                user_instruction=request.instruction,
                current_outline=request.current_outline,
                active_chapter_id=request.active_chapter_id
            ):"""
stream_new = """async for chunk in stream_rewrite_outline_with_gemini(
                user_instruction=request.instruction,
                current_outline=request.current_outline,
                active_chapter_id=request.active_chapter_id,
                system_prompt=request.system_prompt
            ):"""
content = content.replace(stream_old, stream_new)

with open('backend/main.py', 'w') as f:
    f.write(content)

# 2. Update services/commander.py
with open('backend/services/commander.py', 'r') as f:
    content = f.read()

sig_old = "async def rewrite_outline_with_gemini(user_instruction: str, current_outline: List[dict], active_chapter_id: str = None) -> List[dict]:"
sig_new = "async def rewrite_outline_with_gemini(user_instruction: str, current_outline: List[dict], active_chapter_id: str = None, system_prompt: str = None) -> List[dict]:"
content = content.replace(sig_old, sig_new)

sig_stream_old = "async def stream_rewrite_outline_with_gemini(user_instruction: str, current_outline: List[dict], active_chapter_id: str = None):"
sig_stream_new = "async def stream_rewrite_outline_with_gemini(user_instruction: str, current_outline: List[dict], active_chapter_id: str = None, system_prompt: str = None):"
content = content.replace(sig_stream_old, sig_stream_new)

# Re-write the prompt logic
old_prompt_logic = """    prompt = f\"\"\"
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
\"\"\""""

new_prompt_logic = """    sys_p = system_prompt if system_prompt else f"You are an expert Bid Architect (Commander).{context_msg}"
    prompt = f\"\"\"
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
\"\"\""""
content = content.replace(old_prompt_logic, new_prompt_logic)

old_stream_prompt = """    prompt = f\"\"\"
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
\"\"\""""

new_stream_prompt = """    sys_p = system_prompt if system_prompt else f"You are an expert Bid Architect (Commander).{context_msg}"
    prompt = f\"\"\"
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
\"\"\""""
content = content.replace(old_stream_prompt, new_stream_prompt)

with open('backend/services/commander.py', 'w') as f:
    f.write(content)

print("Backend patched for settings.")
