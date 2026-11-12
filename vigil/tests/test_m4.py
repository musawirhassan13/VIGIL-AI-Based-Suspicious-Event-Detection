"""M4 test: Incident History page (row select, Confirm, False alarm, Export report)."""
import csv
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication  # noqa: E402

from vigil import theme  # noqa: E402
from vigil.core.events import Event, EventType  # noqa: E402
from vigil.incident_store import CONFIRMED, FALSE_ALARM, PENDING, IncidentStore  # noqa: E402
from vigil.pages.incident_history import IncidentHistoryPage  # noqa: E402

app = QApplication([])
theme.apply(app)


def ev(kind, conf, source_id="upload", label="Video file", t=5.0):
    return Event(type=EventType(kind), confidence=conf, source_id=source_id, source_label=label,
                 timestamp=datetime.now(), frame_index=10, video_time_s=t, detections=[])


def make():
    store = IncidentStore()
    page = IncidentHistoryPage(store)
    page.resize(1200, 760)
    page.show()
    return store, page


def test_empty_state():
    store, p = make()
    assert p._empty.isVisible() and not p._export_btn.isEnabled()
    assert not p._confirm_btn.isEnabled() and not p._false_btn.isEnabled()
    print("ok empty")


def test_list_select_confirm_false_alarm():
    store, p = make()
    store.add_events([ev("Sudden fall", 0.8), ev("Crowd formation", 0.7, "1", "Main Gate", 9.0)], "/tmp/a.mp4")
    app.processEvents()
    assert len(p._table._rows) == 2 and not p._empty.isVisible() and p._export_btn.isEnabled()
    assert p._hint.isVisible() and not p._detail.isVisible()
    p._on_row_clicked(0)                                    # newest first -> Crowd formation
    assert p._detail.isVisible() and p._d_event.text() == "Crowd formation"
    assert p._fields["Source"].text() == "Main Gate" and p._fields["Confidence"].text() == "70%"
    assert p._confirm_btn.isEnabled() and p._false_btn.isEnabled()
    p._confirm_btn.click()
    assert store.all()[0].status == CONFIRMED and p._d_status.text() == CONFIRMED
    assert not p._confirm_btn.isEnabled() and p._false_btn.isEnabled()
    assert p._selected == store.all()[0].id                 # selection survives the refresh
    p._false_btn.click()
    assert store.all()[0].status == FALSE_ALARM and store.all()[1].status == PENDING
    print("ok select/confirm/false alarm")


def test_export_csv():
    store, p = make()
    store.add_events([ev("Sudden fall", 0.8), ev("Crowd formation", 0.7)], "/tmp/a.mp4")
    path = tempfile.mkdtemp() + "/report.csv"
    assert p.export_csv(path) == 2
    rows = list(csv.reader(open(path, encoding="utf-8-sig")))
    assert rows[0][0] == "ID" and len(rows) == 3 and rows[1][3] == "Sudden fall" and rows[1][5] == PENDING
    print("ok export")


if __name__ == "__main__":
    test_empty_state()
    test_list_select_confirm_false_alarm()
    test_export_csv()
    print("ALL OK")
