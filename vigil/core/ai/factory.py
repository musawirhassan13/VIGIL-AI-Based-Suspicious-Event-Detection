"""Default detector setup: YOLOv8n on CPU.

Weights are looked up in <project root>/models/ first, otherwise
Ultralytics downloads yolov8n.pt automatically on first use.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .detector import PersonDetector, YoloPersonDetector

MODELS_DIR = Path(__file__).resolve().parents[3] / "models"


def default_weights() -> str:
    local = MODELS_DIR / "yolov8n.pt"
    return str(local) if local.is_file() else "yolov8n.pt"


def default_detector_factory(conf: float = 0.25) -> Callable[[], PersonDetector]:
    """Build and warm up the default detector inside its worker thread."""
    def build() -> PersonDetector:
        det = YoloPersonDetector(default_weights(), conf=conf)
        det.warmup()
        return det
    return build
