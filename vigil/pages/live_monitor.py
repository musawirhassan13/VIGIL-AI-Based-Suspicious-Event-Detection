from math import ceil

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout

from ..camera_store import CameraConfig, CameraStore
from ..incident_store import CONFIRMED, FALSE_ALARM, PENDING, IncidentStore
from ..live_widgets import LiveTile, MonitoringButton
from ..widgets import Badge, Button, Card, ListRow, Page, label
from ..workers.live_manager import NO_CAMERAS_MSG, STATE_SUFFIX, LiveManager

MAX_QUEUE = 5   # rows shown in the queue; the rest are in Incident History
SELECTED_CSS = "QFrame#ListRow { background: rgba(123,72,194,0.16); }"
DISABLED_CSS = ('QPushButton[variant="primary"]:disabled { background: #2a1f2c; color: #7a6c78; }'
                'QPushButton[variant="tonal"]:disabled { background: #231a27; color: #7a6c78; }')


class _QueueRow(ListRow):
    """A ListRow you can click to select."""
    clicked = Signal()

    def mousePressEvent(self, e):
        self.clicked.emit()
        super().mousePressEvent(e)


class LiveMonitorPage(Page):
    def __init__(self, store: CameraStore, manager: LiveManager,
                 incidents: IncidentStore | None = None):
        super().__init__("Live Monitor", "")
        self._store, self._mgr = store, manager
        self._incidents = incidents
        self._sel: int | None = None            # selected incident id in the queue
        self._tiles: dict[int, LiveTile] = {}
        self._state: dict[int, str] = {}
        self._ai_notice = ""

        self._toggle = MonitoringButton(manager)
        self._toggle.no_cameras.connect(lambda: self._refresh_header(NO_CAMERAS_MSG))
        self.header.add_action(self._toggle)

        row = QHBoxLayout()
        row.setSpacing(16)
        self._grid = QGridLayout()
        self._grid.setSpacing(16)
        row.addLayout(self._grid, 1)
        row.addWidget(self._build_queue(), 0)
        self.root.addLayout(row, 1)

        store.cameras_changed.connect(self._rebuild)
        manager.frame_ready.connect(self._on_frame)
        manager.camera_status.connect(self._on_status)
        manager.monitoring_changed.connect(self._on_monitoring_changed)
        manager.ai_error.connect(self._on_ai_error)
        if incidents is not None:
            incidents.incidents_changed.connect(self._refresh_queue)
        self._rebuild()
        self._refresh_queue()

    # ---- alert queue (real pending alerts from live cameras) ----
    def _build_queue(self) -> Card:
        queue = Card("Alert queue")
        queue.setFixedWidth(278)
        self._queue_box = QVBoxLayout()
        self._queue_box.setSpacing(0)
        queue.body.addLayout(self._queue_box)
        self._more = label("", "muted")
        self._more.setVisible(False)
        queue.body.addWidget(self._more)
        actions = QHBoxLayout()
        self._confirm_btn = Button("Confirm")
        self._dismiss_btn = Button("Dismiss", "tonal")
        for b in (self._confirm_btn, self._dismiss_btn):
            b.setStyleSheet(DISABLED_CSS)
            b.setEnabled(False)
        self._confirm_btn.clicked.connect(lambda: self._act(CONFIRMED))
        self._dismiss_btn.clicked.connect(lambda: self._act(FALSE_ALARM))
        actions.addWidget(self._confirm_btn)
        actions.addStretch(1)
        actions.addWidget(self._dismiss_btn)
        queue.body.addSpacing(6)
        queue.body.addLayout(actions)
        queue.body.addStretch(1)
        return queue

    def _pending_live(self):
        if self._incidents is None:
            return []
        return [i for i in self._incidents.all()
                if i.status == PENDING and i.source_id != "upload"]

    def _refresh_queue(self) -> None:
        while self._queue_box.count():
            w = self._queue_box.takeAt(0).widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        pending = self._pending_live()               # newest first
        ids = [i.id for i in pending]
        if self._sel not in ids:
            self._sel = ids[0] if ids else None
        shown = pending[:MAX_QUEUE]
        if not shown:
            self._queue_box.addWidget(label("No pending alerts", "muted"))
        for k, inc in enumerate(shown):
            qrow = _QueueRow(inc.type.value,
                             f"{inc.source_label} · {inc.detected_at.strftime('%H:%M')}",
                             Badge("Review", "red"), last=(k == len(shown) - 1))
            if inc.id == self._sel:
                qrow.setStyleSheet(SELECTED_CSS)
            qrow.clicked.connect(lambda i=inc.id: self._select(i))
            self._queue_box.addWidget(qrow)
        extra = len(pending) - len(shown)
        self._more.setText(f"+{extra} more · see Incident History")
        self._more.setVisible(extra > 0)
        has_sel = self._sel is not None
        self._confirm_btn.setEnabled(has_sel)
        self._dismiss_btn.setEnabled(has_sel)

    def _select(self, incident_id: int) -> None:
        self._sel = incident_id
        QTimer.singleShot(0, self._refresh_queue)    # rebuild after the click has finished

    def _act(self, status: str) -> None:
        if self._incidents is not None and self._sel is not None:
            self._incidents.set_status(self._sel, status)   # emits incidents_changed -> refresh

    # ---- grid ----
    def _caption(self, cam: CameraConfig) -> str:
        suffix = STATE_SUFFIX.get(self._state.get(cam.id, ""), "") if self._mgr.is_running else ""
        return cam.label + suffix

    def _rebuild(self) -> None:
        while self._grid.count():
            w = self._grid.takeAt(0).widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._tiles.clear()
        for i in range(8):
            self._grid.setRowStretch(i, 0)
            self._grid.setColumnStretch(i, 0)
        cams = self._store.all()
        if not cams:
            empty = LiveTile(min_height=170)
            empty.set_message(NO_CAMERAS_MSG)
            self._grid.addWidget(empty, 0, 0)
            self._grid.setRowStretch(0, 1)
            self._grid.setColumnStretch(0, 1)
        else:
            cols = 1 if len(cams) == 1 else 2
            for i, cam in enumerate(cams):
                tile = LiveTile(self._caption(cam), 170)
                self._tiles[cam.id] = tile
                self._grid.addWidget(tile, i // cols, i % cols)
            for c in range(cols):
                self._grid.setColumnStretch(c, 1)
            for r in range(ceil(len(cams) / cols)):
                self._grid.setRowStretch(r, 1)
        self._refresh_header()

    # ---- live signals ----
    def _on_frame(self, camera_id: int, image) -> None:
        tile = self._tiles.get(camera_id)
        if tile is not None:
            tile.set_frame(image)

    def _on_status(self, camera_id: int, state: str) -> None:
        self._state[camera_id] = state
        tile, cam = self._tiles.get(camera_id), self._store.get(camera_id)
        if tile is None or cam is None:
            return
        tile.set_caption(self._caption(cam))
        if state != "online":
            tile.clear_frame()

    def _on_ai_error(self, _camera_id: int, message: str) -> None:
        self._ai_notice = f"Detection unavailable · {message}"
        self._refresh_header()

    def _on_monitoring_changed(self, running: bool) -> None:
        self._ai_notice = ""
        if not running:
            self._state.clear()
            for cid, tile in self._tiles.items():
                tile.clear_frame()
                cam = self._store.get(cid)
                if cam:
                    tile.set_caption(self._caption(cam))
        self._refresh_header()

    def _refresh_header(self, notice: str | None = None) -> None:
        if notice:
            text = notice
        elif self._mgr.is_running:
            n = self._mgr.active_count
            text = f"Continuous monitoring · {n} stream{'s' if n != 1 else ''}"
            if self._ai_notice:
                text += f" · {self._ai_notice}"
        else:
            text = "Monitoring stopped · press Start Monitoring"
        self.header.subtitle.setText(text)