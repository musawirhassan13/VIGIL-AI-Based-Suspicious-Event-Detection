
from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from math import hypot
from statistics import median

from ...events import Detection, EventType
from .base import FrameContext, Rule, RuleHit

log = logging.getLogger("vigil")


@dataclass
class _Seen:
    """The previous measurement of one person."""
    t: float
    cx: float
    cy: float
    w: float
    h: float


class FightRule(Rule):
    type = EventType.FIGHT

    def __init__(self, window_s: float = 2.0, min_duration_s: float = 1.2, min_samples: int = 4,
                 gap_ratio: float = 0.3, depth_ratio: float = 0.5, min_close_ratio: float = 0.8,
                 agitation_threshold: float = 1.5, shape_weight: float = 0.5, min_hits: int = 3,
                 max_dt_s: float = 1.0, cooldown_s: float = 30.0, debug: bool = False):
        self.window_s = window_s                      # how much recent time is judged
        self.min_duration_s = min_duration_s          # pair must be observed this long
        self.min_samples = min_samples                # and at least this many measurements
        self.gap_ratio = gap_ratio                    # "close": horizontal gap <= this x body height
        self.depth_ratio = depth_ratio                # same depth: feet within this x body height
        self.min_close_ratio = min_close_ratio        # share of the window the pair must be close
        self.agitation_threshold = agitation_threshold   # THE main tuning knob
        self.shape_weight = shape_weight              # weight of box-shape change vs movement
        self.min_hits = min_hits                      # ignore tracks seen fewer times than this
        self.max_dt_s = max_dt_s                      # ignore measurements with a bigger time gap
        self.cooldown_s = cooldown_s
        self.debug = debug
        self._prev: dict[int, _Seen] = {}
        self._pairs: dict[tuple[int, int], deque] = {}      # pair -> (time, close, agitation)
        self._blocked: dict[int, float] = {}                # person -> no new fight alert until
        self._last_debug: dict[tuple[int, int], float] = {}

    def reset(self) -> None:
        self._prev.clear()
        self._pairs.clear()
        self._blocked.clear()
        self._last_debug.clear()

    def evaluate(self, ctx: FrameContext) -> list[RuleHit]:
        now = ctx.now_s
        hits_by_id = {t.id: t.hits for t in ctx.tracks}
        people = [d for d in ctx.detections
                  if d.track_id is not None and d.width > 0 and d.height > 0
                  and hits_by_id.get(d.track_id, 0) >= self.min_hits]
        before = {d.track_id: self._prev.get(d.track_id) for d in people}
        out: list[RuleHit] = []

        for i in range(len(people)):
            for j in range(i + 1, len(people)):
                a, b = people[i], people[j]
                ia, ib = sorted((a.track_id, b.track_id))
                if (self._blocked.get(ia, float("-inf")) > now
                        or self._blocked.get(ib, float("-inf")) > now):
                    continue
                key = (ia, ib)
                close = self._is_close(a, b)
                samples = self._pairs.get(key)
                if not close and samples is None:
                    continue                      # far apart and not being watched
                pa, pb = before[a.track_id], before[b.track_id]
                if pa is None or pb is None or abs(pa.t - pb.t) > 1e-6:
                    continue                      # no clean previous measurement for both
                dt = now - pa.t
                if dt < 0.02 or dt > self.max_dt_s:
                    continue
                agitation = self._agitation(a, b, pa, pb, dt) if close else 0.0
                if samples is None:
                    samples = self._pairs[key] = deque()
                samples.append((now, close, agitation))
                while samples and now - samples[0][0] > self.window_s:
                    samples.popleft()
                if len(samples) < self.min_samples:
                    continue

                span, close_ratio, med = self._stats(samples)
                self._debug(key, now, close_ratio, med, span)
                if span < self.min_duration_s or close_ratio < self.min_close_ratio:
                    continue
                if med < self.agitation_threshold:
                    continue

                excess = min(1.0, med / self.agitation_threshold - 1.0)
                confidence = min(0.95, 0.72 + 0.23 * excess)   # heuristic score, not a probability
                out.append(RuleHit(self.type, confidence, (a, b), f"{ia}-{ib}"))
                samples.clear()
                self._blocked[ia] = self._blocked[ib] = now + self.cooldown_s

        # housekeeping
        for key in list(self._pairs):
            s = self._pairs[key]
            if not s or now - s[-1][0] > self.window_s or not any(x[1] for x in s):
                del self._pairs[key]
        for d in people:
            cx, cy = d.center
            self._prev[d.track_id] = _Seen(now, cx, cy, d.width, d.height)
        for tid in [t for t, s in self._prev.items() if now - s.t > 2.0]:
            del self._prev[tid]
        for tid in [t for t, until in self._blocked.items() if until <= now]:
            del self._blocked[tid]
        return out

    def _is_close(self, a: Detection, b: Detection) -> bool:
        avg_h = (a.height + b.height) / 2
        gap_x = max(0.0, max(a.box[0], b.box[0]) - min(a.box[2], b.box[2]))   # 0 if boxes overlap
        foot_dy = abs(a.box[3] - b.box[3])
        return gap_x <= self.gap_ratio * avg_h and foot_dy <= self.depth_ratio * avg_h

    def _agitation(self, a: Detection, b: Detection, pa: _Seen, pb: _Seen, dt: float) -> float:
        ax, ay = a.center
        bx, by = b.center
        # movement relative to each other (common movement cancels out), in body heights per second
        rel = hypot((ax - pa.cx) - (bx - pb.cx), (ay - pa.cy) - (by - pb.cy)) / 2
        avg_h = (a.height + b.height) / 2
        rel_rate = rel / (avg_h * dt)
        # how fast the boxes change size (fraction per second)
        shape = (abs(a.width - pa.w) / pa.w + abs(a.height - pa.h) / pa.h
                 + abs(b.width - pb.w) / pb.w + abs(b.height - pb.h) / pb.h) / 4
        return rel_rate + self.shape_weight * (shape / dt)

    @staticmethod
    def _stats(samples) -> tuple[float, float, float]:
        span = samples[-1][0] - samples[0][0]
        close = [s[2] for s in samples if s[1]]
        close_ratio = len(close) / len(samples)
        med = median(close) if close else 0.0          # median: one noisy box can't trigger it
        return span, close_ratio, med

    def _debug(self, key, now: float, close_ratio: float, med: float, span: float) -> None:
        if not self.debug or now - self._last_debug.get(key, float("-inf")) < 0.5:
            return
        self._last_debug[key] = now
        log.info("FIGHT-DEBUG pair %d-%d close=%.0f%% agitation(median)=%.2f span=%.1fs (threshold %.2f)",
                 key[0], key[1], close_ratio * 100, med, span, self.agitation_threshold)