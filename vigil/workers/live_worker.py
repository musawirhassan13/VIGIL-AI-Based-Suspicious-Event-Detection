"""One QThread per live camera: capture -> background AI analysis -> annotated QImage signal.
Never touches widgets. The AI itself runs in LiveAnalyzer's own thread, so slow detection
never freezes the live view."""
import threading
import time
from collections.abc import Callable

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from ..core.ai.draw import draw_detections
from ..core.ai.live_pipeline import LiveAnalyzer
from ..core.capture import FrameSource, parse_source
from .frame_utils import bgr_to_qimage, downscale

RECONNECT_DELAY_S = 3.0
MAX_READ_FAILURES = 5
READ_RETRY_DELAY_S = 0.1
ALERT_HOLD_S = 3.0      # people involved in an event stay red for this long


class LiveWorker(QThread):
    frame_ready = Signal(int, QImage)     # camera_id, display frame (boxes already drawn)
    status_changed = Signal(int, str)     # camera_id, "connecting" | "online" | "reconnecting"
    event_detected = Signal(int, object)  # camera_id, core.events.Event
    ai_error = Signal(int, str)           # camera_id, reason the AI could not run (video keeps playing)

    def __init__(self, camera_id: int, source: str, ui_fps: int = 20,
                 display_width: int = 960,
                 analyzer_factory: Callable[[], LiveAnalyzer] | None = None, parent=None):
        super().__init__(parent)
        self.camera_id = camera_id
        self._source = parse_source(source)   # raises ValueError if empty
        self._min_interval = 1.0 / max(1, ui_fps)
        self._display_width = display_width
        self._stop_event = threading.Event()
        self._analyzer_factory = analyzer_factory
        self._analyzer: LiveAnalyzer | None = None
        self._alert_ids: set[int] = set()
        self._alert_until = 0.0
        self._error_sent = False

    def stop(self) -> None:
        """Non-blocking stop request; the thread exits on its own."""
        self._stop_event.set()

    def run(self) -> None:
        self._analyzer = self._analyzer_factory() if self._analyzer_factory else None
        if self._analyzer is not None:
            self._analyzer.start()
        try:
            first = True
            while not self._stop_event.is_set():
                self.status_changed.emit(self.camera_id, "connecting" if first else "reconnecting")
                first = False
                if self._analyzer is not None:
                    self._analyzer.reset()          # new connection: forget old tracks
                self._stream_once()
                if self._stop_event.wait(RECONNECT_DELAY_S):
                    break
        finally:
            if self._analyzer is not None:
                self._analyzer.stop()

    def _stream_once(self) -> None:
        """Open the source and pump frames until the stream drops or stop() is called."""
        source = FrameSource(self._source)
        try:
            if not source.open():
                return
            failures, announced, last_emit = 0, False, 0.0
            while not self._stop_event.is_set():
                ok, frame = source.read()
                if not ok or frame is None:
                    failures += 1
                    if failures >= MAX_READ_FAILURES:
                        return
                    self._stop_event.wait(READ_RETRY_DELAY_S)
                    continue
                failures = 0
                if not announced:
                    announced = True
                    self.status_changed.emit(self.camera_id, "online")

                now = time.monotonic()
                self._feed_ai(frame, now)
                if now - last_emit >= self._min_interval:
                    last_emit = now
                    display = self._annotate(frame, now)
                    self.frame_ready.emit(
                        self.camera_id, bgr_to_qimage(downscale(display, self._display_width)))
        finally:
            source.release()

    # ---- AI hooks ----
    def _feed_ai(self, frame, now: float) -> None:
        """Hand the frame to the analyzer (if one is due) and forward any new events."""
        a = self._analyzer
        if a is None:
            return
        a.maybe_submit(frame, now)
        for ev in a.pop_events():
            self._alert_ids = {d.track_id for d in ev.detections if d.track_id is not None}
            self._alert_until = now + ALERT_HOLD_S
            self.event_detected.emit(self.camera_id, ev)
        if a.error and not self._error_sent:
            self._error_sent = True
            self.ai_error.emit(self.camera_id, a.error)

    def _annotate(self, frame, now: float):
        """Draw the latest boxes (red for people in a fresh event, purple otherwise) on the frame."""
        a = self._analyzer
        dets = a.latest(now) if a is not None else []
        if not dets:
            return frame
        hot_ids = self._alert_ids if now < self._alert_until else set()
        draw_detections(frame, [d for d in dets if d.track_id not in hot_ids])
        draw_detections(frame, [d for d in dets if d.track_id in hot_ids], alert=True)
        return frame