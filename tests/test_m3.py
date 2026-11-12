"""M3 test: Video Analysis page, AnalysisWorker, IncidentStore (fake detector, no YOLO)."""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from vigil import theme  # noqa: E402
from vigil.core.ai.detector import PersonDetector  # noqa: E402
from vigil.core.ai.event_engine import EventEngine  # noqa: E402
from vigil.core.ai.rules import CrowdRule  # noqa: E402
from vigil.core.events import Detection  # noqa: E402
from vigil.incident_store import PENDING, IncidentStore  # noqa: E402
from vigil.pages.video_analysis import VideoAnalysisPage, fmt_time  # noqa: E402
from vigil.settings_store import SettingsStore  # noqa: E402
from vigil.workers.analysis_worker import AnalysisWorker  # noqa: E402

app = QApplication([])
theme.apply(app)


def wait(cond, secs=15.0):
    t = time.time()
    while not cond() and time.time() - t < secs:
        app.processEvents()
        time.sleep(0.01)
    return cond()


class Fake(PersonDetector):
    def detect(self, frame):
        return [Detection((20, 60, 70, 200), 0.9), Detection((110, 60, 160, 200), 0.9)]


def make_video(seconds=10, fps=20):
    path = tempfile.mkdtemp() + "/clip.mp4"
    w = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (320, 240))
    for i in range(seconds * fps):
        f = np.full((240, 320, 3), (40, 30, 60), np.uint8)
        cv2.putText(f, str(i), (200, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        w.write(f)
    w.release()
    return path


def engine(cfg):
    return EventEngine("upload", "Video file", [CrowdRule(min_people=2, duration_s=1.0, cooldown_s=3.0)],
                       min_confidence=0.5)


def page(detector_factory=lambda: Fake()):
    settings = SettingsStore(Path(tempfile.mkdtemp()) / "s.json")
    incidents = IncidentStore()
    p = VideoAnalysisPage(settings, incidents,
                          worker_factory=lambda path, cfg: AnalysisWorker(path, cfg, detector_factory, engine))
    p.resize(1200, 760)
    p.show()
    return p, incidents


def test_fmt_time():
    assert fmt_time(0) == "00:00:00" and fmt_time(872.4) == "00:14:32" and fmt_time(3725) == "01:02:05"


def test_full_flow():
    p, incidents = page()
    assert not p._save_btn.isEnabled() and p._empty.isVisible()
    video = make_video()
    p.analyze(video)
    assert wait(lambda: p._badge.text().startswith("Done"))
    assert p._badge.text() == "Done · 3 events", p._badge.text()
    assert len(p._rows) == 3 and not p._empty.isVisible() and p._title.text() == "clip.mp4"
    assert len(p._timeline._markers) == 3 and p._timeline._progress == 1.0
    assert all(0 < m < 1 for m in p._timeline._markers) and p._tile.has_frame
    assert p._save_btn.isEnabled()
    first_row_btn = p._rows[0].findChildren(type(p._save_btn))[0]
    first_row_btn.click()
    assert p._clip_active and wait(lambda: not p._clip_active), "clip never finished"
    p._save_btn.click()
    inc = incidents.all()
    assert len(inc) == 3 and inc[0].status == PENDING and inc[0].video_path == video
    assert inc[0].source_label == "Video file" and inc[0].video_time_s is not None
    assert p._save_btn.text() == "Saved ✓" and not p._save_btn.isEnabled()
    p._save_btn.click()
    assert len(incidents.all()) == 3                    # no duplicates
    p.shutdown()
    print("ok full flow")


def test_failure_and_restart():
    def broken():
        raise ImportError("ultralytics is required")
    p, _ = page(broken)
    p.analyze(make_video(3))
    assert wait(lambda: p._badge.text() == "Failed")
    assert "ultralytics" in p.header.subtitle.text()
    p.analyze("/nope/missing.mp4")
    assert p._badge.text() == "Failed" and "missing.mp4" in p.header.subtitle.text()
    p.shutdown()
    print("ok failure")


def test_cancel_by_restart_and_shutdown():
    p, incidents = page()
    p.analyze(make_video(20))
    p.analyze(make_video(10))                       # restart while the first may still be running
    assert wait(lambda: p._badge.text().startswith("Done"))
    assert len(p._rows) == 3                        # only the second video's events
    p.analyze(make_video(20))
    p.shutdown()                                    # cancel + wait, must not hang or crash
    print("ok restart/shutdown")


def test_main_window_builds():
    from vigil.main_window import MainWindow
    w = MainWindow()
    w.show()
    w.sidebar.select(3)
    app.processEvents()
    w.close()
    print("ok main window")


if __name__ == "__main__":
    test_fmt_time()
    test_full_flow()
    test_failure_and_restart()
    test_cancel_by_restart_and_shutdown()
    test_main_window_builds()
    print("ALL OK")
