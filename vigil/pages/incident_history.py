from PySide6.QtWidgets import QHBoxLayout

from .. import mock_data as mock
from ..widgets import Badge, Button, Card, Page, Table, VideoView, label


class IncidentHistoryPage(Page):
    def __init__(self):
        super().__init__("Incident History", "Review, replay and verify saved events")
        self.header.add_action(Button("Export report", "tonal"))

        row = QHBoxLayout()
        row.setSpacing(16)

        left = Card(margins=(18, 12, 18, 18))
        left.setMinimumHeight(378)
        self.table = Table([("Time", 12, "mono"), ("Source", 20, "cell"), ("Event", 24, "cell"),
                            ("Conf.", 10, "mono"), ("Status", 16, "")])
        for inc in mock.INCIDENTS:
            self.table.add_row([inc.time, inc.source, inc.event, f"{inc.confidence}%",
                                Badge(inc.status, mock.STATUS_KIND[inc.status])])
        self.table.row_clicked.connect(self._on_row)
        left.body.addWidget(self.table)

        right = Card("Event clip")
        right.setFixedWidth(446)
        self.clip = VideoView("", mock.SCENE_PAIR, 220)
        right.body.addWidget(self.clip)
        actions = QHBoxLayout()
        actions.addWidget(Button("Confirm"))
        actions.addStretch(1)
        actions.addWidget(Button("False alarm", "tonal"))
        right.body.addLayout(actions)
        right.body.addWidget(label("Flagged for human review. Not an identification of any person.",
                                   "note", wrap=True))
        right.body.addStretch(1)

        row.addWidget(left, 3)
        row.addWidget(right)
        self.root.addLayout(row)
        self.root.addStretch(1)
        self._on_row(0)

    def _on_row(self, index: int) -> None:
        inc = mock.INCIDENTS[index]
        self.table.select(index)
        self.clip.set_caption(f"{inc.source} · {inc.time}")
