import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import axios from 'axios';
import toast from 'react-hot-toast';

type Props = {
  onUploadSuccess: (id: number, url: string, blob: Blob) => void; // ✅ Fix 2
};

export default function UploadDropzone({ onUploadSuccess }: Props) {
  const onDrop = useCallback(async (files: File[]) => {
    const file = files[0];
    const form = new FormData();
    form.append('file', file);

    try {
      const res = await axios.post('/api/upload', form);
      const objectUrl = URL.createObjectURL(file); // ✅ local preview URL
      onUploadSuccess(res.data.id, objectUrl, file);
      toast.success("✅ Uploaded! ID: " + res.data.id);
    } catch {
      toast.error("Upload failed");
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'image/*': [] },
  });

  return (
    <div
      {...getRootProps()}
      className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors
        ${isDragActive ? 'border-emerald-400 bg-emerald-950' : 'border-zinc-600 hover:border-emerald-500'}`}
    >
      <input {...getInputProps()} />
      <p className="text-sm text-zinc-300">Drop image here or click to upload</p>
    </div>
  );
}