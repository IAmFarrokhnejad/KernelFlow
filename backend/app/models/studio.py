from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from ..database.base import Base


class AssetRecord(Base):
    __tablename__ = "studio_assets"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    original_path = Column(String, nullable=False)
    thumbnail_path = Column(String, nullable=True)
    width = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PresetRecord(Base):
    __tablename__ = "studio_presets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    mode = Column(String, nullable=False, default="editor")
    pipeline_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class BatchRunRecord(Base):
    __tablename__ = "studio_batches"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")
    pipeline_json = Column(Text, nullable=False)
    asset_ids_json = Column(Text, nullable=False)
    output_dir = Column(String, nullable=True)
    export_format = Column(String, nullable=False, default="png")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)


class JobRecord(Base):
    __tablename__ = "studio_jobs"

    id = Column(Integer, primary_key=True, index=True)
    kind = Column(String, nullable=False)
    mode = Column(String, nullable=False, default="editor")
    status = Column(String, nullable=False, default="pending")
    asset_id = Column(Integer, ForeignKey("studio_assets.id"), nullable=False)
    batch_id = Column(Integer, ForeignKey("studio_batches.id"), nullable=True)
    pipeline_json = Column(Text, nullable=False)
    output_path = Column(String, nullable=True)
    output_url = Column(String, nullable=True)
    metrics_json = Column(Text, nullable=True)
    histogram_json = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
