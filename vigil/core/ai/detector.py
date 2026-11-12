"""Person detection. YOLO is imported lazily so the rest of the app (and tests) run without it."""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from ..events import Detection

PERSON_CLASS_ID = 0   # COCO


class PersonDetector(ABC):
    @abstractmethod
    def detect(self, frame: np.ndarray) -> list[Detection]:
        """Return the people found in a BGR frame."""


class YoloPersonDetector(PersonDetector):
    """YOLOv8 person detector (CPU by default).

    Not thread-safe: create one instance per worker thread.
    `model_path` may be a local .pt file or a name like "yolov8n.pt" (auto-downloaded once).
    """

    def __init__(self, model_path: str = "yolov8n.pt", conf: float = 0.4,
                 imgsz: int = 640, device: str = "cpu"):
        try:
            from ultralytics import YOLO
        except ImportError as e:
            raise ImportError("ultralytics is required: pip install ultralytics") from e
        self._model = YOLO(model_path)
        self.conf, self.imgsz, self.device = conf, imgsz, device

    def warmup(self) -> None:
        """Run once on a blank frame so the first real frame isn't slow."""
        self.detect(np.zeros((self.imgsz, self.imgsz, 3), np.uint8))

    def detect(self, frame: np.ndarray) -> list[Detection]:
        result = self._model.predict(frame, classes=[PERSON_CLASS_ID], conf=self.conf,
                                     imgsz=self.imgsz, device=self.device, verbose=False)[0]
        if result.boxes is None or len(result.boxes) == 0:
            return []
        xyxy = result.boxes.xyxy.cpu().numpy()
        confs = result.boxes.conf.cpu().numpy()
        return [Detection(tuple(float(v) for v in b), float(c)) for b, c in zip(xyxy, confs)]
