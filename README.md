# KernelFlow


**Real-time spatial domain image filters with visible progressive raster scan**

A beautiful, fully local web application that lets you upload an image and instantly see **every filter being applied row-by-row** from top to bottom; exactly like a real raster scan. Built as a learning tool for EENG583 Digital Image Processing.



## ✨ Features

- **13+ spatial domain filters** (Gaussian, Median, Bilateral, Non-local Means, Guided, Unsharp, High-Boost, LoG, Sobel, Prewitt, Wiener, Richardson-Lucy, Custom 3×3)
- **Two rendering modes**:
  - Client-side raster (fast 3×3 filters directly on canvas)
  - Server-side SSE streaming (all filters with progressive reveal)
- **Real-time progressive raster scan** — watch the filter sweep across the image with adjustable delay
- **Automatic quality metrics** (MSE, PSNR, SSIM) saved to CSV after every filter
- **Detailed metric plots** (original vs processed + histogram + metrics table)
- **SQLite database** for image history
- **100% local** — nothing is sent to any server
- Modern, clean UI with dark theme

## 🚀 Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/IAmFarrokhnejad/KernelFlow
cd KernelFlow
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install fastapi uvicorn sqlalchemy pydantic python-multipart opencv-python numpy scikit-image matplotlib

# Run the backend
uvicorn main:app --reload --port 8000
```

### 3. Frontend Setup

```bash
cd ../frontend

# Install dependencies
npm install

# Run the frontend
npm run dev
```

Open http://localhost:5173 in your browser and start filtering!

## 📁 Project Structure

```
KernelFlow/
├── backend/
│   ├── app/
│   │   ├── crud/
│   │   ├── database/
│   │   ├── models/
│   │   └── main.py
│   ├── services/
│   │   ├── filters.py          # All filter logic + fixes
│   │   └── metrics.py          # MSE/PSNR/SSIM + plots
│   └── uploads/                # Images & processed results
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── App.tsx
│   │   └── ...
│   └── vite.config.ts
├── metrics/                    # Auto-generated CSV + plots
│   ├── filter_metrics.csv
│   └── plots/
└── README.md
```

## 🎛️ Available Filters

| Filter              | Type          | Purpose                        |
|---------------------|---------------|--------------------------------|
| Gaussian            | Smoothing     | Noise reduction                |
| Median              | Non-linear    | Salt & pepper removal          |
| Bilateral           | Edge-preserving | Smoothing without blurring edges |
| Non-Local Means     | Advanced      | Patch-based denoising          |
| Guided              | Edge-preserving | Natural looking smoothing     |
| Unsharp Masking     | Sharpening    | Basic sharpening               |
| High-Boost          | Sharpening    | Controllable boost             |
| LoG (Mexican Hat)   | Edge/Blob     | Laplacian of Gaussian          |
| Sobel               | Edge detection| Gradient magnitude             |
| Prewitt             | Edge detection| Simpler gradient operator      |
| Wiener              | Restoration   | Deconvolution                  |
| Richardson-Lucy     | Restoration   | Iterative deconvolution        |
| Custom 3×3 Mask     | User-defined  | Any convolution kernel         |

## 📊 Metrics & Outputs

After each filter is applied, the app automatically:
- Saves the final processed image
- Computes **MSE, PSNR, SSIM**
- Appends a row to `metrics/filter_metrics.csv`
- Generates a detailed comparison plot in `metrics/plots/`

## 🛠️ Tech Stack

**Backend**
- FastAPI
- SQLAlchemy + SQLite
- OpenCV + scikit-image
- Matplotlib (for plots)

**Frontend**
- React + TypeScript
- Tailwind CSS + shadcn/ui
- Canvas API for client-side filters

## 📝 Notes

- Everything runs locally on your machine
- The progressive raster scan effect is intentional and educational
- You can switch between client-side and server-side mode using the checkbox
- The batch processing script (used only for homework figures) is **not** part of this repository

---

**Made with ❤️ for EENG583 – Digital Image Processing**

Enjoy experimenting with filters!
