"""A2: multi-person tracker. Gives each detected person a stable `track_id` across frames.

Qt-free, no extra dependencies. Matching = IoU against each track's *predicted* box
(last box shifted by its velocity), then a centre-distance fallback for fast movers.
A3 (event rules) reads `tracker.tracks` for motion history (speed, aspect-ratio change).
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field, replace

from ..events import BBox, Detection

HISTORY_LEN = 30   # samples of (frame_index, box) kept per track


def iou(a: BBox, b: BBox) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _center(b: BBox) -> tuple[float, float]:
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


@dataclass
class Track:
    id: int
    box: BBox
    confidence: float
    first_frame: int
    last_frame: int
    hits: int = 1
    missed: int = 0      # consecutive updates without a matching detection
    history: deque = field(default_factory=lambda: deque(maxlen=HISTORY_LEN))

    def __post_init__(self) -> None:
        self.history.append((self.last_frame, self.box))

    @property
    def velocity(self) -> tuple[float, float]:
        """Centre movement in pixels per sampled step (0, 0 until two samples exist)."""
        if len(self.history) < 2:
            return 0.0, 0.0
        (f0, b0), (f1, b1) = self.history[-2], self.history[-1]
        (x0, y0), (x1, y1) = _center(b0), _center(b1)
        return x1 - x0, y1 - y0

    @property
    def speed(self) -> float:
        vx, vy = self.velocity
        return (vx * vx + vy * vy) ** 0.5

    def predicted_box(self) -> BBox:
        vx, vy = self.velocity
        k = self.missed + 1
        b = self.box
        return (b[0] + vx * k, b[1] + vy * k, b[2] + vx * k, b[3] + vy * k)


class PersonTracker:
    def __init__(self, iou_threshold: float = 0.3, max_missed: int = 10,
                 max_dist_ratio: float = 0.6):
        self.iou_threshold = iou_threshold
        self.max_missed = max_missed              # samples a lost person is remembered
        self.max_dist_ratio = max_dist_ratio      # fallback gate: x track height
        self._tracks: dict[int, Track] = {}
        self._next_id = 1

    @property
    def tracks(self) -> list[Track]:
        """Every remembered track (including ones temporarily missed)."""
        return list(self._tracks.values())

    @property
    def active_tracks(self) -> list[Track]:
        """Tracks matched in the most recent update()."""
        return [t for t in self._tracks.values() if t.missed == 0]

    def reset(self) -> None:
        self._tracks.clear()
        self._next_id = 1

    def update(self, detections: list[Detection], frame_index: int) -> list[Detection]:
        """Return the same detections, each with `track_id` filled in."""
        tracks = list(self._tracks.values())
        matched_t: dict[int, int] = {}   # track index -> detection index
        matched_d: set[int] = set()

        # Pass 1: IoU against predicted boxes, best pairs first
        pairs = []
        for ti, t in enumerate(tracks):
            pb = t.predicted_box()
            for di, d in enumerate(detections):
                v = iou(pb, d.box)
                if v >= self.iou_threshold:
                    pairs.append((v, ti, di))
        for _, ti, di in sorted(pairs, reverse=True):
            if ti not in matched_t and di not in matched_d:
                matched_t[ti] = di
                matched_d.add(di)

        # Pass 2: centre-distance fallback for leftovers (fast movement, little overlap)
        pairs = []
        for ti, t in enumerate(tracks):
            if ti in matched_t:
                continue
            px, py = _center(t.predicted_box())
            gate = self.max_dist_ratio * (t.box[3] - t.box[1])
            for di, d in enumerate(detections):
                if di in matched_d:
                    continue
                cx, cy = d.center
                dist = ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5
                if dist <= gate:
                    pairs.append((dist, ti, di))
        for _, ti, di in sorted(pairs):
            if ti not in matched_t and di not in matched_d:
                matched_t[ti] = di
                matched_d.add(di)

        out: list[Detection | None] = [None] * len(detections)
        for ti, di in matched_t.items():
            t, d = tracks[ti], detections[di]
            t.box, t.confidence, t.last_frame = d.box, d.confidence, frame_index
            t.hits += 1
            t.missed = 0
            t.history.append((frame_index, d.box))
            out[di] = replace(d, track_id=t.id)

        for di, d in enumerate(detections):
            if di in matched_d:
                continue
            t = Track(self._next_id, d.box, d.confidence, frame_index, frame_index)
            self._tracks[t.id] = t
            self._next_id += 1
            out[di] = replace(d, track_id=t.id)

        for ti, t in enumerate(tracks):
            if ti in matched_t:
                continue
            t.missed += 1
            if t.missed > self.max_missed:
                del self._tracks[t.id]
        return out  # type: ignore[return-value]
