"""A4.2 test: LiveManager + LiveWorker + pages with a fake detector (needs PySide6 and opencv)."""
import os
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from vigil import theme  # noqa: E402
from vigil.camera_store import CameraStore  # noqa: E402
from vigil.core.ai.detector import PersonDetector  # noqa: E402
from vigil.core.ai.event_engine import EventEngine  # noqa: E402
from vigil.core.ai.rules import CrowdRule  # noqa: E402
from vigil.core.events import Detection  # noqa: E402
from vigil.pages.dashboard import DashboardPage  # noqa: E402
from vigil.workers.live_manager import LiveManager  # noqa: E402

app = QApplication([])
theme.apply(app)


def wait(cond, secs=10.0):
    t = time.time()
    while not cond() and time.time() - t < secs:
        app.processEvents()
        time.sleep(0.01)
    return cond()


class Fake(PersonDetector):
    def detect(self, frame):
        return [Detection((20, 60, 70, 200), 0.9), Detection((110, 60, 160, 200), 0.9)]


def make_video():
    path = tempfile.mkdtemp() + "/cam.mp4"
    w = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 20, (320, 240))
    for _ in range(20000):
        w.write(np.full((240, 320, 3), (40, 30, 60), np.uint8))
    w.release()
    return path


def rgb(img, x, y):
    c = QColor(img.pixel(x, y))
    return c.red(), c.green(), c.blue()


def test_events_boxes_and_counters():
    store = CameraStore()
    store.add("CAM 01", "Gate", make_video())
    mgr = LiveManager(store, detector_factory=lambda: Fake(),
                      engine_factory=lambda cam, cfg: EventEngine(
                          str(cam.id), cam.label, [CrowdRule(min_people=2, duration_s=0.5)],
                          min_confidence=0.5))
    dash = DashboardPage(store, mgr)
    frames, events = [], []
    mgr.frame_ready.connect(lambda cid, img: frames.append(img))
    mgr.event_detected.connect(events.append)
    assert mgr.start() == 1
    assert wait(lambda: len(events) == 1), "no event"
    assert events[0].source_label == "CAM 01 · Gate" and events[0].type.value == "Crowd formation"
    assert wait(lambda: any(rgb(f, 20, 100) == (245, 139, 120) for f in frames)), "no red alert boxes"
    assert any(rgb(f, 20, 100) == (196, 156, 240) for f in frames), "no purple boxes before the event"
    assert len(mgr.events) == 1 and len(mgr.events_today) == 1
    assert dash._alerts_stat._value.text() == "1" and dash._pending_stat._value.text() == "1"
    mgr.stop()
    assert wait(lambda: not mgr._retiring or all(w.isFinished() for w in mgr._retiring))
    mgr.shutdown()
    print("ok events/boxes/counters")


def test_ai_unavailable_video_keeps_playing():
    store = CameraStore()
    store.add("CAM 01", "Gate", make_video())

    def broken():
        raise ImportError("ultralytics is required")
    mgr = LiveManager(store, detector_factory=broken)
    dash = DashboardPage(store, mgr)
    frames, errors = [], []
    mgr.frame_ready.connect(lambda cid, img: frames.append(img))
    mgr.ai_error.connect(lambda cid, msg: errors.append(msg))
    mgr.start()
    assert wait(lambda: errors and len(frames) > 5)
    assert "ultralytics" in errors[0] and "Detection unavailable" in dash.header.subtitle.text()
    mgr.stop()
    mgr.shutdown()
    assert "unavailable" not in dash.header.subtitle.text()
    print("ok ai unavailable")


def test_real_main_window_builds_and_runs():
    from vigil.main_window import MainWindow
    w = MainWindow()
    w.show()
    w.store.add("CAM 01", "Gate", make_video())
    w.live.start()
    assert wait(lambda: any(True for _ in [1]) and w.live.is_running)
    wait(lambda: "Detection unavailable" in w.stack.widget(0).header.subtitle.text(), 8)   # ultralytics absent here
    w.live.shutdown()
    w.close()
    print("ok main window")


if __name__ == "__main__":
    test_events_boxes_and_counters()
    test_ai_unavailable_video_keeps_playing()
    test_real_main_window_builds_and_runs()
    print("ALL OK")
