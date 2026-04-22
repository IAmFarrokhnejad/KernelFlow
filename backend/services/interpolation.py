from __future__ import annotations

import cv2
import numpy as np
from scipy import ndimage


def cubic_kernel(x: np.ndarray, a: float = -0.5) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    ax = np.abs(x)
    ax2 = ax * ax
    ax3 = ax2 * ax
    out = np.zeros_like(x)

    mask1 = ax <= 1
    out[mask1] = ((a + 2) * ax3[mask1] - (a + 3) * ax2[mask1] + 1)

    mask2 = (ax > 1) & (ax < 2)
    out[mask2] = (
        a * ax3[mask2]
        - 5 * a * ax2[mask2]
        + 8 * a * ax[mask2]
        - 4 * a
    )
    return out


def sinc(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    out = np.ones_like(x)
    nz = x != 0
    out[nz] = np.sin(np.pi * x[nz]) / (np.pi * x[nz])
    return out


def lanczos_kernel(x: np.ndarray, a: int = 3) -> np.ndarray:
    ax = np.abs(x)
    return np.where(ax < a, sinc(x) * sinc(x / a), 0.0)


def precompute_contributions(
    in_length: int,
    out_length: int,
    scale: float,
    kernel,
    support: int,
) -> tuple[np.ndarray, np.ndarray]:
    xs = (np.arange(out_length) + 0.5) / scale - 0.5
    left = np.floor(xs).astype(int) - support + 1
    indices = left[:, None] + np.arange(2 * support)[None, :]
    weights = kernel(xs[:, None] - indices)
    weight_sum = weights.sum(axis=1, keepdims=True)
    weights = np.divide(weights, weight_sum, out=np.zeros_like(weights), where=weight_sum != 0)
    indices = np.clip(indices, 0, in_length - 1)
    return indices.astype(np.int32), weights.astype(np.float32)


def resize_separable_custom(
    image: np.ndarray,
    scale_x: float,
    scale_y: float,
    *,
    method: str,
    lanczos_a: int = 3,
) -> np.ndarray:
    was_gray = image.ndim == 2
    working = image[..., None] if was_gray else image
    working = working.astype(np.float32)
    in_h, in_w, channels = working.shape
    out_h = max(1, int(round(in_h * scale_y)))
    out_w = max(1, int(round(in_w * scale_x)))

    if method == "bicubic":
        kernel = lambda x: cubic_kernel(x, a=-0.5)
        support = 2
    elif method == "lanczos":
        kernel = lambda x: lanczos_kernel(x, a=lanczos_a)
        support = lanczos_a
    else:
        raise ValueError(f"Unsupported resize method: {method}")

    x_idx, x_weights = precompute_contributions(in_w, out_w, scale_x, kernel, support)
    y_idx, y_weights = precompute_contributions(in_h, out_h, scale_y, kernel, support)

    tmp = np.empty((in_h, out_w, channels), dtype=np.float32)
    for idx in range(out_w):
        gathered = working[:, x_idx[idx, :], :]
        tmp[:, idx, :] = np.tensordot(gathered, x_weights[idx], axes=([1], [0]))

    out = np.empty((out_h, out_w, channels), dtype=np.float32)
    for idx in range(out_h):
        gathered = tmp[y_idx[idx, :], :, :]
        out[idx, :, :] = np.tensordot(y_weights[idx], gathered, axes=([0], [0]))

    out = np.clip(out, 0, 255).astype(np.uint8)
    if was_gray:
        return out[:, :, 0]
    return out


def upscale_image(image: np.ndarray, *, method: str, scale: float) -> np.ndarray:
    h, w = image.shape[:2]
    out_size = (max(1, int(round(w * scale))), max(1, int(round(h * scale))))

    if method == "nearest":
        return cv2.resize(image, out_size, interpolation=cv2.INTER_NEAREST)
    if method == "bilinear":
        return cv2.resize(image, out_size, interpolation=cv2.INTER_LINEAR)
    if method == "bicubic_lib":
        return cv2.resize(image, out_size, interpolation=cv2.INTER_CUBIC)
    if method == "spline":
        zoom = (scale, scale, 1) if image.ndim == 3 else (scale, scale)
        out = ndimage.zoom(image.astype(np.float32), zoom, order=3, prefilter=True)
        return np.clip(out, 0, 255).astype(np.uint8)
    if method == "bicubic_custom":
        return resize_separable_custom(image, scale, scale, method="bicubic")
    if method == "lanczos_custom":
        return resize_separable_custom(image, scale, scale, method="lanczos")

    raise ValueError(f"Unsupported upscale method: {method}")
