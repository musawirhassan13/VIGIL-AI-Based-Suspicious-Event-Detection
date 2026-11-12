"""A4: live analysis pipeline (Qt-free). One LiveAnalyzer per camera.

The camera thread keeps showing video at full speed and hands frames over with maybe_submit();
a background thread runs detector -> tracker -> EventEngine at the sampling rate and publishes
the latest boxes and any new Events. Slow CPU inference therefore never freezes the live view.
"""
from __future__ import annotations

import threading
from collections.abc import Callable

import numpy as np

from ..events import Detection, Event
from .detector import PersonDetector
from .event_engine import EventEngine
from .tracker import PersonTracker

STALE_S = 2.0   # boxes older than this are not drawn (detector stalled or camera dropped)


class LiveAnalyzer:
    def __init__(self, detector_factory: Callable[[], PersonDetector], engine: EventEngine,
                 sample_fps: float = 5.0):
        self._factory = detector_factory
        self._engine = engine
        self._tracker = PersonTracker()
        self._min_interval = 1.0 / max(0.5, sample_fps)
        self._cond = threading.Condition()
        self._pending: tuple[np.ndarray, float] | None = None
        self._stop = False
        self._reset = False
        self._thread: threading.Thread | None = None
        self._last_submit = float("-inf")
        self._lock = threading.Lock()
        self._dets: list[Detection] = []
        self._dets_time = float("-inf")
        self._events: list[Event] = []
        self.error: str | None = None        # set if the model can't load or inference fails

    # ---- called from the camera thread ----
    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="vigil-analyzer", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 3.0) -> None:
        with self._cond:
            self._stop = True
            self._cond.notify_all()
        if self._thread is not None:
            self._thread.join(timeout)

    def reset(self) -> None:
        """Forget tracks and rule state (call after a camera reconnect)."""
        with self._cond:
            self._reset = True

    def maybe_submit(self, frame: np.ndarray, now_s: float) -> bool:
        """Hand over a frame if one is due. Copies the frame only when it is accepted."""
        if self.error or now_s - self._last_submit < self._min_interval:
            return False
        with self._cond:
            if self._pending is not None:
                return False
            self._pending = (frame.copy(), now_s)
            self._last_submit = now_s
            self._cond.notify()
        return True

    def latest(self, now_s: float) -> list[Detection]:
        with self._lock:
            return list(self._dets) if now_s - self._dets_time <= STALE_S else []

    def pop_events(self) -> list[Event]:
        with self._lock:
            events, self._events = self._events, []
        return events

    # ---- analysis thread ----
    def _run(self) -> None:
        try:
            detector = self._factory()
        except Exception as e:  # noqa: BLE001 - e.g. ultralytics missing, weights not found
            self.error = f"{type(e).__name__}: {e}"
            return
        index = 0
        while True:
            with self._cond:
                while self._pending is None and not self._stop:
                    self._cond.wait(0.2)
                if self._stop:
                    return
                frame, now_s = self._pending
                self._pending = None
                do_reset, self._reset = self._reset, False
            if do_reset:
                self._tracker.reset()
                self._engine.reset()
                with self._lock:
                    self._dets = []
            try:
                h, w = frame.shape[:2]
                dets = self._tracker.update(detector.detect(frame), index)
                events = self._engine.process(
                            self._tracker,
                            dets,
                            index,
                            now_s,
                            (w, h),
                            frame=frame,
                        )
            except Exception as e:  # noqa: BLE001
                self.error = f"{type(e).__name__}: {e}"
                return
            index += 1
            with self._lock:
                self._dets, self._dets_time = dets, now_s
                self._events.extend(events)