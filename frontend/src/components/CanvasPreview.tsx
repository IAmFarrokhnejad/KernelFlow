import { forwardRef, useImperativeHandle, useRef, useState, useEffect } from "react";

type Kernel3x3 = number[][];
export type CanvasPreviewHandle = {
  startFilter: (filter: string, isSimple: boolean, kernel?: Kernel3x3, recordId?: number) => Promise<void>;
};
type Props = { imageUrl: string | null; imageBlob: Blob | null };

const sleep = (ms: number) => new Promise(r => setTimeout(r, ms));
const clamp = (n: number) => Math.max(0, Math.min(255, Math.round(n)));

export default forwardRef<CanvasPreviewHandle, Props>(function CanvasPreview({ imageUrl, imageBlob }, ref) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  useEffect(() => {
    if (!imageUrl || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d")!;
    const img = new Image();
    img.src = imageUrl;
    img.onload = () => {
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      ctx.drawImage(img, 0, 0);
    };
  }, [imageUrl]);

  const convolve3x3 = (
    src: Uint8ClampedArray, dst: Uint8ClampedArray,
    x: number, y: number, w: number, h: number,
    kernel: Kernel3x3, normalize = false
  ) => {
    let r = 0, g = 0, b = 0, sum = 0;
    for (let ky = -1; ky <= 1; ky++) {
      for (let kx = -1; kx <= 1; kx++) {
        const px = Math.min(Math.max(x + kx, 0), w - 1);
        const py = Math.min(Math.max(y + ky, 0), h - 1);
        const i = (py * w + px) * 4;
        const w_ = kernel[ky + 1][kx + 1];
        r += src[i] * w_;
        g += src[i + 1] * w_;
        b += src[i + 2] * w_;
        sum += w_;
      }
    }
    const i = (y * w + x) * 4;
    const d = normalize && sum ? sum : 1;
    dst[i] = clamp(r / d);
    dst[i + 1] = clamp(g / d);
    dst[i + 2] = clamp(b / d);
    dst[i + 3] = src[i + 3];
  };

  const applyFilter = async (filter: string, isSimple: boolean, kernel?: Kernel3x3, recordId: number = 0) => {
    const canvas = canvasRef.current;
    if (!canvas || !imageUrl) return;
    const ctx = canvas.getContext("2d")!;

    const img = new Image();
    img.src = imageUrl;
    await img.decode();
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    ctx.drawImage(img, 0, 0);

    const w = canvas.width, h = canvas.height;
    setIsProcessing(true);

    const CLIENT_FILTERS = new Set(["gaussian", "unsharp", "custom", "sobel", "prewitt"]);
    const useClientPath = isSimple && CLIENT_FILTERS.has(filter);

    try {
      if (useClientPath) {
        // ====================== TRUE PIXEL-BY-PIXEL RASTER SCAN ======================
        const srcData = ctx.getImageData(0, 0, w, h);
        const src = new Uint8ClampedArray(srcData.data);
        const dst = new Uint8ClampedArray(srcData.data);
        const gaussKernel: Kernel3x3 = [[1, 2, 1], [2, 4, 2], [1, 2, 1]];

        for (let y = 0; y < h; y++) {
          for (let x = 0; x < w; x++) {
            const i = (y * w + x) * 4;

            if (filter === "gaussian") {
              convolve3x3(src, dst, x, y, w, h, gaussKernel, true);
            } else if (filter === "custom" && kernel) {
              convolve3x3(src, dst, x, y, w, h, kernel, false);
            } else if (filter === "unsharp") {
              let r = 0, g = 0, b = 0, sum = 0;
              for (let ky = -1; ky <= 1; ky++) {
                for (let kx = -1; kx <= 1; kx++) {
                  const px = Math.min(Math.max(x + kx, 0), w - 1);
                  const py = Math.min(Math.max(y + ky, 0), h - 1);
                  const ii = (py * w + px) * 4;
                  const wt = gaussKernel[ky + 1][kx + 1];
                  r += src[ii] * wt;
                  g += src[ii + 1] * wt;
                  b += src[ii + 2] * wt;
                  sum += wt;
                }
              }
              dst[i]     = clamp(src[i]     * 1.5 - (r / sum) * 0.5);
              dst[i + 1] = clamp(src[i + 1] * 1.5 - (g / sum) * 0.5);
              dst[i + 2] = clamp(src[i + 2] * 1.5 - (b / sum) * 0.5);
              dst[i + 3] = src[i + 3];
            } else if (filter === "sobel") {
              const sobelX: Kernel3x3 = [[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]];
              const sobelY: Kernel3x3 = [[-1, -2, -1], [0, 0, 0], [1, 2, 1]];
              let gx = 0, gy = 0;
              for (let ky = -1; ky <= 1; ky++) {
                for (let kx = -1; kx <= 1; kx++) {
                  const px = Math.min(Math.max(x + kx, 0), w - 1);
                  const py = Math.min(Math.max(y + ky, 0), h - 1);
                  const ii = (py * w + px) * 4;
                  const lum = 0.299 * src[ii] + 0.587 * src[ii + 1] + 0.114 * src[ii + 2];
                  gx += lum * sobelX[ky + 1][kx + 1];
                  gy += lum * sobelY[ky + 1][kx + 1];
                }
              }
              const mag = clamp(Math.sqrt(gx * gx + gy * gy));
              dst[i] = mag; dst[i + 1] = mag; dst[i + 2] = mag; dst[i + 3] = src[i + 3];
            } else if (filter === "prewitt") {
              const prewittX: Kernel3x3 = [[-1, 0, 1], [-1, 0, 1], [-1, 0, 1]];
              const prewittY: Kernel3x3 = [[-1, -1, -1], [0, 0, 0], [1, 1, 1]];
              let gx = 0, gy = 0;
              for (let ky = -1; ky <= 1; ky++) {
                for (let kx = -1; kx <= 1; kx++) {
                  const px = Math.min(Math.max(x + kx, 0), w - 1);
                  const py = Math.min(Math.max(y + ky, 0), h - 1);
                  const ii = (py * w + px) * 4;
                  const lum = 0.299 * src[ii] + 0.587 * src[ii + 1] + 0.114 * src[ii + 2];
                  gx += lum * prewittX[ky + 1][kx + 1];
                  gy += lum * prewittY[ky + 1][kx + 1];
                }
              }
              const mag = clamp(Math.sqrt(gx * gx + gy * gy));
              dst[i] = mag; dst[i + 1] = mag; dst[i + 2] = mag; dst[i + 3] = src[i + 3];
            }

            // Update canvas after EVERY single pixel
            srcData.data.set(dst);
            ctx.putImageData(srcData, 0, 0);
            await sleep(0.5);   // ← Change this number to make it faster/slower (0.5 = fast, 2 = slow)
          }
        }
      } else {
        // ====================== SERVER-SIDE PATH (unchanged) ======================
        if (!imageBlob) return;
        const form = new FormData();
        form.append("file", imageBlob, "image");
        form.append("params", JSON.stringify({ kernel, boost: 1.8 }));
        form.append("record_id", recordId.toString());

        const res = await fetch(`/api/apply/${filter}`, { method: "POST", body: form });
        if (!res.body) return;

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const frames = buffer.split("\n\n");
          buffer = frames.pop() ?? "";

          for (const frame of frames) {
            const b64 = frame.replace(/^data:\s*/, "").trim();
            if (!b64 || b64 === "FINAL_DONE") continue;
            const newImg = new Image();
            newImg.src = `data:image/jpeg;base64,${b64}`;
            await newImg.decode();
            ctx.drawImage(newImg, 0, 0);
            await sleep(30);
          }
        }
      }
    } finally {
      setIsProcessing(false);
    }
  };

  useImperativeHandle(ref, () => ({ startFilter: applyFilter }));

  return (
    <div className="w-full flex flex-col items-center gap-3">
      <canvas
        ref={canvasRef}
        className="border-2 border-dashed border-zinc-600 w-full max-h-[600px] object-contain rounded-lg"
      />
      {isProcessing && (
        <p className="text-sm text-emerald-400 animate-pulse">
          ⚙️ Pixel-by-pixel raster scan in progress...
        </p>
      )}
    </div>
  );
});