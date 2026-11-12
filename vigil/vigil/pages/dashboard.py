from datetime import date

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout

from .. import mock_data as mock
from ..camera_store import ONLINE, CameraConfig, CameraStore
from ..incident_store import CONFIRMED, FALSE_ALARM, PENDING, IncidentStore
from ..live_widgets import LiveTile, MonitoringButton
from ..widgets import Badge, Card, ListRow, Page, StatCard, label
from ..workers.live_manager import NO_CAMERAS_MSG, STATE_SUFFIX, LiveManager

RECENT_ALERTS = 4
# incident status -> (badge text, badge colour)
STATUS_BADGE = {PENDING: ("Review", "red"), CONFIRMED: ("Confirmed", "green"),
                FALSE_ALARM: ("False alarm", "purple")}


class _LiveStat(StatCard):
    def __init__(self, text: str, value: str):
        super().__init__(text, value)
        self._value = self.body.itemAt(1).widget()

    def set_value(self, value: str) -> None:
        self._value.setText(value)


class DashboardPage(Page):
    def __init__(self, store: CameraStore, manager: LiveManager,
                 incidents: IncidentStore | None = None):
        super().__init__("Dashboard", "")
        self._store, self._mgr = store, manager
        self._incidents = incidents
        self._prio: int | None = None
        self._state: dict[int, str] = {}
        self._ai_notice = ""

        self._toggle = MonitoringButton(manager)
        self._toggle.no_cameras.connect(lambda: self._refresh_header(NO_CAMERAS_MSG))
        self.header.add_action(self._toggle)

        stats = QHBoxLayout()
        stats.setSpacing(16)
        self._online_stat = _LiveStat("Cameras online", "0 / 0")
        stats.addWidget(self._online_stat, 1)
        self._alerts_stat = _LiveStat("Alerts today", "0")
        self._pending_stat = _LiveStat("Pending review", "0")
        stats.addWidget(self._alerts_stat, 1)
        stats.addWidget(self._pending_stat, 1)
        stats.addWidget(StatCard(*mock.STATS[3]), 1)             # Videos analyzed: still mock
        self.root.addLayout(stats)

        mid = QHBoxLayout()
        mid.setSpacing(16)
        cam = Card("Priority camera")
        self._tile = LiveTile(min_height=300)
        cam.body.addWidget(self._tile, 1)
        alerts = Card("Recent alerts")
        self._alerts_box = QVBoxLayout()
        self._alerts_box.setSpacing(0)
        alerts.body.addLayout(self._alerts_box)
        alerts.body.addStretch(1)
        mid.addWidget(cam, 2)
        mid.addWidget(alerts, 1)
        self.root.addLayout(mid, 1)

        status = Card(margins=(20, 14, 20, 14))
        srow = QHBoxLayout()
        srow.addWidget(label("System status", "cardtitle"))
        for name in mock.SYSTEM_STATUS:
            srow.addStretch(1)
            srow.addWidget(Badge(f"{name} · OK", "green"))
        status.body.addLayout(srow)
        self.root.addWidget(status)

        store.cameras_changed.connect(self._refresh_all)
        store.status_changed.connect(lambda *_: self._refresh_all())
        manager.frame_ready.connect(self._on_frame)
        manager.camera_status.connect(self._on_status)
        manager.monitoring_changed.connect(self._on_monitoring_changed)
        manager.ai_error.connect(self._on_ai_error)
        if incidents is not None:
            incidents.incidents_changed.connect(self._on_incidents_changed)
        else:
            manager.event_detected.connect(lambda _e: self._refresh_counts())
        self._refresh_counts()
        self._refresh_alerts()
        self._refresh_all()

    # ---- priority camera: stay on the current one while it is online, else first online, else first ----
    def _pick_priority(self) -> CameraConfig | None:
        cams = self._store.all()
        cur = self._store.get(self._prio) if self._prio is not None else None
        if cur and cur.status == ONLINE:
            return cur
        online = next((c for c in cams if c.status == ONLINE), None)
        return online or cur or (cams[0] if cams else None)

    def _refresh_all(self) -> None:
        cams = self._store.all()
        self._online_stat.set_value(f"{sum(c.status == ONLINE for c in cams)} / {len(cams)}")
        cam = self._pick_priority()
        new_id = cam.id if cam else None
        if new_id != self._prio:
            self._prio = new_id
            self._tile.clear_frame()
        self._tile.set_message("" if cam else NO_CAMERAS_MSG)
        self._update_caption()
        self._refresh_header()

    def _update_caption(self) -> None:
        cam = self._store.get(self._prio) if self._prio is not None else None
        if cam is None:
            self._tile.set_caption("")
            return
        suffix = STATE_SUFFIX.get(self._state.get(cam.id, ""), "") if self._mgr.is_running else ""
        self._tile.set_caption(cam.label + suffix)

    def _on_frame(self, camera_id: int, image) -> None:
        if camera_id == self._prio:
            self._tile.set_frame(image)

    def _on_status(self, camera_id: int, state: str) -> None:
        self._state[camera_id] = state
        if camera_id == self._prio:
            if state != "online":
                self._tile.clear_frame()
            self._update_caption()

    # ---- alert counters and the Recent alerts list ----
    def _on_incidents_changed(self) -> None:
        self._refresh_counts()
        self._refresh_alerts()

    def _refresh_counts(self) -> None:
        if self._incidents is None:
            n = str(len(self._mgr.events_today))
            self._alerts_stat.set_value(n)
            self._pending_stat.set_value(n)
            return
        today = date.today()
        incidents = self._incidents.all()
        live_today = sum(1 for i in incidents
                         if i.source_id != "upload" and i.detected_at.date() == today)
        pending = sum(1 for i in incidents if i.status == PENDING)
        self._alerts_stat.set_value(str(live_today))
        self._pending_stat.set_value(str(pending))

    def _refresh_alerts(self) -> None:
        while self._alerts_box.count():
            w = self._alerts_box.takeAt(0).widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        recent = self._incidents.all()[:RECENT_ALERTS] if self._incidents is not None else []
        if not recent:
            self._alerts_box.addWidget(label("No alerts yet", "muted"))
            return
        for k, inc in enumerate(recent):
            when = "Upload" if inc.source_id == "upload" else inc.detected_at.strftime("%H:%M")
            text, kind = STATUS_BADGE.get(inc.status, ("Review", "purple"))
            self._alerts_box.addWidget(
                ListRow(inc.type.value, f"{inc.source_label} · {when}", Badge(text, kind),
                        last=(k == len(recent) - 1)))

    def _on_ai_error(self, _camera_id: int, message: str) -> None:
        self._ai_notice = f"Detection unavailable · {message}"
        self._refresh_header()

    def _on_monitoring_changed(self, running: bool) -> None:
        self._ai_notice = ""
        if not running:
            self._state.clear()
            self._tile.clear_frame()
        self._update_caption()
        self._refresh_header()

    def _refresh_header(self, notice: str | None = None) -> None:
        if notice:
            text = notice
        elif self._mgr.is_running:
            text = "Live Camera Mode · monitoring active"
            if self._ai_notice:
                text += f" · {self._ai_notice}"
        else:
            text = "Live Camera Mode · monitoring stopped"
        self.header.subtitle.setText(text)