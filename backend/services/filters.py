import cv2
import numpy as np
from skimage.restoration import wiener, richardson_lucy
from skimage import img_as_float
import asyncio
import base64

async def process_and_stream(img: np.ndarray, filter_name: str, params: dict):
    h = img.shape[0]
    processed = img.copy()
    
    # Send original
    yield encode_img(processed)
    
    step = max(15, h // 25)  # visible chunks
    
    for row in range(step, h + step, step):
        temp = processed.copy()
        
        if filter_name == "gaussian":
            temp[:row] = cv2.GaussianBlur(temp[:row], (5, 5), 0)
        elif filter_name == "median":
            k = params.get("ksize", 5)
            temp[:row] = cv2.medianBlur(temp[:row], k if k % 2 == 1 else k+1)
        elif filter_name == "bilateral":
            temp[:row] = cv2.bilateralFilter(temp[:row], 9, 75, 75)
        elif filter_name == "nonlocal":
            temp = cv2.fastNlMeansDenoisingColored(temp, None, 10, 10, 7, 21)  # full but we chunk-reveal
            temp[:row] = temp[:row]  # reveal progressively
        elif filter_name == "guided":
            guide = cv2.cvtColor(temp, cv2.COLOR_BGR2GRAY) if len(temp.shape) == 3 else temp
            temp[:row] = cv2.ximgproc.guidedFilter(guide[:row], temp[:row], 8, 0.01)
        elif filter_name == "unsharp":
            blur = cv2.GaussianBlur(temp[:row], (5,5), 0)
            temp[:row] = cv2.addWeighted(temp[:row], 1.5, blur, -0.5, 0)
        elif filter_name == "highboost":
            blur = cv2.GaussianBlur(temp[:row], (5,5), 0)
            temp[:row] = cv2.addWeighted(temp[:row], params.get("boost", 2.0), blur, 1-params.get("boost", 2.0), 0)
        elif filter_name == "log":
            gray = cv2.cvtColor(temp, cv2.COLOR_BGR2GRAY) if len(temp.shape)==3 else temp
            blur = cv2.GaussianBlur(gray, (5,5), 0)
            temp[:row] = cv2.Laplacian(blur, cv2.CV_64F)[:row]
            temp[:row] = cv2.convertScaleAbs(temp[:row])
            if len(temp.shape)==3: temp = cv2.cvtColor(temp, cv2.COLOR_GRAY2BGR)
        elif filter_name == "wiener":
            psf = np.ones((5,5)) / 25
            float_img = img_as_float(temp)
            restored = wiener(float_img, psf, 0.01)
            restored = (restored * 255).clip(0, 255).astype(np.uint8)
            temp = restored
        elif filter_name == "richardson":
            psf = cv2.getGaussianKernel(5, 1.5)
            psf = psf @ psf.T
            float_img = img_as_float(temp)
            restored = richardson_lucy(float_img, psf, iterations=10)
            temp = (restored * 255).clip(0, 255).astype(np.uint8)
        elif filter_name == "sobel":
            gray = cv2.cvtColor(temp[:row], cv2.COLOR_BGR2GRAY) if len(temp.shape) == 3 else temp[:row]
            sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
            magnitude = cv2.magnitude(sobelx, sobely)
            magnitude = cv2.convertScaleAbs(magnitude)
            temp[:row] = cv2.cvtColor(magnitude, cv2.COLOR_GRAY2BGR)

        elif filter_name == "prewitt":
            gray = cv2.cvtColor(temp[:row], cv2.COLOR_BGR2GRAY) if len(temp.shape) == 3 else temp[:row]
            kernelx = np.array([[-1, 0, 1], [-1, 0, 1], [-1, 0, 1]], dtype=np.float32)
            kernely = np.array([[-1, -1, -1], [0, 0, 0], [1, 1, 1]], dtype=np.float32)
            prewittx = cv2.filter2D(gray.astype(np.float32), -1, kernelx)
            prewitty = cv2.filter2D(gray.astype(np.float32), -1, kernely)
            magnitude = cv2.magnitude(prewittx, prewitty)
            magnitude = cv2.convertScaleAbs(magnitude)
            temp[:row] = cv2.cvtColor(magnitude, cv2.COLOR_GRAY2BGR)
        elif filter_name == "custom":
            kernel = np.array(params["kernel"], dtype=np.float32)
            temp = cv2.filter2D(temp, -1, kernel)
        
        # Send current state (top rows updated → scan effect)
        yield encode_img(temp)
        await asyncio.sleep(0.08)  # ← visible delay you asked for
    
    # Final full-quality image
    yield "FINAL_DONE"
    yield encode_img(processed)  # optional final pass

def encode_img(img: np.ndarray):
    _, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buffer).decode()