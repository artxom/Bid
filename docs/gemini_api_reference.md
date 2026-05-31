# Google Gen AI SDK (Python) Reference

This document serves as the **Project-Level Reference** for using the Gemini API. 
**ALL FUTURE AGENTS MUST CONSULT THIS DOCUMENT** before writing or modifying any code that interacts with Gemini.

The project uses the new unified **`google-genai`** SDK (v0.3.0+). The legacy `google-generativeai` and `vertexai` libraries are deprecated and MUST NOT be used.

## 1. Installation & Imports

```python
# pip install google-genai
from google import genai
from google.genai import types
```

## 2. Client Initialization

```python
# Gemini Developer API (uses GEMINI_API_KEY environment variable)
client = genai.Client(api_key='YOUR_API_KEY')
```

## 3. Basic Generation (Sync & Async)

### Sync Generation
```python
response = client.models.generate_content(
    model='gemini-3.1-pro-preview',
    contents='Why is the sky blue?'
)
print(response.text)
```

### Async Generation
```python
# Note: Use `client.aio` for async operations!
response = await client.aio.models.generate_content(
    model='gemini-3.1-pro-preview',
    contents='Why is the sky blue?'
)
print(response.text)
```

## 4. Structured Output (JSON) & Configuration

```python
# Note: Pydantic schemas in `response_schema` may throw $ref extra_forbidden errors if they are nested. 
# It is safer to prompt for markdown JSON or pass a plain Dict Schema.

response = client.models.generate_content(
    model='gemini-3.1-pro-preview',
    contents='...',
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.2,
    ),
)
```

## 5. Streaming (Sync & Async)

### Sync Streaming
```python
response_stream = client.models.generate_content_stream(
    model='gemini-3.1-pro-preview',
    contents='Tell me a story.'
)
for chunk in response_stream:
    print(chunk.text, end='')
```

### Async Streaming
```python
# Note: client.aio.models.generate_content_stream IS the async generator.
# Do NOT await the call itself (e.g. NOT `await client.aio...stream()`)
response_stream = client.aio.models.generate_content_stream(
    model='gemini-3.1-pro-preview',
    contents='Tell me a story.'
)
async for chunk in response_stream:
    print(chunk.text, end='')
```

## 6. System Instructions

To use system instructions, use the `system_instruction` parameter within `GenerateContentConfig`.

```python
response = client.models.generate_content(
    model='gemini-3.1-pro-preview',
    contents='User prompt',
    config=types.GenerateContentConfig(
        system_instruction="You are a helpful Bid Architect.",
        temperature=0.2
    )
)
```
