"""A3 rule framework. A Rule looks at one frame of tracked people and may report hits."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ...events import Detection, EventType
from ..tracker import Track


@dataclass(frozen=True)
class FrameContext:
    """Everything a rule may look at for one analysed frame."""
    detections: list[Detection]      # people in this frame, with track_id filled in by the tracker
    tracks: list[Track]              # active tracks (motion history, used by fall / fight rules)
    frame_index: int
    now_s: float                     # seconds: video time for files, monotonic clock for live
    frame_size: tuple[int, int]      # (width, height) in pixels
    frame: object | None = None      # raw BGR numpy frame; optional for backwards compatibility


@dataclass(frozen=True)
class RuleHit:
    type: EventType
    confidence: float                # heuristic score 0..1 (not a calibrated probability)
    detections: tuple[Detection, ...]   # people involved (drawn in red)
    key: str = ""                    # identifies "the same incident" for cooldown, e.g. "Lab:7"


class Rule(ABC):
    type: EventType
    cooldown_s: float = 30.0         # the engine ignores repeat hits with the same key within this time

    @abstractmethod
    def evaluate(self, ctx: FrameContext) -> list[RuleHit]:
        ...

    def reset(self) -> None:
        """Forget all state (called when a new video / monitoring session starts)."""
