from __future__ import annotations

import base64
import json
import uuid
from pathlib import Path
from typing import Any, Generator

import cv2
import numpy as np
from PIL import Image

from services.metrics import compute_histograms, compute_metrics
from services.operations import OPERATION_LOOKUP, apply_operation, default_target


SUPPORTED_EXPORTS = {"png": ".png", "jpg": ".jpg", "jpeg": ".jpg", "webp": ".webp"}


def _to_gray(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def _normalize_bounds(bounds: dict[str, Any] | None) -> dict[str, float]:
    fallback = {"x": 0.15, "y": 0.15, "width": 0.5, "height": 0.5}
    candidate = fallback if not isinstance(bounds, dict) else bounds
    x = min(max(float(candidate.get("x", fallback["x"])), 0.0), 1.0)
    y = min(max(float(candidate.get("y", fallback["y"])), 0.0), 1.0)
    width = min(max(float(candidate.get("width", fallback["width"])), 0.01), 1.0 - x)
    height = min(max(float(candidate.get("height", fallback["height"])), 0.01), 1.0 - y)
    return {"x": x, "y": y, "width": width, "height": height}


def encode_image(image: np.ndarray, ext: str = ".jpg", quality: int = 90) -> str:
    params: list[int] = []
    if ext in {".jpg", ".jpeg"}:
        params = [cv2.IMWRITE_JPEG_QUALITY, quality]
    elif ext == ".webp":
        params = [cv2.IMWRITE_WEBP_QUALITY, quality]
    ok, buffer = cv2.imencode(ext, image, params)
    if not ok:
        raise ValueError("Failed to encode image")
    return base64.b64encode(buffer).decode("ascii")


def save_image(image: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXPORTS.values():
        raise ValueError(f"Unsupported output format: {suffix}")
    params: list[int] = []
    if suffix == ".jpg":
        params = [cv2.IMWRITE_JPEG_QUALITY, 95]
    elif suffix == ".webp":
        params = [cv2.IMWRITE_WEBP_QUALITY, 95]
    ok = cv2.imwrite(str(path), image, params)
    if not ok:
        raise ValueError(f"Failed to save {path}")


def read_image(path: Path) -> np.ndarray:
    if path.suffix.lower() == ".gif":
        pil_image = Image.open(path)
        if getattr(pil_image, "is_animated", False):
            pil_image.seek(0)
        rgb = np.array(pil_image.convert("RGB"))
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    buffer = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError(f"Failed to read image: {path}")
    if image.ndim == 2:
        return image
    if image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    return image


def build_proxy(image: np.ndarray, *, max_edge: int = 1280) -> np.ndarray:
    h, w = image.shape[:2]
    long_edge = max(h, w)
    if long_edge <= max_edge:
        return image.copy()
    scale = max_edge / float(long_edge)
    size = (max(1, int(round(w * scale))), max(1, int(round(h * scale))))
    return cv2.resize(image, size, interpolation=cv2.INTER_AREA)


def build_thumbnail(image: np.ndarray, *, max_edge: int = 420) -> np.ndarray:
    return build_proxy(image, max_edge=max_edge)


def resolve_bounds(image_shape: tuple[int, ...], target: dict[str, Any]) -> tuple[int, int, int, int]:
    h, w = image_shape[:2]
    bounds = _normalize_bounds(target.get("bounds"))
    x = min(w - 1, max(0, int(round(bounds["x"] * w))))
    y = min(h - 1, max(0, int(round(bounds["y"] * h))))
    width = min(max(1, int(round(bounds["width"] * w))), w - x)
    height = min(max(1, int(round(bounds["height"] * h))), h - y)
    return x, y, width, height


def _mask_from_generator(image: np.ndarray, generator_name: str, params: dict[str, Any]) -> np.ndarray:
    gray = cv2.normalize(_to_gray(image).astype(np.float32), None, 0.0, 1.0, cv2.NORM_MINMAX)
    if generator_name == "luminance":
        min_value = float(params.get("min", 0.2))
        max_value = float(params.get("max", 1.0))
        return np.where((gray >= min_value) & (gray <= max_value), 1.0, 0.0).astype(np.float32)
    if generator_name == "threshold":
        threshold = float(params.get("threshold", 160)) / 255.0
        return np.where(gray >= threshold, 1.0, 0.0).astype(np.float32)
    if generator_name == "edge":
        low = max(0, min(255, int(params.get("low", 60))))
        high = max(low + 1, min(255, int(params.get("high", 180))))
        edges = cv2.Canny((gray * 255).astype(np.uint8), low, high)
        return (edges > 0).astype(np.float32)
    return np.ones_like(gray, dtype=np.float32)


def build_target_mask(image: np.ndarray, target: dict[str, Any] | None) -> np.ndarray:
    config = default_target() if target is None else {**default_target(), **target}
    h, w = image.shape[:2]
    mask = np.ones((h, w), dtype=np.float32)
    scope = str(config.get("scope", "global"))
    if scope in {"rectangle", "ellipse", "crop"}:
        x, y, width, height = resolve_bounds(image.shape, config)
        mask = np.zeros((h, w), dtype=np.float32)
        if scope == "ellipse":
            center = (x + width // 2, y + height // 2)
            axes = (max(1, width // 2), max(1, height // 2))
            cv2.ellipse(mask, center, axes, 0, 0, 360, 1.0, -1)
        else:
            mask[y : y + height, x : x + width] = 1.0

    generator_name = str(config.get("maskGenerator", "none"))
    if generator_name != "none":
        mask *= _mask_from_generator(image, generator_name, config.get("maskParams", {}))

    feather = max(0.0, float(config.get("featherPx", 0)))
    if feather > 0:
        blur = max(1, int(round(feather)))
        kernel_size = blur * 2 + 1
        mask = cv2.GaussianBlur(mask, (kernel_size, kernel_size), feather)
        mask = np.clip(mask, 0.0, 1.0)

    if bool(config.get("invertMask", False)):
        mask = 1.0 - mask

    return mask.astype(np.float32)


def apply_step(image: np.ndarray, step: dict[str, Any]) -> np.ndarray:
    operation_id = str(step.get("operationId"))
    params = step.get("params", {}) or {}
    target = step.get("target") or default_target()
    if operation_id not in OPERATION_LOOKUP:
        raise ValueError(f"Unknown operation: {operation_id}")

    if str(target.get("scope", "global")) == "crop":
        x, y, width, height = resolve_bounds(image.shape, target)
        return apply_operation(image[y : y + height, x : x + width], operation_id, params)

    processed = apply_operation(image, operation_id, params)
    if not OPERATION_LOOKUP[operation_id].supports_mask or processed.shape[:2] != image.shape[:2]:
        return processed

    mask = build_target_mask(image, target)
    if image.ndim == 2:
        blended = processed.astype(np.float32) * mask + image.astype(np.float32) * (1.0 - mask)
        return np.clip(blended, 0, 255).astype(np.uint8)

    blended = processed.astype(np.float32) * mask[..., None] + image.astype(np.float32) * (1.0 - mask[..., None])
    return np.clip(blended, 0, 255).astype(np.uint8)


def normalize_pipeline(pipeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for raw_step in pipeline:
        if not raw_step.get("enabled", True):
            continue
        normalized.append(
            {
                "id": str(raw_step.get("id") or uuid.uuid4()),
                "operationId": str(raw_step.get("operationId")),
                "enabled": True,
                "previewEnabled": bool(raw_step.get("previewEnabled", True)),
                "params": raw_step.get("params", {}) or {},
                "target": raw_step.get("target") or default_target(),
            }
        )
    return normalized


def run_pipeline(source: np.ndarray, pipeline: list[dict[str, Any]], *, include_steps: bool = False) -> tuple[np.ndarray, list[dict[str, Any]]]:
    current = source.copy()
    step_results: list[dict[str, Any]] = []
    for index, step in enumerate(normalize_pipeline(pipeline)):
        current = apply_step(current, step)
        if include_steps:
            step_results.append(
                {
                    "index": index,
                    "stepId": step["id"],
                    "operationId": step["operationId"],
                    "label": OPERATION_LOOKUP[step["operationId"]].label,
                    "image": current.copy(),
                }
            )
    return current, step_results


def preview_stream(source: np.ndarray, pipeline: list[dict[str, Any]], *, mode: str) -> Generator[dict[str, Any], None, dict[str, Any]]:
    steps = normalize_pipeline(pipeline)
    if not steps:
        return {"image": source, "metrics": compute_metrics(source, source), "histogram": compute_histograms(source, source)}

    if mode == "lab":
        base = source.copy()
        if len(steps) > 1:
            for index, step in enumerate(steps[:-1]):
                base = apply_step(base, step)
                yield {
                    "type": "step",
                    "progress": round((index + 1) / max(1, len(steps)), 3),
                    "label": OPERATION_LOOKUP[step["operationId"]].label,
                    "image": encode_image(base),
                }

        final_step = steps[-1]
        final = apply_step(base, final_step)
        if final.shape[:2] == base.shape[:2]:
            h = final.shape[0]
            chunk = max(1, h // 30)
            temp = base.copy()
            for y in range(0, h, chunk):
                temp[y : y + chunk] = final[y : y + chunk]
                yield {
                    "type": "scan",
                    "progress": round(min(1.0, (y + chunk) / h), 3),
                    "label": OPERATION_LOOKUP[final_step["operationId"]].label,
                    "image": encode_image(temp),
                }
        result = final
    else:
        result = source.copy()
        for index, step in enumerate(steps):
            result = apply_step(result, step)
            if step.get("previewEnabled", True):
                yield {
                    "type": "step",
                    "progress": round((index + 1) / len(steps), 3),
                    "label": OPERATION_LOOKUP[step["operationId"]].label,
                    "image": encode_image(result),
                }

    return {"image": result, "metrics": compute_metrics(source, result), "histogram": compute_histograms(source, result)}


def parse_json_text(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback
