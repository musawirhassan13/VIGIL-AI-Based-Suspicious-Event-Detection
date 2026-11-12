"""Draw detections on OpenCV frames (colours match the UI theme)."""
from __future__ import annotations

import cv2
import numpy as np

from ..events import Detection
from .rules.restricted_area import Zone

ALERT_BGR = (120, 139, 245)    # #f58b78
NORMAL_BGR = (240, 156, 196)   # #c49cf0


def draw_detections(frame: np.ndarray, detections: list[Detection] | tuple[Detection, ...],
                    alert: bool = False) -> np.ndarray:
    """Draw boxes in place and return the frame."""
    color = ALERT_BGR if alert else NORMAL_BGR
    for d in detections:
        x1, y1, x2, y2 = (int(v) for v in d.box)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        tag = f"#{d.track_id} " if d.track_id is not None else ""
        cv2.putText(frame, f"{tag}{d.confidence:.2f}", (x1, max(14, y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
    return frame


def draw_zones(frame: np.ndarray, zones, color=ALERT_BGR) -> np.ndarray:
    """Outline restricted zones (normalised points) on a frame, in place."""
    h, w = frame.shape[:2]
    for z in zones:
        pts = np.array([[int(x * w), int(y * h)] for x, y in z.points], np.int32)
        cv2.polylines(frame, [pts], True, color, 2, cv2.LINE_AA)
        cv2.putText(frame, z.name, (pts[0][0] + 4, pts[0][1] + 16), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, color, 1, cv2.LINE_AA)
    return frame