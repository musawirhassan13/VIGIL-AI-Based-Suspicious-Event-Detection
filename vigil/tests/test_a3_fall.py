"""A3.2 tests: Sudden fall rule (synthetic shapes, no YOLO)."""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vigil.core.ai.event_engine import EventEngine, build_default_rules  # noqa: E402
from vigil.core.ai.rules import FallRule, FrameContext  # noqa: E402
from vigil.core.ai.tracker import PersonTracker  # noqa: E402
from vigil.core.events import Detection, EventType  # noqa: E402

SIZE = (1000, 500)


def standing(tid=1, x=500):          # 40x100 -> aspect 2.5
    return Detection((x - 20, 300, x + 20, 400), 0.9, tid)


def bending(tid=1, x=500):           # 70x80 -> aspect ~1.14 (in between)
    return Detection((x - 35, 320, x + 35, 400), 0.9, tid)


def lying(tid=1, x=500):             # 110x35 -> aspect 0.32
    return Detection((x - 55, 365, x + 55, 400), 0.9, tid)


def run(rule, timeline, step=0.1):
    """timeline: list of (duration_s, detection-or-list-or-None). Returns all hits."""
    hits, t, i = [], 0.0, 0
    for dur, d in timeline:
        for _ in range(round(dur / step)):
            dets = [] if d is None else (d if isinstance(d, list) else [d])
            hits += rule.evaluate(FrameContext(dets, [], i, round(t, 6), SIZE))
            t, i = t + step, i + 1
    return hits


def test_real_fall_fires_once():
    r = FallRule()
    hits = run(r, [(1.5, standing()), (0.2, bending()), (2.5, lying())])
    assert len(hits) == 1 and hits[0].type == EventType.FALL and hits[0].key == "1"
    assert hits[0].confidence >= 0.7 and hits[0].detections[0].track_id == 1


def test_get_up_quickly_is_not_a_fall():
    assert run(FallRule(), [(1.0, standing()), (0.1, bending()), (0.6, lying()), (1.0, standing())]) == []


def test_slow_lying_down_is_not_a_fall():
    assert run(FallRule(), [(1.0, standing()), (3.0, bending()), (2.5, lying())]) == []


def test_sitting_or_bending_is_not_a_fall():
    assert run(FallRule(), [(1.0, standing()), (5.0, bending())]) == []


def test_already_lying_when_first_seen():
    assert run(FallRule(), [(4.0, lying())]) == []


def test_crawling_away_is_not_a_fall():
    r = FallRule()
    crawl = [(0.1, lying(x=500 + 25 * k)) for k in range(25)]
    assert run(r, [(1.0, standing()), (0.1, bending())] + crawl) == []


def test_frame_edge_cropping_ignored():
    r = FallRule()
    cut_standing = Detection((0, 300, 30, 400), 0.9, 1)         # touches left edge
    cut_lying = Detection((0, 365, 100, 400), 0.9, 1)
    assert run(r, [(1.0, cut_standing), (3.0, cut_lying)]) == []


def test_width_growth_without_height_loss_is_not_a_fall():
    merged = Detection((430, 300, 570, 400), 0.9, 1)            # 140x100: aspect 0.71 but not shorter
    assert run(FallRule(), [(1.0, standing()), (3.0, merged)]) == []


def test_lost_track_forgotten():
    r = FallRule()
    assert run(r, [(1.0, standing()), (0.1, bending()), (0.3, lying()), (3.0, None), (2.5, lying())]) == []


def test_only_the_person_who_falls():
    two = lambda d: [d, standing(tid=2, x=800)]                 # noqa: E731
    hits = run(FallRule(), [(1.0, two(standing())), (0.2, two(bending())), (2.5, two(lying()))])
    assert [h.key for h in hits] == ["1"]


def test_new_track_id_after_fall_is_linked_to_vanished_upright():
    # tracker lost the falling person and started id 5 right where id 1 stood
    r = FallRule()
    hits = run(r, [(1.0, standing(1)), (0.2, None), (2.5, lying(5))])
    assert len(hits) == 1 and hits[0].key == "5" and hits[0].confidence >= 0.7


def test_unrelated_lying_track_is_not_linked():
    far = run(FallRule(), [(1.0, standing(1, x=100)), (0.2, None), (2.5, lying(5, x=800))])
    assert far == []
    still_there = run(FallRule(), [(1.0, [standing(1, x=500)]), (0.2, [standing(1, x=500)]),
                                   (2.5, [standing(1, x=500), lying(5, x=520)])])
    assert still_there == []                                        # id 1 is still standing: different person


def test_slower_real_world_fall_with_wide_but_not_flat_box():
    tall = Detection((460, 280, 520, 400), 0.9, 1)                  # 60x120, aspect 2.0
    mid = Detection((440, 320, 540, 400), 0.9, 1)                   # 100x80, aspect 0.8, height 0.67
    low = Detection((430, 340, 550, 400), 0.9, 1)                   # 120x60, aspect 0.5
    hits = run(FallRule(), [(1.0, tall), (0.3, mid), (2.0, low)])
    assert len(hits) == 1 and hits[0].confidence >= 0.7


def test_engine_integration_and_default_rules():
    assert any(isinstance(r, FallRule) for r in build_default_rules())
    eng = EventEngine("3", "Cafeteria", [FallRule()], clock=lambda: datetime(2026, 1, 1))
    tracker, events, t = PersonTracker(), [], 0.0
    for d, dur in ((standing(), 1.5), (bending(), 0.2), (lying(), 3.0)):
        for _ in range(round(dur / 0.1)):
            events += eng.process(tracker, [d], 0, t, SIZE)
            t += 0.1
    assert len(events) == 1 and events[0].type == EventType.FALL and events[0].source_label == "Cafeteria"
    assert events[0].confidence_pct >= 70


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
    print("ALL OK")
