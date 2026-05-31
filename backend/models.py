from sqlalchemy import Column, String, JSON, DateTime
from database import Base
import datetime
import uuid

class Project(Base):
    __tablename__ = "projects"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    filename = Column(String, index=True)
    outline = Column(JSON) # Stores the list of OutlineItem dicts
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
