from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QStackedWidget, QWidget

from .camera_store import CameraStore
from .core.alert_device import AlertSender
from .device_monitor import DeviceMonitor
from .incident_store import IncidentStore
from .pages import (CamerasPage, DashboardPage, IncidentHistoryPage, LiveMonitorPage,
                    SettingsPage, VideoAnalysisPage)
from .settings_store import SettingsStore
from .sidebar import Sidebar
from .workers.live_manager import LiveManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VIGIL · AI-Based Suspicious Event Detection")

        # Keep the window inside the usable screen area (above the taskbar)
        avail = QGuiApplication.primaryScreen().availableGeometry()
        max_w, max_h = avail.width() - 20, avail.height() - 60   # 60 = title bar + borders
        self.resize(min(1415, max_w), min(840, max_h))
        self.setMinimumSize(min(1180, max_w), min(720, max_h))

        self.settings = SettingsStore()          # create once, before the pages

        # Shared services (SQLite repository replaces the stores in Phase 6)
        self.store = CameraStore(self)
        self.incidents = IncidentStore(self)
        self.live = LiveManager(self.store, self.settings)

        # Every live detection becomes a Pending incident for the operator to review
        self.live.event_detected.connect(self.incidents.add_event)
        self.alerts = AlertSender(self.settings)                     # live events -> ESP8266 LED + buzzer
        self.live.event_detected.connect(self.alerts.notify)
        self.device = DeviceMonitor(self.settings)                   # real ESP8266 connection status

        root = QWidget()
        root.setObjectName("Root")
        root.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.sidebar = Sidebar()
        self.device.status_changed.connect(lambda state, _addr: self.sidebar.set_device_status(state))
        self.stack = QStackedWidget()
        self._cameras_page = CamerasPage(self.store)
        self._video_page = VideoAnalysisPage(self.settings, self.incidents)
        # Order must match sidebar.NAV_ITEMS
        for page in (DashboardPage(self.store, self.live, self.incidents), self._cameras_page,
                     LiveMonitorPage(self.store, self.live, self.incidents), self._video_page,
                     IncidentHistoryPage(self.incidents), SettingsPage(self.settings, self.device)):
            self.stack.addWidget(page)
        self.sidebar.page_selected.connect(self.stack.setCurrentIndex)

        lay.addWidget(self.sidebar)
        lay.addWidget(self.stack, 1)
        self.setCentralWidget(root)
        self.sidebar.select(0)
        self.device.start()

    def closeEvent(self, event) -> None:
        self.live.shutdown()
        self._cameras_page.shutdown()
        self._video_page.shutdown()
        self.device.stop()
        self.device.wait(4000)
        super().closeEvent(event)