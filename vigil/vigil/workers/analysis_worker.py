"""Analyses one uploaded video file in a background thread.

Pipeline: scan_video -> detector -> tracker -> EventEngine.
Side-by-side Depth + RGB clips are automatically cropped to their right-side
RGB view. Regular CCTV footage remains full-frame.
"""
import threading
import time
from collections.abc import Callable

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from ..core.ai.draw import draw_detections
from ..core.ai.event_engine import EventEngine
from ..core.ai.factory import default_detector_factory
from ..core.ai.tracker import PersonTracker
from ..core.ai.video_scan import scan_video, video_info
from .frame_utils import bgr_to_qimage, downscale

PREVIEW_INTERVAL_S = 0.4
PREVIEW_WIDTH = 960
VIDEO_ANALYSIS_SAMPLE_FPS = 10.0
VIDEO_ANALYSIS_DETECTOR_CONF = 0.25


class AnalysisWorker(QThread):
    progress = Signal(int)
    preview = Signal(QImage, float)
    event_found = Signal(object)
    failed = Signal(str)
    done = Signal(bool)

    def __init__(self, path: str, settings: dict, detector_factory: Callable | None = None,
                 engine_factory: Callable[[dict], EventEngine] | None = None, parent=None):
        super().__init__(parent)
        self._path = path
        self._cfg = settings
        self._detector_factory = detector_factory
        self._engine_factory = engine_factory
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        try:
            info = video_info(self._path)
            detector_factory = self._detector_factory or default_detector_factory(
                conf=VIDEO_ANALYSIS_DETECTOR_CONF
            )
            detector = detector_factory()
            engine = (
                self._engine_factory(self._cfg)
                if self._engine_factory
                else EventEngine.from_settings(self._cfg, "upload", "Video file")
            )
            tracker = PersonTracker()
            total = max(1, info.frame_count)
            last_preview, last_pct = 0.0, -1

            for r in scan_video(
                self._path,
                detector,
                sample_fps=VIDEO_ANALYSIS_SAMPLE_FPS,
                tracker=tracker,
                view="auto",
            ):
                if self._stop.is_set():
                    self.done.emit(True)
                    return

                frame_height, frame_width = r.frame.shape[:2]
                frame_size = (frame_width, frame_height)
                events = engine.process(
                        tracker,
                        r.detections,
                        r.frame_index,
                        r.time_s,
                        frame_size,
                        r.time_s,
                        frame=r.frame,
                    )
                for ev in events:
                    self.event_found.emit(ev)

                now = time.monotonic()
                if events or now - last_preview >= PREVIEW_INTERVAL_S:
                    last_preview = now
                    hot = {d.track_id for ev in events for d in ev.detections}
                    draw_detections(
                        r.frame, [d for d in r.detections if d.track_id not in hot]
                    )
                    draw_detections(
                        r.frame, [d for d in r.detections if d.track_id in hot],
                        alert=True
                    )
                    self.preview.emit(
                        bgr_to_qimage(downscale(r.frame, PREVIEW_WIDTH)), r.time_s
                    )

                pct = min(99, int(100 * r.frame_index / total)) if info.frame_count > 0 else 0
                if pct != last_pct:
                    last_pct = pct
                    self.progress.emit(pct)

            if self._stop.is_set():
                self.done.emit(True)
                return
            self.progress.emit(100)
            self.done.emit(False)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(f"{type(e).__name__}: {e}")
