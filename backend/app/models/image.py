from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from ..database.base import Base

class ImageRecord(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True, index=True)
    original_filename = Column(String, index=True)
    original_path = Column(String)
    filter_applied = Column(String, nullable=True)
    params = Column(Text, nullable=True)           # JSON string of kernel/boost etc.
    result_path = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)