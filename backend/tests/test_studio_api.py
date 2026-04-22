from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)

from app.database.base import create_tables
from main import app


def make_test_image() -> bytes:
    image = np.zeros((64, 64, 3), dtype=np.uint8)
    image[:, :32] = (40, 110, 220)
    image[:, 32:] = (220, 180, 30)
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError("Failed to encode test image")
    return encoded.tobytes()


def sample_pipeline() -> list[dict]:
    return [
        {
            "id": "gaussian-step",
            "operationId": "gaussian",
            "enabled": True,
            "previewEnabled": True,
            "params": {"ksize": 5, "sigma": 0.8},
            "target": {
                "scope": "global",
                "bounds": {"x": 0.15, "y": 0.15, "width": 0.5, "height": 0.5},
                "featherPx": 0,
                "maskGenerator": "none",
                "maskParams": {"threshold": 160, "low": 60, "high": 180, "min": 0.2, "max": 1.0},
                "invertMask": False,
            },
        }
    ]


class StudioApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        create_tables()
        cls.client = TestClient(app)

    def test_import_preview_export_and_batch(self):
        upload = self.client.post(
            "/api/assets",
            files=[("files", ("studio-test.png", make_test_image(), "image/png"))],
        )
        self.assertEqual(upload.status_code, 200)
        asset = upload.json()["items"][0]
        self.assertEqual(asset["width"], 64)

        operations = self.client.get("/api/operations")
        self.assertEqual(operations.status_code, 200)
        self.assertTrue(any(item["id"] == "gaussian" for item in operations.json()["operations"]))

        preview_job = self.client.post(
            "/api/previews",
            json={"asset_id": asset["id"], "pipeline": sample_pipeline(), "mode": "editor"},
        )
        self.assertEqual(preview_job.status_code, 200)
        job_id = preview_job.json()["id"]

        stream = self.client.get(f"/api/jobs/{job_id}/stream")
        self.assertEqual(stream.status_code, 200)
        self.assertIn("event: complete", stream.text)

        exported = self.client.post(
            "/api/exports",
            json={"asset_id": asset["id"], "pipeline": sample_pipeline(), "format": "png", "name": "api-test"},
        )
        self.assertEqual(exported.status_code, 200)
        self.assertEqual(exported.json()["job"]["status"], "completed")

        batch = self.client.post(
            "/api/batches",
            json={"asset_ids": [asset["id"]], "pipeline": sample_pipeline(), "format": "png", "name": "api-batch"},
        )
        self.assertEqual(batch.status_code, 200)
        self.assertEqual(batch.json()["batch"]["status"], "completed")

        history = self.client.get("/api/history")
        self.assertEqual(history.status_code, 200)
        self.assertTrue(history.json()["jobs"])


if __name__ == "__main__":
    unittest.main()
