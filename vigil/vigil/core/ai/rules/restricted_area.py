"""Restricted area entry: a person's feet stay inside a drawn zone."""
from __future__ import annotations

from dataclasses import dataclass

from ...events import EventType
from .base import FrameContext, Rule, RuleHit

Point = tuple[float, float]


def point_in_polygon(x: float, y: float, points: tuple[Point, ...]) -> bool:
    """Ray-casting test."""
    inside = False
    j = len(points) - 1
    for i in range(len(points)):
        xi, yi = points[i]
        xj, yj = points[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


@dataclass(frozen=True)
class Zone:
    """Polygon in NORMALISED coordinates (0..1 of frame width/height), so it survives resizing."""
    name: str
    points: tuple[Point, ...]

    @classmethod
    def rect(cls, name: str, x1: float, y1: float, x2: float, y2: float) -> "Zone":
        return cls(name, ((x1, y1), (x2, y1), (x2, y2), (x1, y2)))

    def contains(self, x: float, y: float) -> bool:
        return point_in_polygon(x, y, self.points)


class RestrictedAreaRule(Rule):
    type = EventType.RESTRICTED_AREA

    def __init__(self, zones=(), dwell_s: float = 0.5, cooldown_s: float = 30.0):
        self.zones = list(zones)
        self.dwell_s = dwell_s           # must stay inside this long (filters box jitter at the edge)
        self.cooldown_s = cooldown_s     # per person + zone
        self._inside_since: dict[tuple[str, int], float] = {}
        self._fired: set[tuple[str, int]] = set()

    def reset(self) -> None:
        self._inside_since.clear()
        self._fired.clear()

    def evaluate(self, ctx: FrameContext) -> list[RuleHit]:
        if not self.zones:
            return []
        w, h = ctx.frame_size
        hits: list[RuleHit] = []
        seen: set[tuple[str, int]] = set()
        for det in ctx.detections:
            if det.track_id is None or w <= 0 or h <= 0:
                continue
            fx, fy = det.foot_point
            fx, fy = fx / w, fy / h
            for zone in self.zones:
                key = (zone.name, det.track_id)
                if not zone.contains(fx, fy):
                    continue
                seen.add(key)
                since = self._inside_since.setdefault(key, ctx.now_s)
                if ctx.now_s - since >= self.dwell_s and key not in self._fired:
                    self._fired.add(key)
                    hits.append(RuleHit(self.type, min(0.99, 0.55 + 0.45 * det.confidence),
                                        (det,), f"{zone.name}:{det.track_id}"))
        # anyone who left the zone (or disappeared) is forgotten, so re-entry can fire again
        for key in [k for k in self._inside_since if k not in seen]:
            del self._inside_since[key]
            self._fired.discard(key)
        return hits