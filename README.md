# KernelFlow vNext

Local-first image processing studio built on a React/Vite frontend and a FastAPI backend.

## What it does

- Import local images and keep them in a local asset library
- Build non-destructive pipelines made of enhancement, filtering, restoration, and upscaling steps
- Apply steps globally or target rectangular, elliptical, cropped, and generated-mask regions
- Compare before/after output with live proxy previews
- Save reusable presets and run the current pipeline across a batch queue
- Switch into Lab mode for raster-scan visualization, custom kernels, histogram review, and MSE/PSNR/SSIM inspection

## Current architecture

### Frontend
- React 19 + TypeScript + Vite
- Three-pane studio UI:
  - asset/preset rail
  - workspace viewer
  - pipeline inspector

### Backend
- FastAPI + SQLAlchemy + SQLite
- Local storage under `backend/storage/`
- Operation registry for:
  - smoothing and denoise
  - sharpening and restoration
  - threshold and morphology cleanup
  - line-art and pencil enhancement
  - interpolation and upscaling
  - custom 3x3 kernels

## API surfaces

- `POST /api/assets`
- `GET /api/assets`
- `GET /api/operations`
- `POST /api/previews`
- `GET /api/jobs/{id}/stream`
- `POST /api/exports`
- `POST /api/batches`
- `GET /api/history`
- `GET/POST /api/presets`

## Local run

### Backend
```powershell
cd backend
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

### Frontend
```powershell
cd frontend
npm install --ignore-scripts
npm run dev
```

Open `http://localhost:5173`.

## Verification

### Frontend
```powershell
cd frontend
node .\node_modules\typescript\bin\tsc -b
node .\node_modules\vite\bin\vite.js build
node .\node_modules\vitest\vitest.mjs run
```

### Backend
```powershell
python -m unittest discover -s backend\tests -v
```

## Repository notes

- Runtime outputs are intentionally ignored:
  - `backend/storage/`
  - `backend/image_filter.db`
  - `backend/metrics/filter_metrics.csv`
  - `backend/metrics/plots/`
