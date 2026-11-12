"""A3: turns tracked people into Events by running the rules, then filtering and de-duplicating."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime

from ..events import Detection, Event, EventType
from .rules import (
    CrowdRule, FallRule, FightModelRule, FrameContext,
    RestrictedAreaRule, Rule, Zone,
)
from .tracker import PersonTracker


def build_default_rules(zones: Iterable[Zone] = ()) -> list[Rule]:
    """Build the app rules; FightModelRule falls back to the original FightRule if needed."""
    return [
        CrowdRule(min_people=4, duration_s=0.5),
        RestrictedAreaRule(zones),
        FallRule(),
        FightModelRule(),
    ]


class EventEngine:
    """One instance per video source (camera or uploaded file). Call process() after tracker.update()."""

    def __init__(
        self,
        source_id: str,
        source_label: str,
        rules: list[Rule],
        min_confidence: float = 0.7,
        enabled: set[EventType] | None = None,
        clock: Callable[[], datetime] = datetime.now,
    ):
        self.source_id = source_id
        self.source_label = source_label
        self.rules = rules
        self.min_confidence = min_confidence
        self.enabled = enabled
        self._clock = clock
        self._last_fired: dict[tuple[EventType, str], float] = {}

    @classmethod
    def from_settings(
        cls,
        settings: dict,
        source_id: str,
        source_label: str,
        zones: Iterable[Zone] = (),
    ) -> "EventEngine":
        """Build from SettingsStore.all(): uses 'confidence' (%) and the 'events' on/off map."""
        known = {t.value: t for t in EventType}
        enabled = {
            known[name]
            for name, on in settings.get("events", {}).items()
            if on and name in known
        }
        return cls(
            source_id,
            source_label,
            build_default_rules(zones),
            min_confidence=settings.get("confidence", 70) / 100,
            enabled=enabled,
        )

    def reset(self) -> None:
        self._last_fired.clear()
        for rule in self.rules:
            rule.reset()

    def process(
        self,
        tracker: PersonTracker,
        detections: list[Detection],
        frame_index: int,
        now_s: float,
        frame_size: tuple[int, int],
        video_time_s: float | None = None,
        frame: object | None = None,
    ) -> list[Event]:
        ctx = FrameContext(
            detections,
            tracker.active_tracks,
            frame_index,
            now_s,
            frame_size,
            frame,
        )
        events: list[Event] = []
        for rule in self.rules:
            if self.enabled is not None and rule.type not in self.enabled:
                continue
            for hit in rule.evaluate(ctx):
                if hit.confidence < self.min_confidence:
                    continue
                slot = (hit.type, hit.key)
                last = self._last_fired.get(slot)
                if last is not None and now_s - last < rule.cooldown_s:
                    continue
                self._last_fired[slot] = now_s
                events.append(
                    Event(
                        hit.type,
                        hit.confidence,
                        self.source_id,
                        self.source_label,
                        self._clock(),
                        frame_index,
                        video_time_s,
                        hit.detections,
                    )
                )
        return events
