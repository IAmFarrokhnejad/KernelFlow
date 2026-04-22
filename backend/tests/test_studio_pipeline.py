from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.operations import default_target
from services.pipeline import build_target_mask, run_pipeline


class StudioPipelineTests(unittest.TestCase):
    def test_rectangle_mask_covers_requested_region(self):
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        target = default_target()
        target["scope"] = "rectangle"
        target["bounds"] = {"x": 0.2, "y": 0.2, "width": 0.3, "height": 0.3}
        mask = build_target_mask(image, target)

        self.assertAlmostEqual(float(mask[10, 10]), 0.0, places=3)
        self.assertAlmostEqual(float(mask[35, 35]), 1.0, places=3)

    def test_pipeline_crop_changes_output_dimensions(self):
        image = np.full((40, 60, 3), 160, dtype=np.uint8)
        pipeline = [
            {
                "id": "crop-step",
                "operationId": "gaussian",
                "enabled": True,
                "previewEnabled": True,
                "params": {"ksize": 5, "sigma": 1.0},
                "target": {
                    **default_target(),
                    "scope": "crop",
                    "bounds": {"x": 0.25, "y": 0.25, "width": 0.5, "height": 0.5},
                },
            }
        ]

        result, steps = run_pipeline(image, pipeline, include_steps=True)
        self.assertEqual(result.shape[:2], (20, 30))
        self.assertEqual(len(steps), 1)


if __name__ == "__main__":
    unittest.main()
