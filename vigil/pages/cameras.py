from PySide6.QtWidgets import QHBoxLayout, QLineEdit

from .. import mock_data as mock
from ..widgets import Badge, Button, Card, Page, Table, label, labeled


class CamerasPage(Page):
    def __init__(self):
        super().__init__("Camera Management", "Add and test CCTV / RTSP sources")
        add_btn = Button("Add Camera")
        add_btn.clicked.connect(lambda: self._fill(("", "", "")))
        self.header.add_action(add_btn)

        row = QHBoxLayout()
        row.setSpacing(16)

        left = Card(margins=(18, 12, 18, 18))
        left.setMinimumHeight(406)
        self.table = Table([("Name", 11, "cell"), ("Location", 17, "cellmuted"),
                            ("Stream", 20, "monomuted"), ("Status", 12, ""), ("", 10, "")])
        for cam in mock.CAMERAS:
            edit = Button("Edit", "tonal", "sm")
            edit.clicked.connect(lambda _=False, c=cam: self._fill((c.name, c.location, c.stream)))
            self.table.add_row([cam.name, cam.location, cam.stream,
                                Badge("Online" if cam.online else "Offline",
                                      "green" if cam.online else "red"), edit])
        left.body.addWidget(self.table)

        right = Card("Add Camera")
        right.setFixedWidth(446)
        self.name, self.location, self.url = QLineEdit(), QLineEdit(), QLineEdit()
        for text, w in (("Camera name", self.name), ("Location", self.location), ("RTSP URL", self.url)):
            right.body.addWidget(labeled(text, w))
        test = QHBoxLayout()
        test.addWidget(Button("Test Connection", "tonal"))
        test.addStretch(1)
        test.addWidget(Badge("Connection OK", "green"))
        right.body.addSpacing(4)
        right.body.addLayout(test)
        right.body.addWidget(Button("Save Camera"))
        right.body.addStretch(1)
        self._fill(mock.NEW_CAMERA_DRAFT)

        row.addWidget(left, 3)
        row.addWidget(right)
        self.root.addLayout(row)
        self.root.addStretch(1)

    def _fill(self, values) -> None:
        self.name.setText(values[0])
        self.location.setText(values[1])
        self.url.setText(values[2])
