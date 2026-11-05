from PySide6.QtWidgets import QHBoxLayout

from .. import mock_data as mock
from ..widgets import Badge, Button, Card, ListRow, Page, TimelineBar, VideoView, label


class VideoAnalysisPage(Page):
    def __init__(self):
        super().__init__("Video Analysis", "Upload a recording and detect suspicious events")
        self.header.add_action(Button("Upload Video"))

        row = QHBoxLayout()
        row.setSpacing(16)

        left = Card()
        top = QHBoxLayout()
        top.addWidget(label(mock.VIDEO_FILE, "cardtitle"))
        top.addStretch(1)
        top.addWidget(Badge(f"Analyzing · {int(mock.VIDEO_PROGRESS * 100)}%", "purple"))
        left.body.addLayout(top)
        left.body.addWidget(VideoView("00:14:32", mock.SCENE_PAIR, 320), 1)
        left.body.addWidget(TimelineBar(mock.VIDEO_PROGRESS, mock.VIDEO_MARKERS))

        right = Card("Detected events")
        for i, ev in enumerate(mock.VIDEO_EVENTS):
            right.body.addWidget(ListRow(ev.event, ev.timestamp, Button("Play clip", "tonal", "sm"),
                                         mono_sub=True, last=(i == len(mock.VIDEO_EVENTS) - 1)))
        right.body.addSpacing(6)
        right.body.addWidget(Button("Save to Incident History"))
        right.body.addStretch(1)

        row.addWidget(left, 2)
        row.addWidget(right, 1)
        self.root.addLayout(row, 1)
