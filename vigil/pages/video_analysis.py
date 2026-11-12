from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from ..analysis_widgets import AnalysisTimeline, ClipPlayer
from ..core.ai.video_scan import video_info
from ..core.events import Event
from ..incident_store import IncidentStore
from ..live_widgets import LiveTile
from ..settings_store import SettingsStore
from ..widgets import Badge, Button, Card, ListRow, Page, label, set_props
from ..workers.analysis_worker import AnalysisWorker

FILE_FILTER = "Videos (*.mp4 *.avi)"
CLIP_BEFORE_S, CLIP_AFTER_S = 3.0, 5.0       # "Play clip" window around an event
IDLE_MESSAGE = "Upload a recording to detect suspicious events"
IDLE_SUBTITLE = "Upload a recording and detect suspicious events"
DISABLED_CSS = 'QPushButton[variant="primary"]:disabled { background: #2a1f2c; color: #7a6c78; }'


def fmt_time(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


class VideoAnalysisPage(Page):
    def __init__(self, settings, incidents, worker_factory=None, alert_sender=None):
        super().__init__("Video Analysis", IDLE_SUBTITLE)
        self.root.setContentsMargins(32, 24, 32, 70)   # bottom 70 lifts the cards up
        self._settings, self._incidents = settings, incidents
        self._alert_sender = alert_sender
        self._worker_factory = worker_factory or AnalysisWorker
        self._worker: AnalysisWorker | None = None
        self._retiring: list[AnalysisWorker] = []
        self._path: str | None = None
        self._duration = 1.0
        self._events: list[Event] = []
        self._saved = 0
        self._rows: list[ListRow] = []
        self._clip_active = False
        self._player = ClipPlayer(self)
        self._player.frame.connect(self._on_clip_frame)
        self._player.finished.connect(self._on_clip_finished)

        upload = Button("Upload Video")
        upload.clicked.connect(self._choose_file)
        self.header.add_action(upload)

        row = QHBoxLayout()
        row.setSpacing(16)

        left = Card()
        top = QHBoxLayout()
        self._title = label("No video selected", "cardtitle")
        top.addWidget(self._title)
        top.addStretch(1)
        self._badge = Badge("Idle", "purple")
        self._badge.setVisible(False)
        top.addWidget(self._badge)
        left.body.addLayout(top)
        self._tile = LiveTile(min_height=320)
        self._tile.set_message(IDLE_MESSAGE)
        left.body.addWidget(self._tile, 1)
        self._timeline = AnalysisTimeline()
        left.body.addWidget(self._timeline)

        right = Card("Detected events")
        self._empty = label("No events detected yet", "muted")
        right.body.addWidget(self._empty)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }"
                             "QScrollArea > QWidget > QWidget { background: transparent; }")
        inner = QWidget()
        self._list = QVBoxLayout(inner)
        self._list.setContentsMargins(0, 0, 0, 0)
        self._list.setSpacing(0)
        self._list.addStretch(1)
        scroll.setWidget(inner)
        right.body.addWidget(scroll, 1)
        self._save_btn = Button("Save to Incident History")
        self._save_btn.setStyleSheet(DISABLED_CSS)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save)
        right.body.addWidget(self._save_btn)

        row.addWidget(left, 2)
        row.addWidget(right, 1)
        self.root.addLayout(row, 1)

    # ---- choosing and starting ----
    def _choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Upload Video", "", FILE_FILTER)
        if path:
            self.analyze(path)

    def analyze(self, path: str) -> None:
        """Start analysing a video file (cancels any analysis already running)."""
        self._retire_worker()
        self._player.stop()
        self._clip_active = False
        self._path, self._events, self._saved = path, [], 0
        for r in self._rows:
            r.setParent(None)
            r.deleteLater()
        self._rows.clear()
        self._empty.setVisible(True)
        self._update_save_button()
        self._title.setText(Path(path).name)
        self._timeline.set_state(0.0, [])
        self._tile.clear_frame()
        self._tile.set_caption("")
        self._tile.set_message("")
        self._set_badge("Analyzing · 0%", "purple")
        self.header.subtitle.setText(IDLE_SUBTITLE)
        try:
            self._duration = video_info(path).duration_s or 1.0
        except Exception as e:  # noqa: BLE001
            self._on_failed(f"{type(e).__name__}: {e}")
            return

        worker = self._worker_factory(path, self._settings.all())

        def current(fn):
            # drop signals already queued by a retired/cancelled worker
            return lambda *a, w=worker: fn(*a) if w is self._worker else None

        worker.progress.connect(current(self._on_progress))
        worker.preview.connect(current(self._on_preview))
        worker.event_found.connect(current(self._on_event))
        worker.failed.connect(current(self._on_failed))
        worker.done.connect(current(self._on_done))
        worker.finished.connect(self._reap)
        self._worker = worker
        worker.start()

    # ---- worker signals ----
    def _on_progress(self, pct: int) -> None:
        self._set_badge(f"Analyzing · {pct}%", "purple")
        self._timeline.set_state(pct / 100, self._markers())

    def _on_preview(self, image, t: float) -> None:
        if not self._clip_active:
            self._tile.set_frame(image)
            self._tile.set_caption(fmt_time(t))

    def _on_event(self, ev: Event) -> None:
        self._events.append(ev)
        self._incidents.add_event(ev, self._path)    # NEW: save as an alert right away
        if self._alert_sender is not None:
            self._alert_sender.notify(ev)
        self._saved = len(self._events)              # NEW: mark it as already saved
        self._empty.setVisible(False)
        if self._rows:
            set_props(self._rows[-1], last=False)
        play = Button("Play clip", "tonal", "sm")
        play.clicked.connect(lambda _=False, e=ev: self._play_clip(e))
        row = ListRow(ev.type.value, fmt_time(ev.video_time_s or 0.0), play, mono_sub=True, last=True)
        self._rows.append(row)
        self._list.insertWidget(self._list.count() - 1, row)
        self._timeline.set_state(self._timeline._progress, self._markers())
        self._update_save_button()

    def _on_failed(self, message: str) -> None:
        self._set_badge("Failed", "red")
        self._tile.set_message("Analysis could not run")
        self.header.subtitle.setText(f"Analysis failed · {message}")

    def _on_done(self, cancelled: bool) -> None:
        if cancelled:
            self._set_badge("Stopped", "purple")
            return
        n = len(self._events)
        self._set_badge(f"Done · {n} event{'s' if n != 1 else ''}", "green")
        self._timeline.set_state(1.0, self._markers())

    def _markers(self) -> list[float]:
        return [(e.video_time_s or 0.0) / self._duration for e in self._events]

    # ---- Play clip ----
    def _play_clip(self, ev: Event) -> None:
        if not self._path:
            return
        t = ev.video_time_s or 0.0
        self._clip_active = self._player.play(self._path, max(0.0, t - CLIP_BEFORE_S), t + CLIP_AFTER_S)

    def _on_clip_frame(self, image, t: float) -> None:
        self._tile.set_frame(image)
        self._tile.set_caption(fmt_time(t))

    def _on_clip_finished(self) -> None:
        self._clip_active = False

    # ---- Save to Incident History ----
    def _update_save_button(self) -> None:
        unsaved = len(self._events) - self._saved
        if unsaved > 0:
            self._save_btn.setText("Save to Incident History")
            self._save_btn.setEnabled(True)
        else:
            self._save_btn.setText("Saved ✓" if self._saved else "Save to Incident History")
            self._save_btn.setEnabled(False)

    def _save(self) -> None:
        new = self._events[self._saved:]
        if not new:
            return
        self._incidents.add_events(new, self._path)
        self._saved = len(self._events)
        self._update_save_button()
        self.header.subtitle.setText(f"Saved {len(new)} event{'s' if len(new) != 1 else ''} to Incident History")

    # ---- helpers / lifecycle ----
    def _set_badge(self, text: str, kind: str) -> None:
        self._badge.set_kind(kind, text)
        self._badge.setVisible(True)

    def _retire_worker(self) -> None:
        w = self._worker
        if w is None:
            return
        for sig in (w.progress, w.preview, w.event_found, w.failed, w.done):
            try:
                sig.disconnect()        # ignore anything a cancelled worker still sends
            except (RuntimeError, TypeError):
                pass
        w.stop()
        self._retiring.append(w)
        self._worker = None

    def _reap(self) -> None:
        for w in [w for w in [self._worker, *self._retiring] if w is not None and w.isFinished()]:
            w.wait()
            if w in self._retiring:
                self._retiring.remove(w)
            else:
                self._worker = None
            w.deleteLater()

    def shutdown(self, timeout_ms: int = 8000) -> None:
        """Cancel the running analysis and wait for threads (call from the window's closeEvent)."""
        self._player.stop()
        self._retire_worker()
        for w in list(self._retiring):
            if not w.wait(timeout_ms):
                w.terminate()
                w.wait(1000)
        self._retiring.clear()