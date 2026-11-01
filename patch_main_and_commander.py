import re

# 1. Update main.py
with open("backend/main.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("from google import genai", "from openai import AsyncOpenAI")
content = content.replace("from services.commander import rewrite_outline_with_gemini, stream_rewrite_outline_with_gemini", "from services.commander import rewrite_outline_with_deepseek, stream_rewrite_outline_with_deepseek")

models_endpoint_old = """@app.get("/models")
async def get_models():
    try:
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("No API key found in environment variables.")
        client = genai.Client(api_key=api_key)
        models_list = client.models.list()
        result = []
        for m in models_list:
            # Check if it's a generative model
            if hasattr(m, 'supported_generation_methods') and "generateContent" in getattr(m, 'supported_generation_methods', []):
                result.append({"name": m.name, "display_name": m.display_name})
        # If supported_generation_methods is not easily accessible in the new SDK version, fallback to just returning all or checking prefix
        if not result:
            for m in models_list:
                if "gemini" in m.name.lower():
                    result.append({"name": m.name, "display_name": m.display_name})
                    
        return {"status": "success", "models": result}
    except Exception as e:
        print(f"Failed to fetch models dynamically: {e}")
        # Fallback to standard models if API throws 501 or key missing
        fallback_models = [
            {"name": "gemini-3.1-pro-preview", "display_name": "Gemini 3.1 Pro (Preview)"},
            {"name": "gemini-3.5-flash", "display_name": "Gemini 3.5 Flash"},
            {"name": "gemini-2.5-flash", "display_name": "Gemini 2.5 Flash"},
            {"name": "gemini-1.5-pro", "display_name": "Gemini 1.5 Pro"},
            {"name": "gemini-1.5-flash", "display_name": "Gemini 1.5 Flash"},
        ]
        return {"status": "success", "models": fallback_models}"""

models_endpoint_new = """@app.get("/models")
async def get_models():
    try:
        api_key = os.getenv("DEEPSEEK_API_KEY")
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        if not api_key:
            raise ValueError("No API key found in environment variables.")
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        models_list = await client.models.list()
        result = []
        for m in models_list.data:
            result.append({"name": m.id, "display_name": m.id})
            
        return {"status": "success", "models": result}
    except Exception as e:
        print(f"Failed to fetch models dynamically: {e}")
        fallback_models = [
            {"name": "deepseek-v4-pro", "display_name": "DeepSeek v4 Pro"},
            {"name": "deepseek-v4-flash", "display_name": "DeepSeek v4 Flash"}
        ]
        return {"status": "success", "models": fallback_models}"""
content = content.replace(models_endpoint_old, models_endpoint_new)

content = content.replace('flash_model: Optional[str] = "gemini-3.5-flash"', 'flash_model: Optional[str] = "deepseek-v4-pro"')
content = content.replace('pro_model: Optional[str] = "gemini-3.1-pro"', 'pro_model: Optional[str] = "deepseek-v4-pro"')

dify_prep_old = """        # --- Pre-process context using Gemini Flash Model ---
        detailed_context = section.context
        try:
            gemini_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
            if gemini_key:
                client = genai.Client(api_key=gemini_key)"""
dify_prep_new = """        # --- Pre-process context using DeepSeek Model ---
        detailed_context = section.context
        try:
            deepseek_key = os.getenv("DEEPSEEK_API_KEY")
            base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
            if deepseek_key:
                client = AsyncOpenAI(api_key=deepseek_key, base_url=base_url)"""
content = content.replace(dify_prep_old, dify_prep_new)

flash_call_old = """                flash_start_time = time.time()
                flash_response = client.models.generate_content(
                    model=flash_model or "gemini-2.5-flash",
                    contents=prompt,
                )
                flash_latency = time.time() - flash_start_time
                
                if flash_response.text:
                    detailed_context = flash_response.text
                    
                flash_usage = None
                if hasattr(flash_response, 'usage_metadata') and flash_response.usage_metadata:
                    flash_usage = {
                        "prompt_token_count": getattr(flash_response.usage_metadata, 'prompt_token_count', 0),
                        "candidates_token_count": getattr(flash_response.usage_metadata, 'candidates_token_count', 0),
                        "total_token_count": getattr(flash_response.usage_metadata, 'total_token_count', 0)
                    }"""
flash_call_new = """                flash_start_time = time.time()
                flash_response = await client.chat.completions.create(
                    model=flash_model or "deepseek-v4-pro",
                    messages=[{"role": "user", "content": prompt}]
                )
                flash_latency = time.time() - flash_start_time
                
                if flash_response.choices and flash_response.choices[0].message.content:
                    detailed_context = flash_response.choices[0].message.content
                    
                flash_usage = None
                if flash_response.usage:
                    flash_usage = {
                        "prompt_token_count": getattr(flash_response.usage, 'prompt_tokens', 0),
                        "candidates_token_count": getattr(flash_response.usage, 'completion_tokens', 0),
                        "total_token_count": getattr(flash_response.usage, 'total_tokens', 0)
                    }"""
content = content.replace(flash_call_old, flash_call_new)

content = content.replace("Error generating pre-context with Gemini:", "Error generating pre-context with DeepSeek:")
content = content.replace("rewrite_outline_with_gemini", "rewrite_outline_with_deepseek")
content = content.replace("stream_rewrite_outline_with_gemini", "stream_rewrite_outline_with_deepseek")

with open("backend/main.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Updated backend/main.py")
