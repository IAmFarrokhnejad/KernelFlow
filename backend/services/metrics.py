from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path

import cv2
import matplotlib
import numpy as np
from skimage.metrics import mean_squared_error, peak_signal_noise_ratio, structural_similarity

matplotlib.use("Agg")
import matplotlib.pyplot as plt

METRICS_DIR = Path("metrics")
METRICS_DIR.mkdir(exist_ok=True)
PLOTS_DIR = METRICS_DIR / "plots"
PLOTS_DIR.mkdir(exist_ok=True)
CSV_FILE = METRICS_DIR / "filter_metrics.csv"


def compute_metrics(original: np.ndarray, processed: np.ndarray) -> dict[str, float]:
    if original.shape != processed.shape:
        processed = cv2.resize(processed, (original.shape[1], original.shape[0]))

    mse = mean_squared_error(original, processed)
    psnr = peak_signal_noise_ratio(original, processed, data_range=255.0)
    ssim = structural_similarity(
        original,
        processed,
        channel_axis=2 if len(original.shape) == 3 else None,
        data_range=255.0,
    )
    return {"mse": float(mse), "psnr": float(psnr), "ssim": float(ssim)}


def compute_histograms(original: np.ndarray, processed: np.ndarray, bins: int = 48) -> dict[str, list[float] | int]:
    def _histogram(image: np.ndarray) -> list[float]:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        values, _ = np.histogram(gray.ravel(), bins=bins, range=(0, 256))
        total = max(1, int(values.sum()))
        return [round(float(value) / total, 6) for value in values]

    return {"original": _histogram(original), "processed": _histogram(processed), "bins": bins}


def save_metrics_to_csv(image_filename: str, filter_name: str, params: dict, metrics: dict) -> None:
    fieldnames = ["timestamp", "image_filename", "filter_name", "params", "mse", "psnr", "ssim"]
    file_exists = CSV_FILE.exists()
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "image_filename": image_filename,
                "filter_name": filter_name,
                "params": str(params),
                "mse": metrics["mse"],
                "psnr": metrics["psnr"],
                "ssim": metrics["ssim"],
            }
        )


def save_metrics_plot(
    original: np.ndarray,
    processed: np.ndarray,
    image_filename: str,
    filter_name: str,
    metrics: dict,
) -> str:
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    original_rgb = cv2.cvtColor(original, cv2.COLOR_BGR2RGB) if original.ndim == 3 else original
    processed_rgb = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB) if processed.ndim == 3 else processed

    axes[0, 0].imshow(original_rgb, cmap="gray" if original.ndim == 2 else None)
    axes[0, 0].set_title("Original")
    axes[0, 0].axis("off")

    axes[0, 1].imshow(processed_rgb, cmap="gray" if processed.ndim == 2 else None)
    axes[0, 1].set_title(f"Processed - {filter_name}")
    axes[0, 1].axis("off")

    original_gray = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY) if original.ndim == 3 else original
    processed_gray = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY) if processed.ndim == 3 else processed
    axes[1, 0].hist(original_gray.ravel(), bins=256, color="#2563eb", alpha=0.6, label="Original")
    axes[1, 0].hist(processed_gray.ravel(), bins=256, color="#f97316", alpha=0.6, label="Processed")
    axes[1, 0].set_title("Histogram")
    axes[1, 0].legend()

    axes[1, 1].axis("off")
    summary = (
        f"MSE  : {metrics['mse']:.2f}\n"
        f"PSNR : {metrics['psnr']:.2f} dB\n"
        f"SSIM : {metrics['ssim']:.4f}\n\n"
        f"Image: {image_filename}\n"
        f"Filter: {filter_name}\n"
        f"Time : {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')}"
    )
    axes[1, 1].text(0.05, 0.5, summary, fontsize=13, va="center", ha="left", family="monospace")

    plt.tight_layout()
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    plot_path = PLOTS_DIR / f"{Path(image_filename).stem}_{filter_name}_{timestamp}.png"
    plt.savefig(plot_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return str(plot_path)
