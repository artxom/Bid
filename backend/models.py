from sqlalchemy import Column, String, JSON, DateTime, Float
from database import Base
import datetime
import uuid

class Project(Base):
    __tablename__ = "projects"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    filename = Column(String, index=True)
    template_path = Column(String, nullable=True) # Stores the path to the uploaded document
    outline = Column(JSON) # Stores the list of OutlineItem dicts
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class LLMRequestLog(Base):
    __tablename__ = "llm_request_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    scenario = Column(String, index=True) # e.g. dify_workflow, dify_pre_process, outline_rewrite
    model_used = Column(String)
    input_payload = Column(JSON)
    output_payload = Column(JSON)
    usage_data = Column(JSON, nullable=True)
    latency = Column(Float, nullable=True)
