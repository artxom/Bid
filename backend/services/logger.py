import asyncio
import traceback
from typing import Any, Dict, Optional
from database import SessionLocal
from models import LLMRequestLog

def log_llm_request_sync(
    scenario: str,
    model_used: str,
    input_payload: Any,
    output_payload: Any,
    latency: float,
    usage_data: Optional[Dict[str, Any]] = None
):
    """
    Synchronous DB write for LLM requests.
    Opens a session, writes the log, and closes it.
    """
    db = SessionLocal()
    try:
        log_entry = LLMRequestLog(
            scenario=scenario,
            model_used=model_used,
            input_payload=input_payload,
            output_payload=output_payload,
            latency=latency,
            usage_data=usage_data
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        print(f"Failed to log LLM request ({scenario}): {e}")
        traceback.print_exc()
    finally:
        db.close()

def log_llm_request_async(
    scenario: str,
    model_used: str,
    input_payload: Any,
    output_payload: Any,
    latency: float,
    usage_data: Optional[Dict[str, Any]] = None
):
    """
    Fire-and-forget asynchronous logger.
    Offloads the DB write to a background thread to prevent blocking main async loops.
    """
    asyncio.create_task(
        asyncio.to_thread(
            log_llm_request_sync,
            scenario,
            model_used,
            input_payload,
            output_payload,
            latency,
            usage_data
        )
    )
