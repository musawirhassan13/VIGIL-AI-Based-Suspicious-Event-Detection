"""A4 tests: LiveAnalyzer (Qt-free, fake detector)."""
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402

from vigil.core.ai.detector import PersonDetector  # noqa: E402
from vigil.core.ai.event_engine import EventEngine  # noqa: E402
from vigil.core.ai.live_pipeline import STALE_S, LiveAnalyzer  # noqa: E402
from vigil.core.ai.rules import CrowdRule  # noqa: E402
from vigil.core.events import Detection, EventType  # noqa: E402

FRAME = np.zeros((240, 320, 3), np.uint8)


class Fake(PersonDetector):
    def __init__(self, n=2):
        self.n, self.calls = n, 0

    def detect(self, frame):
        self.calls += 1
        return [Detection((20 + 90 * i, 60, 70 + 90 * i, 200), 0.9) for i in range(self.n)]


def engine(min_people=1):
    return EventEngine("1", "Cam", [CrowdRule(min_people=min_people, duration_s=0.0)],
                       min_confidence=0.5, clock=lambda: datetime(2026, 1, 1))


def wait(cond, secs=5.0):
    t = time.time()
    while not cond() and time.time() - t < secs:
        time.sleep(0.01)
    return cond()


def test_detections_tracks_and_events():
    a = LiveAnalyzer(lambda: Fake(2), engine(), sample_fps=20)
    a.start()
    try:
        assert wait(lambda: (a.maybe_submit(FRAME, time.monotonic()) or True) and a.latest(time.monotonic()))
        dets = a.latest(time.monotonic())
        assert len(dets) == 2 and {d.track_id for d in dets} == {1, 2}
        assert wait(lambda: a._events != [])
        ev = a.pop_events()
        assert len(ev) == 1 and ev[0].type == EventType.CROWD and a.pop_events() == []
        assert a.latest(time.monotonic() + STALE_S + 1) == []        # stale boxes are dropped
    finally:
        a.stop()
    assert not a._thread.is_alive()


def test_sampling_rate_limits_inference():
    fake = Fake()
    a = LiveAnalyzer(lambda: fake, engine(), sample_fps=2)           # at most every 0.5 s
    a.start()
    try:
        accepted = 0
        for i in range(100):                                          # 100 frames over 1.0 s of clock
            accepted += a.maybe_submit(FRAME, i * 0.01)
            time.sleep(0.003)
        assert accepted <= 2
        assert wait(lambda: fake.calls == accepted)
    finally:
        a.stop()


def test_submit_copies_frame():
    a = LiveAnalyzer(lambda: Fake(), engine(), sample_fps=20)       # not started: frame stays pending
    f = np.zeros((10, 10, 3), np.uint8)
    assert a.maybe_submit(f, 1.0)
    f[:] = 255
    assert a._pending[0].max() == 0
    assert not a.maybe_submit(f, 5.0)                                # one pending frame at a time


def test_model_load_error_is_reported_not_raised():
    def boom():
        raise ImportError("ultralytics is required")
    a = LiveAnalyzer(boom, engine())
    a.start()
    assert wait(lambda: a.error is not None) and "ultralytics" in a.error
    assert a.maybe_submit(FRAME, 100.0) is False and a.latest(100.0) == []
    a.stop()


def test_inference_error_stops_analysis_cleanly():
    class Bad(PersonDetector):
        def detect(self, frame):
            raise RuntimeError("cuda exploded")
    a = LiveAnalyzer(lambda: Bad(), engine())
    a.start()
    a.maybe_submit(FRAME, 0.0)
    assert wait(lambda: a.error is not None) and "cuda exploded" in a.error
    a.stop()


def test_reset_restarts_track_ids():
    a = LiveAnalyzer(lambda: Fake(1), engine(min_people=99), sample_fps=20)
    a.start()
    try:
        a.maybe_submit(FRAME, 0.0)
        assert wait(lambda: a.latest(0.0) != [])
        assert a.latest(0.0)[0].track_id == 1
        a.reset()
        a.maybe_submit(FRAME, 1.0)
        assert wait(lambda: a.latest(1.0) != [] and a._dets_time == 1.0)
        assert a.latest(1.0)[0].track_id == 1                        # tracker started over
    finally:
        a.stop()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
    print("ALL OK", threading.active_count(), "threads")
