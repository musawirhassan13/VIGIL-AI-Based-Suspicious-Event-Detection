"""Helpers for the Video Analysis page: AnalysisTimeline and ClipPlayer."""
import cv2
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QImage

from .widgets import TimelineBar
from .workers.frame_utils import bgr_to_qimage, downscale


class AnalysisTimeline(TimelineBar):
    """TimelineBar whose progress (0..1) and event markers (fractions 0..1) can be updated."""

    def set_state(self, progress: float, markers) -> None:
        self._progress = max(0.0, min(1.0, progress))
        self._markers = [max(0.0, min(1.0, m)) for m in markers]
        self.update()


class ClipPlayer(QObject):
    """Plays a time range of a video file frame by frame (Play clip). Runs on the UI timer."""
    frame = Signal(QImage, float)     # image, video time in seconds
    finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._cap: cv2.VideoCapture | None = None
        self._end = 0.0

    @property
    def playing(self) -> bool:
        return self._cap is not None

    def play(self, path: str, start_s: float, end_s: float) -> bool:
        self.stop()
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            cap.release()
            self.finished.emit()
            return False
        cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, start_s) * 1000)
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        self._cap, self._end = cap, end_s
        self._timer.start(int(1000 / min(30.0, fps)))
        return True

    def stop(self) -> None:
        self._timer.stop()
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def _tick(self) -> None:
        if self._cap is None:
            return
        ok, frame = self._cap.read()
        t = self._cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
        if not ok or t > self._end:
            self.stop()
            self.finished.emit()
            return
        self.frame.emit(bgr_to_qimage(downscale(frame, 960)), t)