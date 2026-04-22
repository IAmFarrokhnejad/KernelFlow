from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.studio import AssetRecord, BatchRunRecord, JobRecord, PresetRecord


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True)


def create_asset(
    db: Session,
    *,
    filename: str,
    mime_type: str,
    original_path: str,
    thumbnail_path: str | None,
    width: int,
    height: int,
) -> AssetRecord:
    record = AssetRecord(
        filename=filename,
        mime_type=mime_type,
        original_path=original_path,
        thumbnail_path=thumbnail_path,
        width=width,
        height=height,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def list_assets(db: Session) -> list[AssetRecord]:
    return db.query(AssetRecord).order_by(AssetRecord.created_at.desc()).all()


def get_asset(db: Session, asset_id: int) -> AssetRecord | None:
    return db.query(AssetRecord).filter(AssetRecord.id == asset_id).first()


def create_job(
    db: Session,
    *,
    kind: str,
    asset_id: int,
    pipeline: list[dict[str, Any]],
    mode: str = "editor",
    batch_id: int | None = None,
) -> JobRecord:
    record = JobRecord(
        kind=kind,
        asset_id=asset_id,
        batch_id=batch_id,
        mode=mode,
        pipeline_json=_json_dump(pipeline),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_job(db: Session, job_id: int) -> JobRecord | None:
    return db.query(JobRecord).filter(JobRecord.id == job_id).first()


def update_job_status(
    db: Session,
    job: JobRecord,
    *,
    status: str,
    error: str | None = None,
    output_path: str | None = None,
    output_url: str | None = None,
    metrics: dict[str, Any] | None = None,
    histogram: dict[str, Any] | None = None,
) -> JobRecord:
    job.status = status
    job.error = error
    job.output_path = output_path
    job.output_url = output_url
    if metrics is not None:
        job.metrics_json = _json_dump(metrics)
    if histogram is not None:
        job.histogram_json = _json_dump(histogram)
    job.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job


def create_or_update_preset(
    db: Session,
    *,
    name: str,
    description: str,
    mode: str,
    pipeline: list[dict[str, Any]],
    preset_id: int | None = None,
) -> PresetRecord:
    record: PresetRecord | None = None
    if preset_id is not None:
        record = db.query(PresetRecord).filter(PresetRecord.id == preset_id).first()
    if record is None:
        record = db.query(PresetRecord).filter(PresetRecord.name == name).first()

    if record is None:
        record = PresetRecord(
            name=name,
            description=description,
            mode=mode,
            pipeline_json=_json_dump(pipeline),
        )
        db.add(record)
    else:
        record.name = name
        record.description = description
        record.mode = mode
        record.pipeline_json = _json_dump(pipeline)
        record.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(record)
    return record


def list_presets(db: Session) -> list[PresetRecord]:
    return db.query(PresetRecord).order_by(PresetRecord.name.asc()).all()


def create_batch(
    db: Session,
    *,
    name: str,
    asset_ids: list[int],
    pipeline: list[dict[str, Any]],
    output_dir: str,
    export_format: str,
) -> BatchRunRecord:
    record = BatchRunRecord(
        name=name,
        asset_ids_json=_json_dump(asset_ids),
        pipeline_json=_json_dump(pipeline),
        output_dir=output_dir,
        export_format=export_format,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def finish_batch(db: Session, batch: BatchRunRecord, *, status: str) -> BatchRunRecord:
    batch.status = status
    batch.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(batch)
    return batch


def list_batches(db: Session) -> list[BatchRunRecord]:
    return db.query(BatchRunRecord).order_by(BatchRunRecord.created_at.desc()).all()


def list_recent_jobs(db: Session, *, limit: int = 40) -> list[JobRecord]:
    return db.query(JobRecord).order_by(JobRecord.created_at.desc()).limit(limit).all()
