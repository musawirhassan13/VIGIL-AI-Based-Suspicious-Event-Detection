"""Frame helpers shared by the live and (future) video-analysis workers."""
import cv2
import numpy as np
from PySide6.QtGui import QImage


def downscale(frame: np.ndarray, max_width: int) -> np.ndarray:
    h, w = frame.shape[:2]
    if w <= max_width:
        return frame
    scale = max_width / w
    return cv2.resize(frame, (max_width, max(1, int(h * scale))), interpolation=cv2.INTER_AREA)


def bgr_to_qimage(frame: np.ndarray) -> QImage:
    """Convert an OpenCV BGR frame to a QImage that owns its pixel data."""
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w, _ = rgb.shape
    return QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy()