"""Alert queue: pending LIVE incidents with Confirm / Dismiss (M5).

Confirm -> incident status "Confirmed"; Dismiss -> "False alarm". Both go through IncidentStore,
so Incident History updates by itself. Uploaded-video incidents are not live alerts and are skipped.
"""
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from .incident_store import CONFIRMED, FALSE_ALARM, PENDING, Incident, IncidentStore
from .widgets import Button, Card, ListRow, label

MAX_VISIBLE = 6


class AlertQueueCard(Card):
    def __init__(self, incidents: IncidentStore, title: str = "Alert queue", max_visible: int = MAX_VISIBLE):
        super().__init__(title)
        self._incidents = incidents
        self._max = max_visible
        self._rows: list[ListRow] = []
        self._empty = label("No pending alerts", "muted")
        self.body.addWidget(self._empty)
        holder = QWidget()
        self._list = QVBoxLayout(holder)
        self._list.setContentsMargins(0, 0, 0, 0)
        self._list.setSpacing(0)
        self.body.addWidget(holder)
        self.body.addStretch(1)
        self._incidents.incidents_changed.connect(self.refresh)
        self.refresh()

    @property
    def pending(self) -> list[Incident]:
        return [i for i in self._incidents.all() if i.status == PENDING and i.source_id != "upload"]

    def refresh(self) -> None:
        for r in self._rows:
            r.setParent(None)
            r.deleteLater()
        self._rows.clear()
        shown = self.pending[: self._max]
        self._empty.setVisible(not shown)
        for n, inc in enumerate(shown):
            confirm = Button("Confirm", "primary", "sm")
            dismiss = Button("Dismiss", "tonal", "sm")
            confirm.clicked.connect(lambda _=False, i=inc.id: self._incidents.set_status(i, CONFIRMED))
            dismiss.clicked.connect(lambda _=False, i=inc.id: self._incidents.set_status(i, FALSE_ALARM))
            box = QWidget()
            hl = QHBoxLayout(box)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(8)
            hl.addWidget(confirm)
            hl.addWidget(dismiss)
            sub = f"{inc.source_label} · {inc.detected_at:%H:%M} · {inc.confidence_pct}%"
            row = ListRow(inc.type.value, sub, box, last=(n == len(shown) - 1))
            self._rows.append(row)
            self._list.addWidget(row)
