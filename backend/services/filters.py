import cv2
import numpy as np
from skimage.restoration import wiener, richardson_lucy
from skimage import img_as_float
import asyncio
import base64


def apply_full_filter(img: np.ndarray, filter_name: str, params: dict):
    """EXACT same logic as the batch script (fully fixed for color images)."""
    processed = img.copy()

    if filter_name == "gaussian":
        processed = cv2.GaussianBlur(processed, (5, 5), 0)
    elif filter_name == "median":
        k = params.get("ksize", 5)
        k = k if k % 2 == 1 else k + 1
        processed = cv2.medianBlur(processed, k)
    elif filter_name == "bilateral":
        processed = cv2.bilateralFilter(processed, 9, 75, 75)
    elif filter_name == "nonlocal":
        processed = cv2.fastNlMeansDenoisingColored(processed, None, 10, 10, 7, 21)
    elif filter_name == "guided":
        try:
            guide = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY) if len(processed.shape) == 3 else processed
            processed = cv2.ximgproc.guidedFilter(guide, processed, 8, 0.01)
        except (AttributeError, Exception):
            # Safe fallback if ximgproc is missing
            processed = cv2.bilateralFilter(processed, 9, 75, 75)
    elif filter_name == "unsharp":
        blur = cv2.GaussianBlur(processed, (5, 5), 0)
        processed = cv2.addWeighted(processed, 1.5, blur, -0.5, 0)
    elif filter_name == "highboost":
        blur = cv2.GaussianBlur(processed, (5, 5), 0)
        processed = cv2.addWeighted(processed, params.get("boost", 2.0), blur, 1 - params.get("boost", 2.0), 0)
    elif filter_name == "log":
        gray = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY) if len(processed.shape) == 3 else processed
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        lap = cv2.Laplacian(blur, cv2.CV_64F)
        processed = cv2.convertScaleAbs(lap)
        if len(img.shape) == 3:
            processed = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)
    elif filter_name == "wiener":
        psf = np.ones((5, 5)) / 25
        if len(img.shape) == 3:  # color → per-channel
            channels = cv2.split(img)
            restored_channels = []
            for ch in channels:
                float_ch = img_as_float(ch)
                restored_ch = wiener(float_ch, psf, 0.01)
                restored_channels.append((restored_ch * 255).clip(0, 255).astype(np.uint8))
            processed = cv2.merge(restored_channels)
        else:  # grayscale
            float_img = img_as_float(img)
            restored = wiener(float_img, psf, 0.01)
            processed = (restored * 255).clip(0, 255).astype(np.uint8)
    elif filter_name == "richardson":
        psf = cv2.getGaussianKernel(5, 1.5)
        psf = psf @ psf.T
        if len(img.shape) == 3:  # color → per-channel
            channels = cv2.split(img)
            restored_channels = []
            for ch in channels:
                float_ch = img_as_float(ch)
                restored_ch = richardson_lucy(float_ch, psf, iterations=10)
                restored_channels.append((restored_ch * 255).clip(0, 255).astype(np.uint8))
            processed = cv2.merge(restored_channels)
        else:  # grayscale
            float_img = img_as_float(img)
            restored = richardson_lucy(float_img, psf, iterations=10)
            processed = (restored * 255).clip(0, 255).astype(np.uint8)
    elif filter_name == "sobel":
        gray = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY) if len(processed.shape) == 3 else processed
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        magnitude = cv2.magnitude(sobelx, sobely)
        processed = cv2.convertScaleAbs(magnitude)
        if len(img.shape) == 3:
            processed = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)
    elif filter_name == "prewitt":
        gray = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY) if len(processed.shape) == 3 else processed
        kernelx = np.array([[-1, 0, 1], [-1, 0, 1], [-1, 0, 1]], dtype=np.float32)
        kernely = np.array([[-1, -1, -1], [0, 0, 0], [1, 1, 1]], dtype=np.float32)
        prewittx = cv2.filter2D(gray.astype(np.float32), -1, kernelx)
        prewitty = cv2.filter2D(gray.astype(np.float32), -1, kernely)
        magnitude = cv2.magnitude(prewittx, prewitty)
        processed = cv2.convertScaleAbs(magnitude)
        if len(img.shape) == 3:
            processed = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)
    elif filter_name == "custom":
        if "kernel" in params and isinstance(params["kernel"], (list, np.ndarray)):
            kernel = np.array(params["kernel"], dtype=np.float32)
            processed = cv2.filter2D(processed, -1, kernel)

    return processed


def encode_img(img: np.ndarray):
    _, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buffer).decode()


async def process_and_stream(img: np.ndarray, filter_name: str, params: dict):
    """Progressive raster scan using the FIXED full filter (same as batch script)."""
    h = img.shape[0]
    processed = apply_full_filter(img, filter_name, params)

    # Send original
    yield encode_img(img)

    step = 1  # per-row raster

    for row in range(step, h + step, step):
        temp = img.copy()
        temp[:row] = processed[:row]          # reveal filtered rows
        yield encode_img(temp)
        await asyncio.sleep(0.12)             # visible delay

    # Final full-quality image
    yield "FINAL_DONE"
    yield encode_img(processed)