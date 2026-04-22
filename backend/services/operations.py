from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import cv2
import numpy as np
from skimage import img_as_float
from skimage.restoration import richardson_lucy, wiener

from services.interpolation import upscale_image


ImageOp = Callable[[np.ndarray, dict[str, Any]], np.ndarray]


@dataclass(frozen=True)
class OperationDefinition:
    id: str
    label: str
    category: str
    supports_mask: bool
    supports_preview: bool
    params_schema: list[dict[str, Any]]


def _odd(value: Any, default: int = 3, minimum: int = 1) -> int:
    try:
        candidate = int(value)
    except (TypeError, ValueError):
        candidate = default
    candidate = max(minimum, candidate)
    return candidate if candidate % 2 == 1 else candidate + 1


def _to_gray(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def _gray_to_color(gray: np.ndarray, reference: np.ndarray) -> np.ndarray:
    if reference.ndim == 2:
        return gray
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def _auto_contrast(gray: np.ndarray) -> np.ndarray:
    return cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)


def _weighted_kernel(size: int = 3) -> np.ndarray:
    if size <= 3:
        return np.array([[1, 2, 1], [2, 4, 2], [1, 2, 1]], dtype=np.float32)
    base = cv2.getGaussianKernel(size, 0)
    return base @ base.T


def _apply_gaussian(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    ksize = _odd(params.get("ksize", 5), default=5)
    sigma = float(params.get("sigma", 0.0))
    return cv2.GaussianBlur(image, (ksize, ksize), sigma)


def _apply_median(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    return cv2.medianBlur(image, _odd(params.get("ksize", 5), default=5))


def _apply_bilateral(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    diameter = max(3, int(params.get("diameter", 9)))
    sigma_color = float(params.get("sigmaColor", 75))
    sigma_space = float(params.get("sigmaSpace", 75))
    return cv2.bilateralFilter(image, diameter, sigma_color, sigma_space)


def _apply_nonlocal(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    h = float(params.get("strength", 10))
    template_window = _odd(params.get("templateWindowSize", 7), default=7, minimum=3)
    search_window = _odd(params.get("searchWindowSize", 21), default=21, minimum=3)
    if image.ndim == 2:
        return cv2.fastNlMeansDenoising(image, None, h=h, templateWindowSize=template_window, searchWindowSize=search_window)
    return cv2.fastNlMeansDenoisingColored(
        image,
        None,
        h=h,
        hColor=float(params.get("colorStrength", h)),
        templateWindowSize=template_window,
        searchWindowSize=search_window,
    )


def _apply_guided(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    radius = max(1, int(params.get("radius", 8)))
    epsilon = float(params.get("epsilon", 0.01))
    try:
        guide = _to_gray(image)
        return cv2.ximgproc.guidedFilter(guide, image, radius, epsilon)
    except Exception:
        return cv2.bilateralFilter(image, radius * 2 + 1, 75, 75)


def _apply_box(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    size = _odd(params.get("ksize", 3), default=3)
    return cv2.blur(image, (size, size))


def _apply_weighted_average(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    size = _odd(params.get("ksize", 3), default=3)
    kernel = _weighted_kernel(size)
    kernel = kernel / np.sum(kernel)
    return cv2.filter2D(image, -1, kernel)


def _apply_unsharp(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    sigma = float(params.get("sigma", 1.2))
    amount = float(params.get("amount", 1.2))
    blur = cv2.GaussianBlur(image, (0, 0), sigma)
    return cv2.addWeighted(image, 1.0 + amount, blur, -amount, 0)


def _apply_highboost(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    sigma = float(params.get("sigma", 1.2))
    boost = float(params.get("boost", 1.8))
    blur = cv2.GaussianBlur(image, (0, 0), sigma)
    return cv2.addWeighted(image, boost, blur, 1.0 - boost, 0)


def _laplacian_kernel(connectivity: int) -> np.ndarray:
    if connectivity == 8:
        return np.array([[1, 1, 1], [1, -8, 1], [1, 1, 1]], dtype=np.float32)
    return np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)


def _apply_laplacian(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    connectivity = 8 if int(params.get("connectivity", 4)) == 8 else 4
    sharpen = bool(params.get("sharpen", True))
    gray = _to_gray(image).astype(np.float32)
    response = cv2.filter2D(gray, -1, _laplacian_kernel(connectivity))
    if sharpen:
        out = np.clip(gray - response, 0, 255).astype(np.uint8)
    else:
        out = cv2.convertScaleAbs(response)
    return _gray_to_color(out, image)


def _apply_log(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    gray = _to_gray(image)
    ksize = _odd(params.get("ksize", 5), default=5)
    sigma = float(params.get("sigma", 1.0))
    response = cv2.Laplacian(cv2.GaussianBlur(gray, (ksize, ksize), sigma), cv2.CV_64F)
    return _gray_to_color(cv2.convertScaleAbs(response), image)


def _apply_wiener(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    psf_size = _odd(params.get("psfSize", 5), default=5)
    balance = float(params.get("balance", 0.01))
    psf = np.ones((psf_size, psf_size), dtype=np.float32) / float(psf_size * psf_size)
    if image.ndim == 2:
        restored = wiener(img_as_float(image), psf, balance)
        return np.clip(restored * 255, 0, 255).astype(np.uint8)

    channels = []
    for channel in cv2.split(image):
        restored = wiener(img_as_float(channel), psf, balance)
        channels.append(np.clip(restored * 255, 0, 255).astype(np.uint8))
    return cv2.merge(channels)


def _apply_richardson(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    psf_size = _odd(params.get("psfSize", 5), default=5)
    sigma = float(params.get("sigma", 1.5))
    iterations = max(1, int(params.get("iterations", 10)))
    psf = cv2.getGaussianKernel(psf_size, sigma)
    psf = psf @ psf.T
    if image.ndim == 2:
        restored = richardson_lucy(img_as_float(image), psf, num_iter=iterations)
        return np.clip(restored * 255, 0, 255).astype(np.uint8)

    channels = []
    for channel in cv2.split(image):
        restored = richardson_lucy(img_as_float(channel), psf, num_iter=iterations)
        channels.append(np.clip(restored * 255, 0, 255).astype(np.uint8))
    return cv2.merge(channels)


def _gradient_components(gray: np.ndarray, op: str) -> tuple[np.ndarray, np.ndarray]:
    if op == "prewitt":
        kernel_x = np.array([[-1, 0, 1], [-1, 0, 1], [-1, 0, 1]], dtype=np.float32)
        kernel_y = np.array([[-1, -1, -1], [0, 0, 0], [1, 1, 1]], dtype=np.float32)
        gx = cv2.filter2D(gray.astype(np.float32), -1, kernel_x)
        gy = cv2.filter2D(gray.astype(np.float32), -1, kernel_y)
        return gx, gy
    return (
        cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3),
        cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3),
    )


def _apply_sobel(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    gray = _to_gray(image)
    gx, gy = _gradient_components(gray, "sobel")
    return _gray_to_color(cv2.convertScaleAbs(cv2.magnitude(gx, gy)), image)


def _apply_prewitt(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    gray = _to_gray(image)
    gx, gy = _gradient_components(gray, "prewitt")
    return _gray_to_color(cv2.convertScaleAbs(cv2.magnitude(gx, gy)), image)


def _apply_gradient(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    gray = _to_gray(image)
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=1)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=1)
    return _gray_to_color(cv2.convertScaleAbs(cv2.magnitude(gx, gy)), image)


def _apply_threshold(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    gray = _to_gray(image)
    threshold = int(params.get("threshold", 180))
    _, out = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    return _gray_to_color(out, image)


def _apply_adaptive_threshold(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    gray = _auto_contrast(_to_gray(image))
    block_size = _odd(params.get("blockSize", 31), default=31, minimum=3)
    c_value = float(params.get("c", 12))
    out = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block_size, c_value)
    return _gray_to_color(out, image)


def _apply_morphology(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    operation = str(params.get("operation", "open"))
    kernel_size = _odd(params.get("kernelSize", 3), default=3, minimum=1)
    iterations = max(1, int(params.get("iterations", 1)))
    kernel = np.ones((kernel_size, kernel_size), dtype=np.uint8)
    op_map = {
        "open": cv2.MORPH_OPEN,
        "close": cv2.MORPH_CLOSE,
        "erode": cv2.MORPH_ERODE,
        "dilate": cv2.MORPH_DILATE,
    }
    out = cv2.morphologyEx(_to_gray(image), op_map.get(operation, cv2.MORPH_OPEN), kernel, iterations=iterations)
    return _gray_to_color(out, image)


def _apply_line_thicken(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    amount = max(1, int(params.get("amount", 1)))
    gray = _to_gray(image)
    binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    inverted = 255 - binary
    size = 2 if amount == 1 else 3
    thick = cv2.dilate(inverted, np.ones((size, size), dtype=np.uint8), iterations=1)
    return _gray_to_color(255 - thick, image)


def _apply_pencil_cleanup(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    gray = _to_gray(image)
    denoise = float(params.get("denoise", 4.0))
    if denoise > 0:
        gray = cv2.fastNlMeansDenoising(gray, None, h=denoise, templateWindowSize=7, searchWindowSize=21)
    gray = _auto_contrast(gray)
    blur = cv2.GaussianBlur(gray, (0, 0), float(params.get("sigma", 0.8)))
    amount = float(params.get("amount", 0.25))
    out = cv2.addWeighted(gray, 1.0 + amount, blur, -amount, 0)
    return _gray_to_color(np.clip(out, 0, 255).astype(np.uint8), image)


def _apply_lineart_cleanup(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    gray = _to_gray(image)
    denoise = float(params.get("denoise", 4.0))
    if denoise > 0:
        gray = cv2.fastNlMeansDenoising(gray, None, h=denoise, templateWindowSize=7, searchWindowSize=21)
    gray = _auto_contrast(gray)
    if bool(params.get("adaptive", True)):
        block_size = _odd(params.get("blockSize", 31), default=31, minimum=3)
        c_value = float(params.get("c", 12))
        binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block_size, c_value)
    else:
        threshold = int(params.get("threshold", 180))
        binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)[1]

    kernel = np.ones((2, 2), dtype=np.uint8)
    if bool(params.get("open", False)):
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    if bool(params.get("close", True)):
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    line_thicken = int(params.get("lineThicken", 1))
    if line_thicken > 0:
        size = 2 if line_thicken == 1 else 3
        thick = cv2.dilate(255 - binary, np.ones((size, size), dtype=np.uint8), iterations=1)
        binary = 255 - thick

    return _gray_to_color(binary, image)


def _apply_custom_kernel(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    kernel_values = params.get("kernel", [[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    kernel = np.array(kernel_values, dtype=np.float32)
    if kernel.shape != (3, 3):
        raise ValueError("Custom kernel must be 3x3")
    if bool(params.get("normalize", False)):
        kernel_sum = float(kernel.sum())
        if abs(kernel_sum) > 1e-9:
            kernel = kernel / kernel_sum
    return cv2.filter2D(image, -1, kernel)


def _apply_upscale(method: str) -> ImageOp:
    def _runner(image: np.ndarray, params: dict[str, Any]) -> np.ndarray:
        return upscale_image(image, method=method, scale=float(params.get("scale", 2.0)))

    return _runner


OPERATION_DEFINITIONS: list[OperationDefinition] = [
    OperationDefinition("gaussian", "Gaussian Blur", "smoothing", True, True, [{"key": "ksize", "label": "Kernel", "type": "number", "min": 3, "max": 21, "step": 2, "default": 5}, {"key": "sigma", "label": "Sigma", "type": "number", "min": 0, "max": 10, "step": 0.1, "default": 0}]),
    OperationDefinition("median", "Median Denoise", "smoothing", True, True, [{"key": "ksize", "label": "Kernel", "type": "number", "min": 3, "max": 21, "step": 2, "default": 5}]),
    OperationDefinition("bilateral", "Bilateral Smooth", "smoothing", True, True, [{"key": "diameter", "label": "Diameter", "type": "number", "min": 3, "max": 21, "step": 1, "default": 9}, {"key": "sigmaColor", "label": "Color Sigma", "type": "number", "min": 1, "max": 200, "step": 1, "default": 75}, {"key": "sigmaSpace", "label": "Space Sigma", "type": "number", "min": 1, "max": 200, "step": 1, "default": 75}]),
    OperationDefinition("nonlocal", "Non-Local Means", "smoothing", True, True, [{"key": "strength", "label": "Strength", "type": "number", "min": 0, "max": 30, "step": 0.5, "default": 10}, {"key": "colorStrength", "label": "Color Strength", "type": "number", "min": 0, "max": 30, "step": 0.5, "default": 10}]),
    OperationDefinition("guided", "Guided Smooth", "smoothing", True, True, [{"key": "radius", "label": "Radius", "type": "number", "min": 1, "max": 20, "step": 1, "default": 8}, {"key": "epsilon", "label": "Epsilon", "type": "number", "min": 0.001, "max": 0.2, "step": 0.001, "default": 0.01}]),
    OperationDefinition("box", "Box Filter", "smoothing", True, True, [{"key": "ksize", "label": "Kernel", "type": "number", "min": 3, "max": 21, "step": 2, "default": 3}]),
    OperationDefinition("weighted_average", "Weighted Average", "smoothing", True, True, [{"key": "ksize", "label": "Kernel", "type": "number", "min": 3, "max": 9, "step": 2, "default": 3}]),
    OperationDefinition("unsharp", "Unsharp Mask", "sharpen", True, True, [{"key": "sigma", "label": "Sigma", "type": "number", "min": 0.1, "max": 5, "step": 0.1, "default": 1.2}, {"key": "amount", "label": "Amount", "type": "number", "min": 0.1, "max": 4, "step": 0.1, "default": 1.2}]),
    OperationDefinition("highboost", "High-Boost", "sharpen", True, True, [{"key": "sigma", "label": "Sigma", "type": "number", "min": 0.1, "max": 5, "step": 0.1, "default": 1.2}, {"key": "boost", "label": "Boost", "type": "number", "min": 1.1, "max": 5, "step": 0.1, "default": 1.8}]),
    OperationDefinition("laplacian", "Laplacian", "sharpen", True, True, [{"key": "connectivity", "label": "Kernel", "type": "select", "default": 4, "options": [{"label": "4-neighbor", "value": 4}, {"label": "8-neighbor", "value": 8}]}, {"key": "sharpen", "label": "Sharpen", "type": "boolean", "default": True}]),
    OperationDefinition("log", "LoG", "sharpen", True, True, [{"key": "ksize", "label": "Kernel", "type": "number", "min": 3, "max": 21, "step": 2, "default": 5}, {"key": "sigma", "label": "Sigma", "type": "number", "min": 0.1, "max": 5, "step": 0.1, "default": 1.0}]),
    OperationDefinition("wiener", "Wiener Restore", "restore", True, True, [{"key": "psfSize", "label": "PSF Size", "type": "number", "min": 3, "max": 11, "step": 2, "default": 5}, {"key": "balance", "label": "Balance", "type": "number", "min": 0.001, "max": 0.1, "step": 0.001, "default": 0.01}]),
    OperationDefinition("richardson", "Richardson-Lucy", "restore", True, True, [{"key": "psfSize", "label": "PSF Size", "type": "number", "min": 3, "max": 11, "step": 2, "default": 5}, {"key": "sigma", "label": "PSF Sigma", "type": "number", "min": 0.1, "max": 5, "step": 0.1, "default": 1.5}, {"key": "iterations", "label": "Iterations", "type": "number", "min": 1, "max": 30, "step": 1, "default": 10}]),
    OperationDefinition("sobel", "Sobel", "analysis", True, True, []),
    OperationDefinition("prewitt", "Prewitt", "analysis", True, True, []),
    OperationDefinition("gradient", "Gradient Magnitude", "analysis", True, True, []),
    OperationDefinition("threshold", "Threshold", "cleanup", True, True, [{"key": "threshold", "label": "Threshold", "type": "number", "min": 0, "max": 255, "step": 1, "default": 180}]),
    OperationDefinition("adaptive_threshold", "Adaptive Threshold", "cleanup", True, True, [{"key": "blockSize", "label": "Block Size", "type": "number", "min": 3, "max": 61, "step": 2, "default": 31}, {"key": "c", "label": "C", "type": "number", "min": -20, "max": 20, "step": 1, "default": 12}]),
    OperationDefinition("morphology", "Morphology", "cleanup", True, True, [{"key": "operation", "label": "Mode", "type": "select", "default": "open", "options": [{"label": "Open", "value": "open"}, {"label": "Close", "value": "close"}, {"label": "Erode", "value": "erode"}, {"label": "Dilate", "value": "dilate"}]}, {"key": "kernelSize", "label": "Kernel", "type": "number", "min": 1, "max": 11, "step": 2, "default": 3}, {"key": "iterations", "label": "Iterations", "type": "number", "min": 1, "max": 6, "step": 1, "default": 1}]),
    OperationDefinition("line_thicken", "Line Thicken", "cleanup", True, True, [{"key": "amount", "label": "Amount", "type": "number", "min": 1, "max": 2, "step": 1, "default": 1}]),
    OperationDefinition("pencil_cleanup", "Pencil Cleanup", "cleanup", True, True, [{"key": "denoise", "label": "Denoise", "type": "number", "min": 0, "max": 12, "step": 0.5, "default": 4}, {"key": "sigma", "label": "Sigma", "type": "number", "min": 0.1, "max": 5, "step": 0.1, "default": 0.8}, {"key": "amount", "label": "Sharpen", "type": "number", "min": 0.1, "max": 1.2, "step": 0.05, "default": 0.25}]),
    OperationDefinition("lineart_cleanup", "Line Art Cleanup", "cleanup", True, True, [{"key": "denoise", "label": "Denoise", "type": "number", "min": 0, "max": 12, "step": 0.5, "default": 4}, {"key": "adaptive", "label": "Adaptive", "type": "boolean", "default": True}, {"key": "blockSize", "label": "Block Size", "type": "number", "min": 3, "max": 61, "step": 2, "default": 31}, {"key": "c", "label": "C", "type": "number", "min": -20, "max": 20, "step": 1, "default": 12}, {"key": "threshold", "label": "Threshold", "type": "number", "min": 0, "max": 255, "step": 1, "default": 180}, {"key": "open", "label": "Morph Open", "type": "boolean", "default": False}, {"key": "close", "label": "Morph Close", "type": "boolean", "default": True}, {"key": "lineThicken", "label": "Line Thicken", "type": "number", "min": 0, "max": 2, "step": 1, "default": 1}]),
    OperationDefinition("nearest", "Nearest Upscale", "upscale", False, True, [{"key": "scale", "label": "Scale", "type": "number", "min": 1, "max": 8, "step": 0.5, "default": 2}]),
    OperationDefinition("bilinear", "Bilinear Upscale", "upscale", False, True, [{"key": "scale", "label": "Scale", "type": "number", "min": 1, "max": 8, "step": 0.5, "default": 2}]),
    OperationDefinition("bicubic_lib", "Bicubic Upscale", "upscale", False, True, [{"key": "scale", "label": "Scale", "type": "number", "min": 1, "max": 8, "step": 0.5, "default": 2}]),
    OperationDefinition("spline", "Spline Upscale", "upscale", False, True, [{"key": "scale", "label": "Scale", "type": "number", "min": 1, "max": 8, "step": 0.5, "default": 2}]),
    OperationDefinition("bicubic_custom", "Custom Bicubic", "upscale", False, True, [{"key": "scale", "label": "Scale", "type": "number", "min": 1, "max": 8, "step": 0.5, "default": 2}]),
    OperationDefinition("lanczos_custom", "Lanczos", "upscale", False, True, [{"key": "scale", "label": "Scale", "type": "number", "min": 1, "max": 8, "step": 0.5, "default": 2}]),
    OperationDefinition("custom_kernel", "Custom 3x3 Kernel", "expert", True, True, [{"key": "normalize", "label": "Normalize", "type": "boolean", "default": False}, {"key": "kernel", "label": "Kernel", "type": "matrix3x3", "default": [[0, -1, 0], [-1, 5, -1], [0, -1, 0]]}]),
]


OPERATION_IMPLS: dict[str, ImageOp] = {
    "gaussian": _apply_gaussian,
    "median": _apply_median,
    "bilateral": _apply_bilateral,
    "nonlocal": _apply_nonlocal,
    "guided": _apply_guided,
    "box": _apply_box,
    "weighted_average": _apply_weighted_average,
    "unsharp": _apply_unsharp,
    "highboost": _apply_highboost,
    "laplacian": _apply_laplacian,
    "log": _apply_log,
    "wiener": _apply_wiener,
    "richardson": _apply_richardson,
    "sobel": _apply_sobel,
    "prewitt": _apply_prewitt,
    "gradient": _apply_gradient,
    "threshold": _apply_threshold,
    "adaptive_threshold": _apply_adaptive_threshold,
    "morphology": _apply_morphology,
    "line_thicken": _apply_line_thicken,
    "pencil_cleanup": _apply_pencil_cleanup,
    "lineart_cleanup": _apply_lineart_cleanup,
    "nearest": _apply_upscale("nearest"),
    "bilinear": _apply_upscale("bilinear"),
    "bicubic_lib": _apply_upscale("bicubic_lib"),
    "spline": _apply_upscale("spline"),
    "bicubic_custom": _apply_upscale("bicubic_custom"),
    "lanczos_custom": _apply_upscale("lanczos_custom"),
    "custom_kernel": _apply_custom_kernel,
}


OPERATION_LOOKUP = {definition.id: definition for definition in OPERATION_DEFINITIONS}


def default_target() -> dict[str, Any]:
    return {
        "scope": "global",
        "bounds": {"x": 0.15, "y": 0.15, "width": 0.5, "height": 0.5},
        "featherPx": 0,
        "maskGenerator": "none",
        "maskParams": {"threshold": 160, "low": 60, "high": 180, "min": 0.2, "max": 1.0},
        "invertMask": False,
    }


def _step(step_id: str, params: dict[str, Any] | None = None, target: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": f"preset-{step_id}",
        "operationId": step_id,
        "enabled": True,
        "previewEnabled": True,
        "params": params or {},
        "target": target or default_target(),
    }


DEFAULT_PRESETS: list[dict[str, Any]] = [
    {"name": "Quick Enhance", "description": "Denoise gently, then sharpen details.", "mode": "editor", "pipeline": [_step("gaussian", {"ksize": 5, "sigma": 0.8}), _step("unsharp", {"sigma": 1.2, "amount": 0.7})]},
    {"name": "Clean Line Art", "description": "Threshold and reconnect thin sketch lines.", "mode": "editor", "pipeline": [_step("lineart_cleanup", {"denoise": 4, "adaptive": True, "lineThicken": 1, "close": True})]},
    {"name": "Pencil Cleanup", "description": "Preserve graphite texture while clarifying strokes.", "mode": "editor", "pipeline": [_step("pencil_cleanup", {"denoise": 3.5, "sigma": 0.8, "amount": 0.3})]},
    {"name": "Upscale 2x", "description": "Bicubic upscale tuned for photos and scans.", "mode": "editor", "pipeline": [_step("bicubic_lib", {"scale": 2})]},
    {"name": "Upscale 4x", "description": "Lanczos upscale for detailed images.", "mode": "editor", "pipeline": [_step("lanczos_custom", {"scale": 4})]},
    {"name": "Sharpen Details", "description": "Crisper local contrast with high-boost sharpening.", "mode": "editor", "pipeline": [_step("highboost", {"sigma": 1.2, "boost": 1.9})]},
    {"name": "Edge Extract", "description": "Strong edge map for inspection workflows.", "mode": "editor", "pipeline": [_step("sobel")]},
    {"name": "Custom Kernel Lab", "description": "Starter kernel for lab experiments.", "mode": "lab", "pipeline": [_step("custom_kernel", {"normalize": False, "kernel": [[0, -1, 0], [-1, 5, -1], [0, -1, 0]]})]},
]


def list_operation_payloads() -> list[dict[str, Any]]:
    return [
        {
            "id": definition.id,
            "label": definition.label,
            "category": definition.category,
            "supportsMask": definition.supports_mask,
            "supportsPreview": definition.supports_preview,
            "paramsSchema": definition.params_schema,
        }
        for definition in OPERATION_DEFINITIONS
    ]


def get_operation_defaults(operation_id: str) -> dict[str, Any]:
    definition = OPERATION_LOOKUP[operation_id]
    params = {}
    for field in definition.params_schema:
        params[field["key"]] = field.get("default")
    return params


def apply_operation(image: np.ndarray, operation_id: str, params: dict[str, Any]) -> np.ndarray:
    if operation_id not in OPERATION_IMPLS:
        raise ValueError(f"Unknown operation: {operation_id}")
    return OPERATION_IMPLS[operation_id](image, params)
