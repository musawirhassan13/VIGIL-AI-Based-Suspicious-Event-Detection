"""Incident History: real incidents from IncidentStore, row select, Confirm, False alarm, Export report."""
import csv

from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from ..incident_store import CONFIRMED, FALSE_ALARM, PENDING, Incident, IncidentStore
from ..widgets import Badge, Button, Card, Page, Table, label
from .video_analysis import fmt_time

STATUS_KIND = {PENDING: "red", CONFIRMED: "green", FALSE_ALARM: "purple"}
TIME_FORMAT = "%d %b %H:%M:%S"
REPORT_COLUMNS = ["ID", "Detected at", "Source", "Event", "Confidence %", "Status", "Video file", "Video time"]
DISABLED_CSS = ('QPushButton[variant="primary"]:disabled { background: #2a1f2c; color: #7a6c78; }'
                'QPushButton[variant="tonal"]:disabled { background: #231a27; color: #7a6c78; }')
NO_SELECTION = "Select an incident to review it"


class IncidentHistoryPage(Page):
    def __init__(self, incidents: IncidentStore):
        super().__init__("Incident History", "Review detected incidents and confirm or dismiss them")
        self._incidents = incidents
        self._shown: list[int] = []          # incident id per table row
        self._selected: int | None = None

        self._export_btn = Button("Export report", "tonal")
        self._export_btn.clicked.connect(self._export)
        self.header.add_action(self._export_btn)

        row = QHBoxLayout()
        row.setSpacing(16)

        # ---- left: table ----
        left = Card()
        self._empty = label("No incidents yet · analyse a video or start monitoring", "muted")
        left.body.addWidget(self._empty)
        self._table = Table([("Time", 2, "cellmuted"), ("Source", 2, "cell"), ("Event", 3, "cell"),
                             ("Conf.", 1, "cell"), ("Status", 2, "cell")])
        self._table.row_clicked.connect(self._on_row_clicked)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }"
                             "QScrollArea > QWidget > QWidget { background: transparent; }")
        scroll.setWidget(self._table)
        left.body.addWidget(scroll, 1)

        # ---- right: detail ----
        right = Card("Incident details")
        self._hint = label(NO_SELECTION, "muted")
        right.body.addWidget(self._hint)
        self._detail = QWidget()
        dl = QVBoxLayout(self._detail)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(10)
        self._d_event = label("", "cardtitle")
        dl.addWidget(self._d_event)
        self._d_status = Badge(PENDING, "red")
        dl.addWidget(self._d_status)
        self._fields: dict[str, QLabel] = {}
        for key in ("Source", "Detected at", "Confidence", "Video file", "Video time"):
            dl.addWidget(label(key, "fieldlabel"))
            val = label("", "mono", wrap=True)
            self._fields[key] = val
            dl.addWidget(val)
        right.body.addWidget(self._detail)
        right.body.addStretch(1)
        self._confirm_btn = Button("Confirm")
        self._false_btn = Button("False alarm", "tonal")
        for b in (self._confirm_btn, self._false_btn):
            b.setStyleSheet(DISABLED_CSS)
            right.body.addWidget(b)
        self._confirm_btn.clicked.connect(lambda: self._set_status(CONFIRMED))
        self._false_btn.clicked.connect(lambda: self._set_status(FALSE_ALARM))

        row.addWidget(left, 2)
        row.addWidget(right, 1)
        self.root.addLayout(row, 1)

        self._incidents.incidents_changed.connect(self._refresh)
        self._refresh()

    # ---- list ----
    def _refresh(self) -> None:
        incidents = self._incidents.all()                       # newest first
        self._table.clear()
        self._shown = [i.id for i in incidents]
        for inc in incidents:
            self._table.add_row([inc.detected_at.strftime("%H:%M") if inc.source_id != "upload" else "Upload",
                                 inc.source_label, inc.type.value, f"{inc.confidence_pct}%",
                                 Badge(inc.status, STATUS_KIND.get(inc.status, "purple"))])
        self._empty.setVisible(not incidents)
        self._export_btn.setEnabled(bool(incidents))
        if self._selected not in self._shown:
            self._selected = None
        if self._selected is not None:
            self._table.select(self._shown.index(self._selected))
        self._show_detail(self._incidents.get(self._selected) if self._selected is not None else None)

    def _on_row_clicked(self, index: int) -> None:
        if 0 <= index < len(self._shown):
            self._selected = self._shown[index]
            self._table.select(index)
            self._show_detail(self._incidents.get(self._selected))

    # ---- detail ----
    def _show_detail(self, inc: Incident | None) -> None:
        self._detail.setVisible(inc is not None)
        self._hint.setVisible(inc is None)
        self._confirm_btn.setEnabled(inc is not None and inc.status != CONFIRMED)
        self._false_btn.setEnabled(inc is not None and inc.status != FALSE_ALARM)
        if inc is None:
            return
        self._d_event.setText(inc.type.value)
        self._d_status.set_kind(STATUS_KIND.get(inc.status, "purple"), inc.status)
        self._fields["Source"].setText(inc.source_label)
        self._fields["Detected at"].setText(inc.detected_at.strftime(TIME_FORMAT))
        self._fields["Confidence"].setText(f"{inc.confidence_pct}%")
        self._fields["Video file"].setText(inc.video_path or "—")
        self._fields["Video time"].setText(fmt_time(inc.video_time_s) if inc.video_time_s is not None else "—")

    def _set_status(self, status: str) -> None:
        if self._selected is not None:
            self._incidents.set_status(self._selected, status)   # emits incidents_changed -> _refresh

    # ---- export ----
    def export_csv(self, path: str) -> int:
        """Write every incident to a CSV file (opens in Excel). Returns the number of rows written."""
        incidents = list(reversed(self._incidents.all()))        # oldest first in the report
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(REPORT_COLUMNS)
            for i in incidents:
                w.writerow([i.id, i.detected_at.strftime("%Y-%m-%d %H:%M:%S"), i.source_label, i.type.value,
                            i.confidence_pct, i.status, i.video_path or "",
                            fmt_time(i.video_time_s) if i.video_time_s is not None else ""])
        return len(incidents)

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export report", "incident_report.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            n = self.export_csv(path)
        except OSError as e:
            self.header.subtitle.setText(f"Export failed · {e}")
            return
        self.header.subtitle.setText(f"Exported {n} incident{'s' if n != 1 else ''} to {path}")