"""Crowd formation: many people in view for a sustained time."""
from __future__ import annotations

from ...events import EventType
from .base import FrameContext, Rule, RuleHit


class CrowdRule(Rule):
    type = EventType.CROWD

    def __init__(self, min_people: int = 5, duration_s: float = 2.0, cooldown_s: float = 30.0):
        self.min_people = min_people
        self.duration_s = duration_s     # how long the count must stay high before alerting
        self.cooldown_s = cooldown_s
        self._since: float | None = None

    def reset(self) -> None:
        self._since = None

    def evaluate(self, ctx: FrameContext) -> list[RuleHit]:
        n = len(ctx.detections)
        if n < self.min_people:
            self._since = None
            return []
        if self._since is None:
            self._since = ctx.now_s
        if ctx.now_s - self._since < self.duration_s:
            return []
        confidence = min(0.95, 0.7 + 0.05 * (n - self.min_people))   # more people -> more certain
        return [RuleHit(self.type, confidence, tuple(ctx.detections))]