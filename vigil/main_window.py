from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QStackedWidget, QWidget

from .pages import (CamerasPage, DashboardPage, IncidentHistoryPage, LiveMonitorPage,
                    SettingsPage, VideoAnalysisPage)
from .sidebar import Sidebar


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VIGIL · AI-Based Suspicious Event Detection")
        self.resize(1415, 840)
        self.setMinimumSize(1180, 720)

        root = QWidget()
        root.setObjectName("Root")
        root.setAttribute(Qt.WA_StyledBackground, True)
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.sidebar = Sidebar()
        self.stack = QStackedWidget()
        # Order must match sidebar.NAV_ITEMS
        for page in (DashboardPage(), CamerasPage(), LiveMonitorPage(),
                     VideoAnalysisPage(), IncidentHistoryPage(), SettingsPage()):
            self.stack.addWidget(page)
        self.sidebar.page_selected.connect(self.stack.setCurrentIndex)

        lay.addWidget(self.sidebar)
        lay.addWidget(self.stack, 1)
        self.setCentralWidget(root)
        self.sidebar.select(0)
