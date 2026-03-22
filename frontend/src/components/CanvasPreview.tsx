import { forwardRef, useImperativeHandle, useRef, useState, useEffect } from "react";

type Kernel3x3 = number[][];
export type CanvasPreviewHandle = {
  startFilter: (filter: string, isSimple: boolean, kernel?: Kernel3x3) => Promise<void>;
};
type Props = { imageUrl: string | null; imageBlob: Blob | null };

const sleep = (ms: number) => new Promise(r => setTimeout(r, ms));
const clamp = (n: number) => Math.max(0, Math.min(255, Math.round(n)));

export default forwardRef<CanvasPreviewHandle, Props>(function CanvasPreview({ imageUrl, imageBlob }, ref) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  // Show image immediately after upload
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

  // ✅ Reads from `src` (original), writes to `dst` (output) — no cross-pixel contamination
  const convolve3x3 = (
    src: Uint8ClampedArray, dst: Uint8ClampedArray,
    x: number, y: number, w: number, h: number,
    kernel: Kernel3x3, normalize = false
  ) => {
    let r=0,g=0,b=0,sum=0;
    for (let ky=-1;ky<=1;ky++) for (let kx=-1;kx<=1;kx++) {
      const px=Math.min(Math.max(x+kx,0),w-1), py=Math.min(Math.max(y+ky,0),h-1);
      const i=(py*w+px)*4, w_=kernel[ky+1][kx+1];
      r+=src[i]*w_; g+=src[i+1]*w_; b+=src[i+2]*w_; sum+=w_;
    }
    const i=(y*w+x)*4, d=normalize&&sum?sum:1;
    dst[i]=clamp(r/d); dst[i+1]=clamp(g/d); dst[i+2]=clamp(b/d); dst[i+3]=src[i+3];
  };

  const applyFilter = async (filter: string, isSimple: boolean, kernel?: Kernel3x3) => {
    const canvas = canvasRef.current;
    if (!canvas || !imageUrl) return;
    const ctx = canvas.getContext("2d")!;

    // Reload original before every filter run
    const img = new Image();
    img.src = imageUrl;
    await img.decode();
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    ctx.drawImage(img, 0, 0);

    const w = canvas.width, h = canvas.height;
    setIsProcessing(true);

    try {
      if (isSimple) {
        const srcData = ctx.getImageData(0, 0, w, h);
        const src = new Uint8ClampedArray(srcData.data); // ✅ immutable source
        const dst = new Uint8ClampedArray(srcData.data); // ✅ output buffer (same size)

        const gaussKernel: Kernel3x3 = [[1,2,1],[2,4,2],[1,2,1]];
        const unsharpKernel: Kernel3x3 = [[1,2,1],[2,4,2],[1,2,1]]; // blur pass; sharpening applied after

        // ✅ Process row-by-row; repaint every 4 rows (smooth scan, not glacially slow)
        for (let y = 0; y < h; y++) {
          for (let x = 0; x < w; x++) {
            if (filter === "gaussian") {
              convolve3x3(src, dst, x, y, w, h, gaussKernel, true);
            } else if (filter === "custom" && kernel) {
              convolve3x3(src, dst, x, y, w, h, kernel, false);
            } else if (filter === "unsharp") {
              // Blur into temp, then apply unsharp = original + (original - blur)
              const temp = new Uint8ClampedArray(4);
              let r=0,g=0,b=0,sum=0;
              for (let ky=-1;ky<=1;ky++) for (let kx=-1;kx<=1;kx++) {
                const px=Math.min(Math.max(x+kx,0),w-1),py2=Math.min(Math.max(y+ky,0),h-1);
                const i=(py2*w+px)*4,wt=gaussKernel[ky+1][kx+1];
                r+=src[i]*wt;g+=src[i+1]*wt;b+=src[i+2]*wt;sum+=wt;
              }
              const i=(y*w+x)*4;
              dst[i  ]=clamp(src[i  ]*1.5-(r/sum)*0.5);
              dst[i+1]=clamp(src[i+1]*1.5-(g/sum)*0.5);
              dst[i+2]=clamp(src[i+2]*1.5-(b/sum)*0.5);
              dst[i+3]=src[i+3];
            } else {
              // Passthrough for filters not implemented client-side
              const i=(y*w+x)*4;
              dst[i]=src[i];dst[i+1]=src[i+1];dst[i+2]=src[i+2];dst[i+3]=src[i+3];
            }
          }

          // ✅ Paint every 4 rows → smooth visible scan line
          if (y % 4 === 0) {
            srcData.data.set(dst);        // ✅ write back to ImageData buffer
            ctx.putImageData(srcData, 0, 0);
            await sleep(16);
          }
        }

        srcData.data.set(dst);
        ctx.putImageData(srcData, 0, 0);

      } else {
        // Server-side SSE path
        if (!imageBlob) return;
        const form = new FormData();
        form.append("file", imageBlob, "image");
        form.append("params", JSON.stringify({ kernel, boost: 1.8 }));
        form.append("record_id", "0"); // placeholder; backend requires it

        const res = await fetch(`/api/apply/${filter}`, { method: "POST", body: form });
        if (!res.body) return;

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          // SSE frames are separated by \n\n
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
      <canvas ref={canvasRef} className="border-2 border-dashed border-zinc-600 w-full max-h-[600px] object-contain rounded-lg" />
      {isProcessing && (
        <p className="text-sm text-emerald-400 animate-pulse">⚙️ Scanning… watch the raster line move</p>
      )}
    </div>
  );
});