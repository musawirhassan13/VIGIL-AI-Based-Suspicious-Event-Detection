"""A3.1 tests: rules framework, Crowd formation, Restricted area entry, EventEngine."""
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from vigil.core.ai.detector import PersonDetector  # noqa: E402
from vigil.core.ai.event_engine import EventEngine, build_default_rules  # noqa: E402
from vigil.core.ai.rules import CrowdRule, FrameContext, RestrictedAreaRule, Zone, point_in_polygon  # noqa: E402
from vigil.core.ai.tracker import PersonTracker  # noqa: E402
from vigil.core.ai.video_scan import scan_video  # noqa: E402
from vigil.core.events import Detection, EventType  # noqa: E402

SIZE = (1000, 500)
FIXED = datetime(2026, 1, 1, 12, 0, 0)


def person(tid, foot_x, foot_y, conf=0.9, w=40, h=100):
    return Detection((foot_x - w / 2, foot_y - h, foot_x + w / 2, foot_y), conf, tid)


def ctx(dets, t, frame=0):
    return FrameContext(dets, [], frame, t, SIZE)


def test_point_in_polygon():
    sq = ((0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8))
    assert point_in_polygon(0.5, 0.5, sq) and not point_in_polygon(0.9, 0.5, sq)
    tri = ((0, 0), (1, 0), (0, 1))
    assert point_in_polygon(0.2, 0.2, tri) and not point_in_polygon(0.8, 0.8, tri)
    z = Zone.rect("A", 0.5, 0.5, 1.0, 1.0)
    assert z.contains(0.7, 0.7) and not z.contains(0.2, 0.2)


def test_crowd_needs_count_and_duration():
    r = CrowdRule(min_people=5, duration_s=2.0)
    crowd = [person(i, 100 + 80 * i, 400) for i in range(1, 6)]
    for t in (0.0, 0.5, 1.0, 1.5):
        assert r.evaluate(ctx(crowd, t)) == []
    hits = r.evaluate(ctx(crowd, 2.0))
    assert len(hits) == 1 and hits[0].type == EventType.CROWD and len(hits[0].detections) == 5
    assert abs(hits[0].confidence - 0.7) < 1e-9
    bigger = crowd + [person(9, 900, 400), person(10, 950, 400)]
    assert abs(r.evaluate(ctx(bigger, 2.5))[0].confidence - 0.8) < 1e-9
    assert r.evaluate(ctx(crowd[:3], 3.0)) == []          # count drops -> timer resets
    assert r.evaluate(ctx(crowd, 3.5)) == [] and r.evaluate(ctx(crowd, 4.0)) == []
    assert len(r.evaluate(ctx(crowd, 5.5))) == 1


def test_restricted_area_dwell_once_and_reentry():
    zone = Zone.rect("Lab", 0.5, 0.5, 1.0, 1.0)         # right-bottom half of a 1000x500 frame
    r = RestrictedAreaRule([zone], dwell_s=0.5)
    assert r.evaluate(ctx([person(1, 200, 400)], 0.0)) == []        # outside
    assert r.evaluate(ctx([person(1, 700, 400)], 1.0)) == []        # just entered
    hits = r.evaluate(ctx([person(1, 710, 400)], 1.6))              # stayed 0.6s
    assert len(hits) == 1 and hits[0].key == "Lab:1" and hits[0].detections[0].track_id == 1
    assert abs(hits[0].confidence - (0.55 + 0.45 * 0.9)) < 1e-9
    assert r.evaluate(ctx([person(1, 720, 400)], 2.0)) == []        # still inside: no repeat
    assert r.evaluate(ctx([person(1, 200, 400)], 3.0)) == []        # left
    assert r.evaluate(ctx([person(1, 700, 400)], 4.0)) == []
    assert len(r.evaluate(ctx([person(1, 700, 400)], 4.6))) == 1    # re-entry fires again


def test_restricted_area_foot_point_and_multiple_people():
    zone = Zone.rect("Lab", 0.5, 0.5, 1.0, 1.0)
    r = RestrictedAreaRule([zone], dwell_s=0.0)
    head_in_feet_out = person(1, 700, 240)               # feet at y=240 < 250 (outside), body overlaps
    both = [head_in_feet_out, person(2, 700, 400), person(3, 100, 400)]
    hits = r.evaluate(ctx(both, 0.0)) + r.evaluate(ctx(both, 0.1))
    assert [h.key for h in hits] == ["Lab:2"]
    assert RestrictedAreaRule([], dwell_s=0).evaluate(ctx(both, 1.0)) == []   # no zones -> silent
    untracked = Detection((650, 300, 750, 400), 0.9, None)
    assert RestrictedAreaRule([zone], dwell_s=0).evaluate(ctx([untracked], 0.0)) == []


def test_engine_filters_and_cooldown():
    zone = Zone.rect("Lab", 0.5, 0.5, 1.0, 1.0)
    tracker = PersonTracker()
    eng = EventEngine("1", "Main Gate", [RestrictedAreaRule([zone], dwell_s=0.0, cooldown_s=10)],
                      min_confidence=0.7, clock=lambda: FIXED)
    d = [person(1, 700, 400)]
    out = eng.process(tracker, d, 5, 1.0, SIZE, video_time_s=None)
    assert len(out) == 1
    e = out[0]
    assert (e.type, e.source_id, e.source_label, e.timestamp, e.frame_index) == \
        (EventType.RESTRICTED_AREA, "1", "Main Gate", FIXED, 5) and e.confidence_pct == 96
    # leaves and re-enters inside cooldown -> suppressed; after cooldown -> fires
    eng.process(tracker, [person(1, 100, 400)], 6, 2.0, SIZE)
    assert eng.process(tracker, d, 7, 3.0, SIZE) == []
    eng.process(tracker, [person(1, 100, 400)], 8, 4.0, SIZE)
    assert len(eng.process(tracker, d, 9, 12.0, SIZE)) == 1
    # confidence threshold
    strict = EventEngine("1", "x", [RestrictedAreaRule([zone], dwell_s=0.0)], min_confidence=0.99)
    assert strict.process(tracker, d, 0, 0.0, SIZE) == []
    eng.reset()
    assert len(eng.process(tracker, d, 10, 13.0, SIZE)) == 1


def test_engine_from_settings():
    settings = {"confidence": 80, "events": {"Possible fight": True, "Sudden fall": True,
                                             "Restricted area entry": True, "Crowd formation": False}}
    eng = EventEngine.from_settings(settings, "1", "Cam", [Zone.rect("Z", 0, 0, 1, 1)])
    assert eng.min_confidence == 0.8 and EventType.CROWD not in eng.enabled
    assert EventType.RESTRICTED_AREA in eng.enabled and len(eng.rules) == len(build_default_rules())
    tracker, crowd = PersonTracker(), [person(i, 100 + 80 * i, 400) for i in range(1, 8)]
    for t in (0, 1, 2, 3):
        assert [e for e in eng.process(tracker, crowd, t, float(t), SIZE) if e.type == EventType.CROWD] == []


class Walker(PersonDetector):
    """One person walking left to right along the bottom of a 320x240 frame."""

    def __init__(self):
        self.n = 0

    def detect(self, frame):
        self.n += 1
        x = 10 + 12 * self.n
        return [Detection((x - 15, 140, x + 15, 230), 0.9)]


def test_end_to_end_scan_tracker_engine():
    path = tempfile.mkdtemp() + "/t.mp4"
    w = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 30, (320, 240))
    for _ in range(90):
        w.write(np.zeros((240, 320, 3), np.uint8))
    w.release()
    tracker = PersonTracker()
    eng = EventEngine("upload", "Video file", [RestrictedAreaRule([Zone.rect("Right", 0.6, 0.4, 1, 1)])],
                      clock=lambda: FIXED)
    events = []
    for r in scan_video(path, Walker(), 10, tracker=tracker):
        events += eng.process(tracker, r.detections, r.frame_index, r.time_s, (320, 240), r.time_s)
    assert len(events) == 1 and events[0].video_time_s is not None and events[0].video_time_s > 1.0
    assert events[0].detections[0].track_id == 1


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
    print("ALL OK")
