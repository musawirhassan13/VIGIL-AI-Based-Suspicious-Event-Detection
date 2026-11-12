from PySide6.QtWidgets import QHBoxLayout, QLineEdit

from ..camera_store import OFFLINE, ONLINE, UNKNOWN, CameraConfig, CameraStore
from ..core.capture import describe_source
from ..widgets import Badge, Button, Card, Page, Table, label, labeled
from ..workers import ProbeWorker

_STATUS_BADGE = {ONLINE: ("Online", "green"), OFFLINE: ("Offline", "red"), UNKNOWN: ("Untested", "purple")}


class CamerasPage(Page):
    def __init__(self, store: CameraStore):
        super().__init__("Camera Management", "Add and test CCTV / RTSP sources")
        self._store = store
        self._editing_id: int | None = None
        self._probe: ProbeWorker | None = None
        self._last_probe: tuple[str, bool] | None = None   # (source text, ok)

        add_btn = Button("Add Camera")
        add_btn.clicked.connect(self._new_camera)
        self.header.add_action(add_btn)

        row = QHBoxLayout()
        row.setSpacing(16)

        left = Card(margins=(18, 12, 18, 18))
        left.setMinimumHeight(406)
        self.table = Table([("Name", 11, "cell"), ("Location", 17, "cellmuted"),
                            ("Stream", 20, "monomuted"), ("Status", 12, ""), ("", 10, "")])
        left.body.addWidget(self.table)

        right = Card("Add Camera")
        right.setFixedWidth(446)
        self.name, self.location, self.url = QLineEdit(), QLineEdit(), QLineEdit()
        self.name.setPlaceholderText("e.g. CAM 01")
        self.location.setPlaceholderText("e.g. Main Gate")
        self.url.setPlaceholderText("rtsp://user:pass@ip:554/stream  or  0")
        for text, w in (("Camera name", self.name), ("Location", self.location), ("RTSP URL", self.url)):
            right.body.addWidget(labeled(text, w))

        self._test_btn = Button("Test Connection", "tonal")
        self._test_btn.clicked.connect(self._test_connection)
        self._result = Badge("", "green")
        self._result.setVisible(False)
        test = QHBoxLayout()
        test.addWidget(self._test_btn)
        test.addStretch(1)
        test.addWidget(self._result)
        right.body.addSpacing(4)
        right.body.addLayout(test)

        save = Button("Save Camera")
        save.clicked.connect(self._save)
        right.body.addWidget(save)
        right.body.addWidget(label("Tip: enter 0 (or 1, 2…) to use a webcam.", "note"))
        right.body.addStretch(1)

        row.addWidget(left, 3)
        row.addWidget(right)
        self.root.addLayout(row)
        self.root.addStretch(1)

        store.cameras_changed.connect(self._refresh_table)
        store.status_changed.connect(lambda *_: self._refresh_table())
        self._refresh_table()

    # ---- table ----
    def _refresh_table(self) -> None:
        self.table.clear()
        for cam in self._store.all():
            edit = Button("Edit", "tonal", "sm")
            edit.clicked.connect(lambda _=False, c=cam: self._edit(c))
            text, kind = _STATUS_BADGE.get(cam.status, _STATUS_BADGE[UNKNOWN])
            self.table.add_row([cam.name, cam.location, describe_source(cam.source),
                                Badge(text, kind), edit])

    # ---- form ----
    def _fill(self, name: str, location: str, source: str) -> None:
        self.name.setText(name)
        self.location.setText(location)
        self.url.setText(source)

    def _new_camera(self) -> None:
        self._editing_id = None
        self._fill("", "", "")
        self._result.setVisible(False)

    def _edit(self, cam: CameraConfig) -> None:
        self._editing_id = cam.id
        self._fill(cam.name, cam.location, cam.source)
        self._result.setVisible(False)

    def _show_result(self, text: str, kind: str) -> None:
        self._result.set_kind(kind, text)
        self._result.setVisible(True)

    # ---- test connection (off the UI thread) ----
    def _test_connection(self) -> None:
        source = self.url.text().strip()
        if not source:
            self._show_result("Enter a source", "red")
            return
        if self._probe is not None:
            return
        self._test_btn.setEnabled(False)
        self._show_result("Testing…", "purple")
        self._probe = ProbeWorker(source)
        self._probe.probe_done.connect(self._on_probe_done)
        self._probe.finished.connect(self._on_probe_finished)
        self._probe.start()

    def _on_probe_done(self, source: str, ok: bool, message: str) -> None:
        self._last_probe = (source, ok)
        self._show_result(message, "green" if ok else "red")

    def _on_probe_finished(self) -> None:
        if self._probe is not None:
            self._probe.wait()
            self._probe.deleteLater()
            self._probe = None
        self._test_btn.setEnabled(True)

    # ---- save ----
    def _save(self) -> None:
        name, location, source = (self.name.text().strip(), self.location.text().strip(),
                                  self.url.text().strip())
        if not name or not source:
            self._show_result("Name and source required", "red")
            return
        tested = self._last_probe if self._last_probe and self._last_probe[0] == source else None
        status = (ONLINE if tested[1] else OFFLINE) if tested else UNKNOWN

        if self._editing_id is None:
            self._store.add(name, location, source, status)
        else:
            self._store.update(self._editing_id, name, location, source)
            if tested:
                self._store.set_status(self._editing_id, status)
        self._editing_id = None
        self._fill("", "", "")
        self._show_result("Camera saved", "green")

    def shutdown(self) -> None:
        """Wait for a running connection test (called on window close)."""
        if self._probe is not None:
            self._probe.wait(8000)