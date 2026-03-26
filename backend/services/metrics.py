import cv2
import numpy as np
from skimage.metrics import mean_squared_error, peak_signal_noise_ratio, structural_similarity
import matplotlib.pyplot as plt
import csv
from pathlib import Path
from datetime import datetime

METRICS_DIR = Path("metrics")
METRICS_DIR.mkdir(exist_ok=True)
PLOTS_DIR = METRICS_DIR / "plots"
PLOTS_DIR.mkdir(exist_ok=True)
CSV_FILE = METRICS_DIR / "filter_metrics.csv"


def compute_metrics(original: np.ndarray, processed: np.ndarray):
    """Compute important quality metrics between original and processed image."""
    # Ensure same shape (safety)
    if original.shape != processed.shape:
        processed = cv2.resize(processed, (original.shape[1], original.shape[0]))

    mse = mean_squared_error(original, processed)
    psnr = peak_signal_noise_ratio(original, processed, data_range=255.0)
    ssim = structural_similarity(
        original, processed,
        channel_axis=2 if len(original.shape) == 3 else None,
        data_range=255.0
    )

    return {
        "mse": float(mse),
        "psnr": float(psnr),
        "ssim": float(ssim)
    }


def save_metrics_to_csv(image_filename: str, filter_name: str, params: dict, metrics: dict):
    """Append metrics to CSV (never overwrites)."""
    fieldnames = ["timestamp", "image_filename", "filter_name", "params", "mse", "psnr", "ssim"]

    file_exists = CSV_FILE.exists()
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()

        row = {
            "timestamp": datetime.utcnow().isoformat(),
            "image_filename": image_filename,
            "filter_name": filter_name,
            "params": str(params),
            "mse": metrics["mse"],
            "psnr": metrics["psnr"],
            "ssim": metrics["ssim"]
        }
        writer.writerow(row)


def save_metrics_plot(original: np.ndarray, processed: np.ndarray, image_filename: str, filter_name: str, metrics: dict):
    """Save a rich figure with original/processed images, histogram, and metrics."""
    fig, axs = plt.subplots(2, 2, figsize=(14, 10))

    # Original
    orig_rgb = cv2.cvtColor(original, cv2.COLOR_BGR2RGB) if len(original.shape) == 3 else original
    axs[0, 0].imshow(orig_rgb, cmap="gray" if len(original.shape) == 2 else None)
    axs[0, 0].set_title("Original Image")
    axs[0, 0].axis("off")

    # Processed
    proc_rgb = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB) if len(processed.shape) == 3 else processed
    axs[0, 1].imshow(proc_rgb, cmap="gray" if len(processed.shape) == 2 else None)
    axs[0, 1].set_title(f"Processed — {filter_name}")
    axs[0, 1].axis("off")

    # Histogram (intensity)
    if len(original.shape) == 3:
        orig_gray = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY)
        proc_gray = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)
    else:
        orig_gray = original
        proc_gray = processed

    axs[1, 0].hist(orig_gray.ravel(), bins=256, color="blue", alpha=0.6, label="Original")
    axs[1, 0].hist(proc_gray.ravel(), bins=256, color="red", alpha=0.6, label="Processed")
    axs[1, 0].set_title("Intensity Histogram Comparison")
    axs[1, 0].set_xlabel("Pixel Intensity")
    axs[1, 0].set_ylabel("Count")
    axs[1, 0].legend()

    # Metrics summary
    axs[1, 1].axis("off")
    text = (
        f"MSE  : {metrics['mse']:.2f}\n"
        f"PSNR : {metrics['psnr']:.2f} dB\n"
        f"SSIM : {metrics['ssim']:.4f}\n\n"
        f"Image: {image_filename}\n"
        f"Filter: {filter_name}\n"
        f"Time : {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    axs[1, 1].text(0.05, 0.5, text, fontsize=13, va="center", ha="left", family="monospace")

    plt.suptitle(f"KernelFlow Metrics — {image_filename}", fontsize=16)
    plt.tight_layout()

    # Unique filename
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    plot_path = PLOTS_DIR / f"{Path(image_filename).stem}_{filter_name}_{timestamp}.png"
    plt.savefig(plot_path, dpi=200, bbox_inches="tight")
    plt.close(fig)

    return str(plot_path)