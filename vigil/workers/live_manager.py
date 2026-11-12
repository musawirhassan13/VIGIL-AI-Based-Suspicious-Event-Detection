"""Owns the LiveWorker threads and re-emits their signals to the UI."""
import copy
import logging
from collections.abc import Callable
from datetime import date

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage

from ..camera_store import OFFLINE, ONLINE, CameraConfig, CameraStore
from ..core.ai.event_engine import EventEngine
from ..core.ai.factory import default_detector_factory
from ..core.ai.live_pipeline import LiveAnalyzer
from ..core.events import Event
from ..settings_store import DEFAULTS, SettingsStore
from .live_worker import LiveWorker

log = logging.getLogger("vigil")

NO_CAMERAS_MSG = "No cameras configured · add one under Cameras"
# Caption suffix per worker state (online -> none)
STATE_SUFFIX = {"connecting": " · Connecting…", "reconnecting": " · Offline"}
MAX_EVENTS = 200


def _default_engine(cam: CameraConfig, cfg: dict) -> EventEngine:
    return EventEngine.from_settings(cfg, str(cam.id), cam.label)   # zones: added with the zone editor


class LiveManager(QObject):
    frame_ready = Signal(int, QImage)       # camera_id, frame
    camera_status = Signal(int, str)        # camera_id, "connecting" | "online" | "reconnecting"
    monitoring_changed = Signal(bool)       # running?
    event_detected = Signal(object)         # core.events.Event
    ai_error = Signal(int, str)             # camera_id, why detection is unavailable

    def __init__(self, store: CameraStore, settings: SettingsStore | None = None, parent=None, *,
                 ai_enabled: bool = True, detector_factory: Callable | None = None,
                 engine_factory: Callable[[CameraConfig, dict], EventEngine] | None = None):
        super().__init__(parent)
        self._store = store
        self._settings = settings
        self._ai_enabled = ai_enabled
        self._detector_factory = detector_factory
        self._engine_factory = engine_factory or _default_engine
        self._workers: dict[int, LiveWorker] = {}
        self._retiring: list[LiveWorker] = []   # stopped, waiting to finish
        self.events: list[Event] = []           # newest first; in memory until the SQLite phase

    @property
    def is_running(self) -> bool:
        return bool(self._workers)

    @property
    def active_count(self) -> int:
        return len(self._workers)

    @property
    def events_today(self) -> list[Event]:
        today = date.today()
        return [e for e in self.events if e.timestamp.date() == today]

    def start(self) -> int:
        """Start a worker for every stored camera. Returns the number started.
        Settings are read once here, so changes apply on the next start."""
        if self._workers:
            return len(self._workers)
        cfg = self._settings.all() if self._settings else copy.deepcopy(DEFAULTS)
        for cam in self._store.all():
            try:
                worker = LiveWorker(cam.id, cam.source,
                                    analyzer_factory=self._analyzer_factory(cam, cfg))
            except ValueError:
                continue
            worker.frame_ready.connect(self.frame_ready)
            worker.status_changed.connect(self._on_worker_status)
            worker.event_detected.connect(self._on_worker_event)
            worker.ai_error.connect(self._on_ai_error)
            self._workers[cam.id] = worker
            worker.start()
        if self._workers:
            self.monitoring_changed.emit(True)
        return len(self._workers)

    def stop(self) -> None:
        if not self._workers:
            return
        for worker in self._workers.values():
            self._retire(worker)
        self._workers.clear()
        self.monitoring_changed.emit(False)

    def shutdown(self, timeout_ms: int = 6000) -> None:
        """Stop everything and wait for threads (call from the window's closeEvent)."""
        self.stop()
        for worker in list(self._retiring):
            if not worker.wait(timeout_ms):
                worker.terminate()      # last resort if a read is stuck
                worker.wait(1000)
        self._retiring.clear()

    # ---- internals ----
    def _analyzer_factory(self, cam: CameraConfig, cfg: dict) -> Callable[[], LiveAnalyzer] | None:
        if not self._ai_enabled:
            return None
        detector_factory = self._detector_factory or default_detector_factory()

        def make() -> LiveAnalyzer:     # runs inside the worker thread
            return LiveAnalyzer(detector_factory, self._engine_factory(cam, cfg), sample_fps=cfg["fps"])
        return make

    def _retire(self, worker: LiveWorker) -> None:
        for sig in (worker.frame_ready, worker.status_changed, worker.event_detected, worker.ai_error):
            try:
                sig.disconnect()        # ignore stale signals from a stopping worker
            except (RuntimeError, TypeError):
                pass
        worker.stop()
        self._retiring.append(worker)
        worker.finished.connect(self._reap_finished)

    def _reap_finished(self) -> None:
        for w in [w for w in self._retiring if w.isFinished()]:
            w.wait()
            self._retiring.remove(w)
            w.deleteLater()

    def _on_worker_status(self, camera_id: int, state: str) -> None:
        if camera_id not in self._workers:
            return
        if state == "online":
            self._store.set_status(camera_id, ONLINE)
        elif state == "reconnecting":
            self._store.set_status(camera_id, OFFLINE)
        self.camera_status.emit(camera_id, state)

    def _on_worker_event(self, camera_id: int, event: Event) -> None:
        if camera_id not in self._workers:
            return
        self.events.insert(0, event)
        del self.events[MAX_EVENTS:]
        log.info("EVENT %s: %s %d%%", event.source_label, event.type.value, event.confidence_pct)
        self.event_detected.emit(event)

    def _on_ai_error(self, camera_id: int, message: str) -> None:
        if camera_id in self._workers:
            log.warning("Detection unavailable (camera %d): %s", camera_id, message)
            self.ai_error.emit(camera_id, message)