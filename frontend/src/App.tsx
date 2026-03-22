import { useState, useRef } from 'react';
import { Toaster, toast } from 'react-hot-toast';
import UploadDropzone from './components/UploadDropzone';
import Controls from './components/Controls';
import CanvasPreview from './components/CanvasPreview';

export default function App() {
  const [imageId, setImageId] = useState<number | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);   // ✅ added
  const [imageBlob, setImageBlob] = useState<Blob | null>(null);   // ✅ added
  const [selectedFilter, setSelectedFilter] = useState("gaussian");
  const [useClientRaster, setUseClientRaster] = useState(true);
  const [customKernel, setCustomKernel] = useState<number[][]>([
    [0, -1, 0], [-1, 5, -1], [0, -1, 0]
  ]);

  const canvasRef = useRef<any>(null);

  // ✅ Fix 2: receive all three values from dropzone
  const handleUploadSuccess = (id: number, url: string, blob: Blob) => {
    setImageId(id);
    setImageUrl(url);
    setImageBlob(blob);
  };

  const startScan = () => {
    if (!imageId) { toast.error("Upload an image first!"); return; }
    canvasRef.current?.startFilter(selectedFilter, useClientRaster, customKernel);
    toast.success(`🚀 Scanning with ${selectedFilter}`);
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-white">
      <Toaster position="top-center" />
      <div className="flex h-screen">
        <div className="w-96 border-r border-zinc-700 p-6 overflow-auto space-y-6">
          <h1 className="text-3xl font-bold">🖼️ KernelFlow • PixelScan</h1>

          <UploadDropzone onUploadSuccess={handleUploadSuccess} />

          <Controls
            selectedFilter={selectedFilter}
            setSelectedFilter={setSelectedFilter}
            useClientRaster={useClientRaster}
            setUseClientRaster={setUseClientRaster}
            customKernel={customKernel}
            setCustomKernel={setCustomKernel}
          />

          <button
            onClick={startScan}
            className="w-full bg-emerald-600 hover:bg-emerald-500 py-4 rounded-xl font-bold text-lg shadow-lg">
            🚀 Start Visible Raster Scan
          </button>

          <button onClick={() => window.location.reload()} className="text-xs text-zinc-400 underline">
            Reset / New Image
          </button>
        </div>

        <div className="flex-1 flex flex-col items-center justify-center p-8 bg-zinc-900">
          <CanvasPreview
            ref={canvasRef}
            imageUrl={imageUrl}   // ✅ passed down
            imageBlob={imageBlob} // ✅ passed down
          />
        </div>
      </div>
    </div>
  );
}