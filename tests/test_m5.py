"""M5 test: Alert queue card (Confirm / Dismiss) and live events -> IncidentStore wiring."""
import os
import sys
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from vigil import theme  # noqa: E402
from vigil.alert_queue import AlertQueueCard  # noqa: E402
from vigil.core.events import Event, EventType  # noqa: E402
from vigil.incident_store import CONFIRMED, FALSE_ALARM, PENDING, IncidentStore  # noqa: E402

app = QApplication([])
theme.apply(app)


def ev(kind, source_id="1", label="Main Gate", conf=0.8):
    return Event(type=EventType(kind), confidence=conf, source_id=source_id, source_label=label,
                 timestamp=datetime.now(), frame_index=1, video_time_s=None, detections=[])


def test_queue():
    store = IncidentStore()
    card = AlertQueueCard(store)
    card.resize(420, 400)
    card.show()
    assert card._empty.isVisible() and not card._rows
    store.add_event(ev("Sudden fall"))
    store.add_event(ev("Crowd formation", "2", "Cafeteria"))
    store.add_event(ev("Possible fight", "upload", "Video file"))      # not a live alert
    assert len(card._rows) == 2 and not card._empty.isVisible()
    btns = card._rows[0].findChildren(QPushButton)
    assert [b.text() for b in btns] == ["Confirm", "Dismiss"]
    btns[0].click()                                                    # newest = Crowd formation
    assert store.all()[1].status == CONFIRMED and len(card._rows) == 1
    card._rows[0].findChildren(QPushButton)[1].click()
    assert store.all()[2].status == FALSE_ALARM and not card._rows and card._empty.isVisible()
    assert store.all()[0].status == PENDING                            # upload incident untouched
    print("ok queue")


def test_live_event_wiring():
    from vigil.main_window import MainWindow
    w = MainWindow()
    w.live.event_detected.emit(ev("Sudden fall"))
    assert len(w.incidents.all()) == 1 and w.incidents.all()[0].status == PENDING
    w.close()
    print("ok wiring")


if __name__ == "__main__":
    test_queue()
    test_live_event_wiring()
    print("ALL OK")
