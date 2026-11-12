import re
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QHBoxLayout, QLineEdit,
                               QScrollArea, QSizePolicy, QSlider, QVBoxLayout, QWidget)

from ..core.alert_device import send_alert
from ..settings_store import SettingsStore
from ..widgets import Badge, Button, Card, Page, label, labeled

CLIP_CHOICES = [("10 seconds", 10), ("20 seconds", 20), ("30 seconds", 30)]
RETENTION_CHOICES = [("30 days", 30), ("90 days", 90), ("1 year", 365)]


def parse_address(text: str) -> tuple[str, int] | None:
    """'host' or 'host:port' -> (host, port); None if invalid."""
    host, _, port = text.strip().partition(":")
    if not host or not re.fullmatch(r"[A-Za-z0-9.\-]+", host):
        return None
    if port:
        if not port.isdigit() or not 0 < int(port) < 65536:
            return None
        return host, int(port)
    return host, 80


class _ReachWorker(QThread):
    """Sends a real test alert to the ESP8266 (LED + buzzer), kept off the UI thread."""
    done = Signal(bool, str)

    def __init__(self, address: str, led: bool, buzzer: bool):
        super().__init__()
        self._address, self._led, self._buzzer = address, led, buzzer

    def run(self) -> None:
        ok, message = send_alert(self._address, self._led, self._buzzer)
        self.done.emit(ok, message)


class LabeledSlider(QWidget):
    def __init__(self, text: str, lo: int, hi: int, value: int, fmt=lambda v: f"{v}%"):
        super().__init__()
        self._fmt = fmt
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        name = label(text, "fieldlabel")
        self._val = label(fmt(value), "mono")
        # Give the text row real height so the letters are never cut off
        name.setMinimumHeight(22)
        self._val.setMinimumHeight(22)
        name.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self._val.setAlignment(Qt.AlignVCenter | Qt.AlignRight)

        top = QHBoxLayout()
        top.addWidget(name)
        top.addStretch(1)
        top.addWidget(self._val)
        lay.addLayout(top)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(lo, hi)
        self.slider.setValue(value)
        # The theme's slider handle is 16px tall; without this the slider is squeezed to 6px
        self.slider.setFixedHeight(24)
        self.slider.valueChanged.connect(lambda v: self._val.setText(self._fmt(v)))
        lay.addWidget(self.slider)

    def value(self) -> int:
        return self.slider.value()

    def set_value(self, v: int) -> None:
        self.slider.setValue(v)


def _combo(choices) -> QComboBox:
    c = QComboBox()
    for text, data in choices:
        c.addItem(text, data)
    return c


class SettingsPage(Page):
    def __init__(self, store: SettingsStore, monitor=None):
        super().__init__("Settings", "Detection, alert device and evidence preferences")
        self.root.setContentsMargins(32, 20, 32, 12)   # less empty space around the page
        self.root.setSpacing(10)
        self._store = store
        self._monitor = monitor
        self._reach: _ReachWorker | None = None

        self._status = Badge("", "green")
        self._status.setVisible(False)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(lambda: self._status.setVisible(False))
        save = Button("Save Settings")
        save.clicked.connect(self._save)
        self.header.add_action(self._status)
        self.header.add_action(save)

        content = QWidget()
        content.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)   # scroll instead of squash
        row = QHBoxLayout(content)
        row.setContentsMargins(0, 0, 10, 40)   # right gap for the scrollbar, bottom gap below last field
        row.setSpacing(16)
        left, right = QVBoxLayout(), QVBoxLayout()
        left.setSpacing(16)
        right.setSpacing(16)

        det = Card("Detection")
        self.conf = LabeledSlider("Alert confidence threshold", 40, 99, 70)
        self.fps = LabeledSlider("Frame sampling rate", 1, 30, 10, lambda v: f"{v} fps")
        det.body.addWidget(self.conf)
        det.body.addWidget(self.fps)
        det.body.addSpacing(4)
        det.body.addWidget(label("Event types", "fieldlabel"))
        self.event_boxes: dict[str, QCheckBox] = {}
        for name in store.get("events"):
            cb = QCheckBox(name)
            self.event_boxes[name] = cb
            det.body.addWidget(cb)
        left.addWidget(det)

        ev = Card("Evidence")
        self.clip = _combo(CLIP_CHOICES)
        self.retention = _combo(RETENTION_CHOICES)
        self.folder = QLineEdit()
        ev.body.addWidget(labeled("Clip length", self.clip))
        ev.body.addWidget(labeled("Keep incidents for", self.retention))
        ev.body.addWidget(labeled("Storage folder", self.folder))
        left.addWidget(ev)
        left.addStretch(1)

        dev = Card("ESP8266 alert device")
        self.addr = QLineEdit()
        self.addr.setPlaceholderText("192.168.1.50  or  192.168.1.50:80")
        dev.body.addWidget(labeled("Device address", self.addr))
        self._conn = Badge("", "green")
        self._conn.setVisible(False)
        conn_row = QHBoxLayout()
        conn_row.addWidget(self._conn)
        conn_row.addStretch(1)
        dev.body.addLayout(conn_row)
        self.led = QCheckBox("Enable LED indicator")
        self.buzzer = QCheckBox("Enable buzzer")
        dev.body.addWidget(self.led)
        dev.body.addWidget(self.buzzer)
        dev.body.addSpacing(4)
        self._test_btn = Button("Test Device", "tonal")
        self._test_btn.clicked.connect(self._test_device)
        self._test_result = Badge("", "green")
        self._test_result.setVisible(False)
        test = QHBoxLayout()
        test.addWidget(self._test_btn)
        test.addStretch(1)
        test.addWidget(self._test_result)
        dev.body.addLayout(test)
        right.addWidget(dev)

        priv = Card("Privacy")
        priv.body.addWidget(label("VIGIL flags events for human review. It does not identify "
                                  "any person; an operator confirms every alert.", "note", wrap=True))
        right.addWidget(priv)
        right.addStretch(1)

        row.addLayout(left, 1)
        row.addLayout(right, 1)

        # Scroll area: if the window is short, the page scrolls instead of squashing/cutting
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
            "QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }"
            "QScrollBar::handle:vertical { background: #4b3b47; border-radius: 5px; min-height: 30px; }"
            "QScrollBar::handle:vertical:hover { background: #6b5667; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }")
        scroll.setWidget(content)
        self.root.addWidget(scroll, 1)
        self._load_from_store()
        if monitor is not None:
            monitor.status_changed.connect(self._on_device_state)
            self._on_device_state(monitor.state, "")

    # ---- store <-> widgets ----
    def _load_from_store(self) -> None:
        s = self._store.all()
        self.conf.set_value(s["confidence"])
        self.fps.set_value(s["fps"])
        for name, cb in self.event_boxes.items():
            cb.setChecked(s["events"].get(name, False))
        for combo, key in ((self.clip, "clip_seconds"), (self.retention, "retention_days")):
            i = combo.findData(s[key])
            combo.setCurrentIndex(i if i >= 0 else 0)
        self.folder.setText(s["storage_dir"])
        self.addr.setText(s["device_address"])
        self.led.setChecked(s["led"])
        self.buzzer.setChecked(s["buzzer"])

    def _flash(self, text: str, kind: str) -> None:
        self._status.set_kind(kind, text)
        self._status.setVisible(True)
        self._hide_timer.start(3000)

    # ---- Save Settings ----
    def _save(self) -> None:
        addr = self.addr.text().strip()
        if parse_address(addr) is None:
            self._flash("Invalid device address", "red")
            return
        folder = self.folder.text().strip()
        if not folder:
            self._flash("Storage folder required", "red")
            return
        try:
            Path(folder).expanduser().mkdir(parents=True, exist_ok=True)
        except OSError:
            self._flash("Can't create storage folder", "red")
            return
        values = {
            "confidence": self.conf.value(),
            "fps": self.fps.value(),
            "events": {n: cb.isChecked() for n, cb in self.event_boxes.items()},
            "clip_seconds": self.clip.currentData(),
            "retention_days": self.retention.currentData(),
            "storage_dir": folder,
            "device_address": addr,
            "led": self.led.isChecked(),
            "buzzer": self.buzzer.isChecked(),
        }
        try:
            self._store.update(values)
        except OSError:
            self._flash("Couldn't write settings file", "red")
            return
        if self._monitor is not None:
            self._monitor.refresh()                      # check the (new) device address right away
        self._flash("Settings saved", "green")

    # ---- Test Device: sends a real alert so you can see / hear it ----
    def _test_device(self) -> None:
        if self._reach is not None:
            return
        parsed = parse_address(self.addr.text())
        if parsed is None:
            self._show_test("Invalid address", "red")
            return
        self._test_btn.setEnabled(False)
        self._show_test("Testing…", "purple")
        self._reach = _ReachWorker(self.addr.text().strip(), self.led.isChecked(), self.buzzer.isChecked())
        self._reach.done.connect(lambda ok, msg: self._show_test(msg, "green" if ok else "red"))
        self._reach.finished.connect(self._on_reach_finished)
        self._reach.start()

    def _on_device_state(self, state: str, _address: str) -> None:
        if state == "connected":
            self._conn.set_kind("green", "Connected")
        elif state == "disconnected":
            self._conn.set_kind("red", "Not connected")
        self._conn.setVisible(state in ("connected", "disconnected"))

    def _show_test(self, text: str, kind: str) -> None:
        self._test_result.set_kind(kind, text)
        self._test_result.setVisible(True)

    def _on_reach_finished(self) -> None:
        if self._reach is not None:
            self._reach.wait()
            self._reach.deleteLater()
            self._reach = None
        self._test_btn.setEnabled(True)

    def shutdown(self) -> None:
        """Wait for a running device test (call on window close)."""
        if self._reach is not None:
            self._reach.wait(3000)