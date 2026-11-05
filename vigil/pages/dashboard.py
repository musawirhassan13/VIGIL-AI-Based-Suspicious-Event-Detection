from PySide6.QtWidgets import QHBoxLayout

from .. import mock_data as mock
from ..widgets import Badge, Button, Card, ListRow, Page, StatCard, VideoView, label


class DashboardPage(Page):
    def __init__(self):
        super().__init__("Dashboard", "Live Camera Mode · monitoring active")
        self.header.add_action(Button("Start Monitoring"))

        stats = QHBoxLayout()
        stats.setSpacing(16)
        for text, value in mock.STATS:
            stats.addWidget(StatCard(text, value), 1)
        self.root.addLayout(stats)

        mid = QHBoxLayout()
        mid.setSpacing(16)
        cam = Card("Priority camera")
        cam.body.addWidget(VideoView("CAM 01 · Main Gate · Possible fight", mock.SCENE_FIGHT, 300), 1)
        alerts = Card("Recent alerts")
        for i, (title, sub) in enumerate(mock.ALERTS):
            alerts.body.addWidget(ListRow(title, sub, Badge("Review", "red" if i == 0 else "purple")))
        alerts.body.addStretch(1)
        mid.addWidget(cam, 2)
        mid.addWidget(alerts, 1)
        self.root.addLayout(mid, 1)

        status = Card(margins=(20, 14, 20, 14))
        row = QHBoxLayout()
        row.addWidget(label("System status", "cardtitle"))
        for name in mock.SYSTEM_STATUS:
            row.addStretch(1)
            row.addWidget(Badge(f"{name} · OK", "green"))
        status.body.addLayout(row)
        self.root.addWidget(status)
