from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.crud.studio import (
    create_asset,
    create_batch,
    create_job,
    create_or_update_preset,
    finish_batch,
    get_asset,
    get_job,
    list_assets,
    list_batches,
    list_presets,
    list_recent_jobs,
    update_job_status,
)
from app.database.base import SessionLocal, create_tables, get_db
from services.metrics import save_metrics_plot, save_metrics_to_csv
from services.operations import DEFAULT_PRESETS, list_operation_payloads
from services.pipeline import (
    build_proxy,
    build_thumbnail,
    encode_image,
    parse_json_text,
    preview_stream,
    read_image,
    run_pipeline,
    save_image,
)


class PreviewRequest(BaseModel):
    asset_id: int
    pipeline: list[dict[str, Any]] = Field(default_factory=list)
    mode: str = "editor"
    max_preview_edge: int = 1280


class ExportRequest(BaseModel):
    asset_id: int
    pipeline: list[dict[str, Any]] = Field(default_factory=list)
    format: str = "png"
    name: str | None = None


class BatchRequest(BaseModel):
    asset_ids: list[int] = Field(default_factory=list)
    pipeline: list[dict[str, Any]] = Field(default_factory=list)
    format: str = "png"
    name: str | None = None


class PresetRequest(BaseModel):
    id: int | None = None
    name: str
    description: str = ""
    mode: str = "editor"
    pipeline: list[dict[str, Any]] = Field(default_factory=list)


app = FastAPI(title="KernelFlow vNext")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

STORAGE_ROOT = Path("storage")
ASSET_DIR = STORAGE_ROOT / "assets"
THUMB_DIR = STORAGE_ROOT / "thumbs"
PREVIEW_DIR = STORAGE_ROOT / "previews"
EXPORT_DIR = STORAGE_ROOT / "exports"
for directory in (STORAGE_ROOT, ASSET_DIR, THUMB_DIR, PREVIEW_DIR, EXPORT_DIR):
    directory.mkdir(parents=True, exist_ok=True)

app.mount("/storage", StaticFiles(directory=STORAGE_ROOT), name="storage")


def _slugify(name: str) -> str:
    stem = Path(name).stem or "image"
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", stem).strip("-")
    return safe or "image"


def _extension(filename: str, fallback: str = ".png") -> str:
    suffix = Path(filename).suffix.lower()
    return suffix if suffix else fallback


def _asset_url(path: str | Path | None) -> str | None:
    if path is None:
        return None
    rel = Path(path).relative_to(STORAGE_ROOT)
    return f"/storage/{rel.as_posix()}"


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _serialize_asset(record) -> dict[str, Any]:
    return {
        "id": record.id,
        "filename": record.filename,
        "mimeType": record.mime_type,
        "width": record.width,
        "height": record.height,
        "url": _asset_url(record.original_path),
        "thumbnailUrl": _asset_url(record.thumbnail_path),
        "createdAt": _iso(record.created_at),
    }


def _serialize_preset(record) -> dict[str, Any]:
    return {
        "id": record.id,
        "name": record.name,
        "description": record.description or "",
        "mode": record.mode,
        "pipeline": parse_json_text(record.pipeline_json, []),
        "createdAt": _iso(record.created_at),
        "updatedAt": _iso(record.updated_at),
    }


def _serialize_job(record) -> dict[str, Any]:
    return {
        "id": record.id,
        "kind": record.kind,
        "mode": record.mode,
        "status": record.status,
        "assetId": record.asset_id,
        "batchId": record.batch_id,
        "pipeline": parse_json_text(record.pipeline_json, []),
        "outputUrl": record.output_url,
        "metrics": parse_json_text(record.metrics_json, None),
        "histogram": parse_json_text(record.histogram_json, None),
        "error": record.error,
        "createdAt": _iso(record.created_at),
        "updatedAt": _iso(record.updated_at),
    }


def _serialize_batch(record) -> dict[str, Any]:
    return {
        "id": record.id,
        "name": record.name,
        "status": record.status,
        "assetIds": parse_json_text(record.asset_ids_json, []),
        "pipeline": parse_json_text(record.pipeline_json, []),
        "outputDir": _asset_url(record.output_dir) if record.output_dir else None,
        "format": record.export_format,
        "createdAt": _iso(record.created_at),
        "completedAt": _iso(record.completed_at),
    }


def _ensure_default_presets() -> None:
    db = SessionLocal()
    try:
        existing = {record.name for record in list_presets(db)}
        for preset in DEFAULT_PRESETS:
            if preset["name"] not in existing:
                create_or_update_preset(
                    db,
                    name=preset["name"],
                    description=preset["description"],
                    mode=preset["mode"],
                    pipeline=preset["pipeline"],
                )
    finally:
        db.close()


@app.on_event("startup")
def startup_event():
    create_tables()
    _ensure_default_presets()


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/assets")
def get_assets(db: Session = Depends(get_db)):
    return {"items": [_serialize_asset(record) for record in list_assets(db)]}


@app.post("/api/assets")
async def create_assets(files: list[UploadFile] = File(...), db: Session = Depends(get_db)):
    items: list[dict[str, Any]] = []
    for upload in files:
        raw_bytes = await upload.read()
        if not raw_bytes:
            continue
        suffix = _extension(upload.filename)
        file_name = f"{_slugify(upload.filename)}-{uuid.uuid4().hex[:8]}{suffix}"
        asset_path = ASSET_DIR / file_name
        asset_path.write_bytes(raw_bytes)

        try:
            image = read_image(asset_path)
        except Exception as exc:
            asset_path.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail=f"Unsupported image: {upload.filename}") from exc

        thumb_path = THUMB_DIR / f"{asset_path.stem}.jpg"
        save_image(build_thumbnail(image), thumb_path)
        record = create_asset(
            db,
            filename=upload.filename,
            mime_type=upload.content_type or "application/octet-stream",
            original_path=str(asset_path),
            thumbnail_path=str(thumb_path),
            width=int(image.shape[1]),
            height=int(image.shape[0]),
        )
        items.append(_serialize_asset(record))

    return {"items": items}


@app.get("/api/operations")
def get_operations():
    return {"operations": list_operation_payloads()}


@app.get("/api/presets")
def get_presets(db: Session = Depends(get_db)):
    return {"items": [_serialize_preset(record) for record in list_presets(db)]}


@app.post("/api/presets")
def save_preset(payload: PresetRequest, db: Session = Depends(get_db)):
    record = create_or_update_preset(
        db,
        preset_id=payload.id,
        name=payload.name,
        description=payload.description,
        mode=payload.mode,
        pipeline=payload.pipeline,
    )
    return _serialize_preset(record)


@app.post("/api/previews")
def create_preview_job(payload: PreviewRequest, db: Session = Depends(get_db)):
    asset = get_asset(db, payload.asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    record = create_job(db, kind="preview", asset_id=payload.asset_id, pipeline=payload.pipeline, mode=payload.mode)
    return _serialize_job(record)


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: int, db: Session = Depends(get_db)):
    job = get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    update_job_status(db, job, status="canceled")
    return _serialize_job(job)


@app.get("/api/jobs/{job_id}/stream")
def stream_job(job_id: int, db: Session = Depends(get_db)):
    job = get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    asset = get_asset(db, job.asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")

    pipeline = parse_json_text(job.pipeline_json, [])

    def sse(event: str, data: dict[str, Any]) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=True)}\n\n"

    def generator():
        try:
            update_job_status(db, job, status="running")
            source = read_image(Path(asset.original_path))
            proxy = build_proxy(source, max_edge=1280)
            stream = preview_stream(proxy, pipeline, mode=job.mode)

            while True:
                try:
                    frame = next(stream)
                except StopIteration as stop:
                    result = stop.value
                    break
                yield sse("progress", frame)

            output_path = PREVIEW_DIR / f"job-{job.id}.jpg"
            save_image(result["image"], output_path)
            update_job_status(
                db,
                job,
                status="completed",
                output_path=str(output_path),
                output_url=_asset_url(output_path),
                metrics=result["metrics"],
                histogram=result["histogram"],
            )
            yield sse(
                "complete",
                {
                    "job": _serialize_job(job),
                    "previewUrl": _asset_url(output_path),
                    "metrics": result["metrics"],
                    "histogram": result["histogram"],
                    "inlineImage": f"data:image/jpeg;base64,{encode_image(result['image'])}",
                },
            )
        except Exception as exc:
            update_job_status(db, job, status="failed", error=str(exc))
            yield sse("error", {"message": str(exc), "job": _serialize_job(job)})

    return StreamingResponse(generator(), media_type="text/event-stream")


@app.post("/api/exports")
def export_asset(payload: ExportRequest, db: Session = Depends(get_db)):
    asset = get_asset(db, payload.asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")

    export_format = payload.format.lower()
    suffix = {"png": ".png", "jpg": ".jpg", "jpeg": ".jpg", "webp": ".webp"}.get(export_format)
    if suffix is None:
        raise HTTPException(status_code=400, detail="Unsupported export format")

    job = create_job(db, kind="export", asset_id=payload.asset_id, pipeline=payload.pipeline, mode="editor")
    update_job_status(db, job, status="running")

    source = read_image(Path(asset.original_path))
    result, _ = run_pipeline(source, payload.pipeline)
    output_name = f"{_slugify(payload.name or asset.filename)}-{job.id}{suffix}"
    output_path = EXPORT_DIR / output_name
    save_image(result, output_path)

    metrics = parse_json_text(job.metrics_json, None) or {}
    metrics = metrics or save_export_metrics(asset.filename, payload.pipeline, source, result)
    histogram = parse_json_text(job.histogram_json, None)
    if histogram is None:
        from services.metrics import compute_histograms, compute_metrics

        metrics = compute_metrics(source, result)
        histogram = compute_histograms(source, result)

    update_job_status(
        db,
        job,
        status="completed",
        output_path=str(output_path),
        output_url=_asset_url(output_path),
        metrics=metrics,
        histogram=histogram,
    )
    return {"job": _serialize_job(job), "asset": _serialize_asset(asset)}


def save_export_metrics(asset_name: str, pipeline: list[dict[str, Any]], source, result) -> dict[str, Any]:
    from services.metrics import compute_metrics

    metrics = compute_metrics(source, result)
    filter_name = pipeline[-1]["operationId"] if pipeline else "pipeline"
    save_metrics_to_csv(asset_name, filter_name, {"pipelineLength": len(pipeline)}, metrics)
    save_metrics_plot(source, result, asset_name, filter_name, metrics)
    return metrics


@app.post("/api/batches")
def create_batch_run(payload: BatchRequest, db: Session = Depends(get_db)):
    if not payload.asset_ids:
        raise HTTPException(status_code=400, detail="No assets selected")

    export_format = payload.format.lower()
    suffix = {"png": ".png", "jpg": ".jpg", "jpeg": ".jpg", "webp": ".webp"}.get(export_format)
    if suffix is None:
        raise HTTPException(status_code=400, detail="Unsupported export format")

    batch_name = payload.name or f"batch-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
    batch_dir = EXPORT_DIR / f"{_slugify(batch_name)}-{uuid.uuid4().hex[:6]}"
    batch_dir.mkdir(parents=True, exist_ok=True)
    batch = create_batch(
        db,
        name=batch_name,
        asset_ids=payload.asset_ids,
        pipeline=payload.pipeline,
        output_dir=str(batch_dir),
        export_format=export_format,
    )

    items: list[dict[str, Any]] = []
    failures = 0
    for asset_id in payload.asset_ids:
        asset = get_asset(db, asset_id)
        if asset is None:
            failures += 1
            continue
        job = create_job(db, kind="batch_export", asset_id=asset.id, batch_id=batch.id, pipeline=payload.pipeline, mode="editor")
        update_job_status(db, job, status="running")
        try:
            source = read_image(Path(asset.original_path))
            result, _ = run_pipeline(source, payload.pipeline)
            output_path = batch_dir / f"{_slugify(asset.filename)}-{job.id}{suffix}"
            save_image(result, output_path)
            metrics = save_export_metrics(asset.filename, payload.pipeline, source, result)
            from services.metrics import compute_histograms

            histogram = compute_histograms(source, result)
            update_job_status(
                db,
                job,
                status="completed",
                output_path=str(output_path),
                output_url=_asset_url(output_path),
                metrics=metrics,
                histogram=histogram,
            )
            items.append({"asset": _serialize_asset(asset), "job": _serialize_job(job)})
        except Exception as exc:
            failures += 1
            update_job_status(db, job, status="failed", error=str(exc))
            items.append({"asset": _serialize_asset(asset), "job": _serialize_job(job)})

    finish_batch(db, batch, status="partial_failed" if failures else "completed")
    return {"batch": _serialize_batch(batch), "items": items}


@app.get("/api/history")
def get_history(db: Session = Depends(get_db)):
    return {
        "assets": [_serialize_asset(record) for record in list_assets(db)[:12]],
        "jobs": [_serialize_job(record) for record in list_recent_jobs(db)],
        "batches": [_serialize_batch(record) for record in list_batches(db)],
        "presets": [_serialize_preset(record) for record in list_presets(db)],
    }
