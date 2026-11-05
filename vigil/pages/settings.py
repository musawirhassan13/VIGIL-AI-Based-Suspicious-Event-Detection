from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QHBoxLayout, QLineEdit, QSlider,
                               QVBoxLayout, QWidget)

from ..widgets import Button, Card, Page, label, labeled


class LabeledSlider(QWidget):
    def __init__(self, text: str, lo: int, hi: int, value: int, fmt=lambda v: f"{v}%"):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        top = QHBoxLayout()
        top.addWidget(label(text, "fieldlabel"))
        top.addStretch(1)
        val = label(fmt(value), "mono")
        top.addWidget(val)
        lay.addLayout(top)
        s = QSlider(Qt.Horizontal)
        s.setRange(lo, hi)
        s.setValue(value)
        s.valueChanged.connect(lambda v: val.setText(fmt(v)))
        lay.addWidget(s)


def _combo(items, current=0) -> QComboBox:
    c = QComboBox()
    c.addItems(items)
    c.setCurrentIndex(current)
    return c


class SettingsPage(Page):
    def __init__(self):
        super().__init__("Settings", "Detection, alert device and evidence preferences")
        self.header.add_action(Button("Save Settings"))

        row = QHBoxLayout()
        row.setSpacing(16)
        left, right = QVBoxLayout(), QVBoxLayout()
        left.setSpacing(16)
        right.setSpacing(16)

        det = Card("Detection")
        det.body.addWidget(LabeledSlider("Alert confidence threshold", 40, 99, 70))
        det.body.addWidget(LabeledSlider("Frame sampling rate", 1, 30, 10, lambda v: f"{v} fps"))
        det.body.addSpacing(4)
        det.body.addWidget(label("Event types", "fieldlabel"))
        for name, on in (("Possible fight", True), ("Sudden fall", True),
                         ("Restricted area entry", True), ("Crowd formation", False)):
            cb = QCheckBox(name)
            cb.setChecked(on)
            det.body.addWidget(cb)
        left.addWidget(det)

        ev = Card("Evidence")
        ev.body.addWidget(labeled("Clip length", _combo(["10 seconds", "20 seconds", "30 seconds"], 1)))
        ev.body.addWidget(labeled("Keep incidents for", _combo(["30 days", "90 days", "1 year"], 1)))
        folder = QLineEdit("./evidence")
        ev.body.addWidget(labeled("Storage folder", folder))
        left.addWidget(ev)
        left.addStretch(1)

        dev = Card("ESP8266 alert device")
        dev.body.addWidget(labeled("Device address", QLineEdit("192.168.1.50")))
        for name in ("Enable LED indicator", "Enable buzzer"):
            cb = QCheckBox(name)
            cb.setChecked(True)
            dev.body.addWidget(cb)
        dev.body.addSpacing(4)
        test = QHBoxLayout()
        test.addWidget(Button("Test Device", "tonal"))
        test.addStretch(1)
        dev.body.addLayout(test)
        right.addWidget(dev)

        priv = Card("Privacy")
        priv.body.addWidget(label("VIGIL flags events for human review. It does not identify "
                                  "any person; an operator confirms every alert.", "note", wrap=True))
        right.addWidget(priv)
        right.addStretch(1)

        row.addLayout(left, 1)
        row.addLayout(right, 1)
        self.root.addLayout(row, 1)
