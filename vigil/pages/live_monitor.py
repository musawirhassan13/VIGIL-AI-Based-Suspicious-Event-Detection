from PySide6.QtWidgets import QGridLayout, QHBoxLayout

from .. import mock_data as mock
from ..widgets import Badge, Button, Card, ListRow, Page, VideoView

TILES = [("CAM 01 · Main Gate", mock.SCENE_PAIR), ("CAM 02 · Lab Corridor", mock.SCENE_SINGLE),
         ("CAM 03 · Cafeteria", mock.SCENE_TWO_CALM), ("CAM 04 · Offline", [])]


class LiveMonitorPage(Page):
    def __init__(self):
        super().__init__("Live Monitor", "Continuous monitoring · 4 streams")
        self.header.add_action(Button("Stop Monitoring", "tonal"))

        row = QHBoxLayout()
        row.setSpacing(16)
        grid = QGridLayout()
        grid.setSpacing(16)
        for i, (caption, boxes) in enumerate(TILES):
            grid.addWidget(VideoView(caption, boxes, 170), i // 2, i % 2)
        for c in (0, 1):
            grid.setColumnStretch(c, 1)
        for r in (0, 1):
            grid.setRowStretch(r, 1)

        queue = Card("Alert queue")
        queue.setFixedWidth(278)
        for i, (title, sub) in enumerate(mock.ALERTS):
            queue.body.addWidget(ListRow(title, sub, Badge("Review", "red" if i == 0 else "purple"),
                                         last=(i == len(mock.ALERTS) - 1)))
        actions = QHBoxLayout()
        actions.addWidget(Button("Confirm"))
        actions.addStretch(1)
        actions.addWidget(Button("Dismiss", "tonal"))
        queue.body.addSpacing(6)
        queue.body.addLayout(actions)
        queue.body.addStretch(1)

        row.addLayout(grid, 1)
        row.addWidget(queue, 0)
        self.root.addLayout(row, 1)
