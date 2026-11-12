from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QButtonGroup, QFrame, QPushButton, QVBoxLayout

from .widgets import label

NAV_ITEMS = ["Dashboard", "Cameras", "Live Monitor", "Video Analysis", "Incident History", "Settings"]


class Sidebar(QFrame):
    page_selected = Signal(int)

    def __init__(self):
        super().__init__()
        self.setObjectName("Sidebar")
        self.setFixedWidth(220)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(13, 22, 13, 20)
        lay.setSpacing(4)

        logo = label("VIGIL", "logo")
        f = QFont(logo.font())
        f.setLetterSpacing(QFont.AbsoluteSpacing, 6)
        logo.setFont(f)
        logo.setContentsMargins(11, 0, 0, 0)
        lay.addWidget(logo)
        lay.addSpacing(26)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons = []
        for i, name in enumerate(NAV_ITEMS):
            b = QPushButton(name)
            b.setObjectName("NavItem")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, idx=i: self.page_selected.emit(idx))
            self._group.addButton(b)
            self._buttons.append(b)
            lay.addWidget(b)

        lay.addStretch(1)
        foot = QVBoxLayout()
        foot.setContentsMargins(11, 0, 0, 0)
        foot.setSpacing(2)
        foot.addWidget(label("Security Desk", "sidefoot"))
        self._device = label("ESP8266 · Checking…", "sidefoot")
        foot.addWidget(self._device)
        lay.addLayout(foot)

    def select(self, index: int) -> None:
        self._buttons[index].setChecked(True)
        self.page_selected.emit(index)

    def set_device_status(self, state: str) -> None:
        """state: 'connected' | 'disconnected' | 'no_address' (from DeviceMonitor)."""
        text, color = {"connected": ("ESP8266 · Connected", "#a9d9a0"),
                       "disconnected": ("ESP8266 · Not connected", "#f2a396")}.get(
            state, ("ESP8266 · No IP set", "#a99ba4"))
        self._device.setText(text)
        self._device.setStyleSheet(f"color: {color};")
