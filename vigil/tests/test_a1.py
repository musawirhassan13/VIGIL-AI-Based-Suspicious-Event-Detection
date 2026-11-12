"""A1 tests. Contract + scan logic use a fake detector (no torch); real-YOLO test is opt-in via VIGIL_REAL_YOLO_IMAGE."""
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from vigil.core.ai.detector import PersonDetector  # noqa: E402
from vigil.core.ai.draw import draw_detections  # noqa: E402
from vigil.core.ai.video_scan import scan_video, video_info  # noqa: E402
from vigil.core.events import Detection, Event, EventType  # noqa: E402


class FakeDetector(PersonDetector):
    def __init__(self):
        self.calls = 0

    def detect(self, frame):
        self.calls += 1
        return [Detection((10, 20, 60, 140), 0.9)]


def make_video(n=60, fps=30):
    path = tempfile.mkdtemp() + "/t.mp4"
    w = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (160, 120))
    for _ in range(n):
        w.write(np.zeros((120, 160, 3), np.uint8))
    w.release()
    return path


def test_contract():
    d = Detection((10, 20, 60, 140), 0.9)
    assert (d.width, d.height, d.center, d.foot_point) == (50, 120, (35, 80), (35, 140))
    assert d.aspect == 2.4 and Detection((0, 0, 0, 10), 1).aspect == 0.0
    e = Event(EventType.FIGHT, 0.874, "1", "Main Gate", datetime.now(), 42, None, (d,))
    assert e.confidence_pct == 87 and e.type.value == "Possible fight"
    assert [t.value for t in EventType] == ["Possible fight", "Sudden fall", "Restricted area entry", "Crowd formation"]


def test_scan_sampling():
    path = make_video(60, 30)
    info = video_info(path)
    assert round(info.fps) == 30 and info.frame_count == 60
    det = FakeDetector()
    res = list(scan_video(path, det, sample_fps=10))      # every 3rd frame -> 20 samples
    assert len(res) == 20 and det.calls == 20 and res[1].frame_index == 3 and abs(res[1].time_s - 0.1) < 1e-6
    assert len(list(scan_video(path, FakeDetector(), 10, max_frames=5))) == 5
    try:
        list(scan_video("/nope.mp4", FakeDetector()))
        raise AssertionError("expected FileNotFoundError")
    except FileNotFoundError:
        pass


def test_draw():
    f = np.zeros((200, 200, 3), np.uint8)
    draw_detections(f, [Detection((20, 30, 80, 150), 0.8, track_id=3)], alert=True)
    assert f.any()


def test_real_yolo():
    img = os.environ.get("VIGIL_REAL_YOLO_IMAGE")
    if not img:
        print("skip real YOLO")
        return
    from vigil.core.ai.detector import YoloPersonDetector
    frame = cv2.imread(img)
    det = YoloPersonDetector("yolov8n.pt", conf=0.4)
    people = det.detect(frame)
    print("real YOLO people:", len(people), [round(p.confidence, 2) for p in people])
    assert len(people) >= 3          # bus.jpg has 4 clear people
    path = tempfile.mkdtemp() + "/bus.mp4"
    h, w = frame.shape[:2]
    wr = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 10, (w, h))
    for _ in range(10):
        wr.write(frame)
    wr.release()
    res = list(scan_video(path, det, sample_fps=5))
    assert len(res) == 5 and all(len(r.detections) >= 3 for r in res)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
    print("ALL OK")
