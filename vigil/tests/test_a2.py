"""A2 tests: tracker identity logic (no torch needed)."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from vigil.core.ai.detector import PersonDetector  # noqa: E402
from vigil.core.ai.tracker import PersonTracker, iou  # noqa: E402
from vigil.core.ai.video_scan import scan_video  # noqa: E402
from vigil.core.events import Detection  # noqa: E402


def box(x, y, w=50, h=120):
    return Detection((x, y, x + w, y + h), 0.9)


def ids(out):
    return [d.track_id for d in out]


def test_iou():
    assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0
    assert iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0
    assert abs(iou((0, 0, 10, 10), (5, 0, 15, 10)) - 1 / 3) < 1e-9


def test_two_people_keep_ids():
    t = PersonTracker()
    first = ids(t.update([box(100, 100), box(400, 100)], 0))
    assert first == [1, 2]
    for f in range(1, 25):
        out = t.update([box(100 + 5 * f, 100), box(400 - 5 * f, 100)], f)
        assert ids(out) == [1, 2], (f, ids(out))
    assert len(t.active_tracks) == 2


def test_ids_follow_people_not_list_order():
    t = PersonTracker()
    t.update([box(100, 100), box(400, 100)], 0)
    out = t.update([box(405, 100), box(105, 100)], 1)       # detector returned them swapped
    assert ids(out) == [2, 1]


def test_crossing_paths_keep_ids():
    t = PersonTracker()
    t.update([box(100, 100), box(300, 160)], 0)
    for f in range(1, 21):
        out = t.update([box(100 + 10 * f, 100), box(300 - 10 * f, 160)], f)
        assert ids(out) == [1, 2], (f, ids(out))


def test_fast_mover_matched_by_prediction():
    t = PersonTracker()
    t.update([box(0, 100)], 0)
    for f in range(1, 10):
        assert ids(t.update([box(40 * f, 100)], f)) == [1]   # moves ~80% of its width per step


def test_short_occlusion_keeps_id_and_long_gap_does_not():
    t = PersonTracker(max_missed=5)
    for f in range(4):
        t.update([box(100 + 6 * f, 100)], f)
    for f in range(4, 7):
        t.update([], f)                                      # 3 missed samples
    assert ids(t.update([box(100 + 6 * 7, 100)], 7)) == [1]
    for f in range(8, 15):
        t.update([], f)                                      # gone for 7 > max_missed
    assert t.tracks == []
    assert ids(t.update([box(150, 100)], 15)) == [2]         # new person gets a new id


def test_history_and_velocity():
    t = PersonTracker()
    t.update([box(100, 100)], 0)
    t.update([box(110, 100)], 1)
    tr = t.tracks[0]
    assert tr.velocity == (10.0, 0.0) and tr.speed == 10.0 and tr.hits == 2 and len(tr.history) == 2
    t.reset()
    assert t.tracks == [] and ids(t.update([box(0, 0)], 0)) == [1]


class Mover(PersonDetector):
    def __init__(self):
        self.n = 0

    def detect(self, frame):
        self.n += 1
        return [box(20 + 4 * self.n, 30)]


def test_scan_with_tracker():
    path = tempfile.mkdtemp() + "/t.mp4"
    w = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 30, (320, 240))
    for _ in range(60):
        w.write(np.zeros((240, 320, 3), np.uint8))
    w.release()
    res = list(scan_video(path, Mover(), 10, tracker=PersonTracker()))
    assert len(res) == 20 and {d.track_id for r in res for d in r.detections} == {1}
    res = list(scan_video(path, Mover(), 10))                # still works without a tracker
    assert res[0].detections[0].track_id is None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
    print("ALL OK")
