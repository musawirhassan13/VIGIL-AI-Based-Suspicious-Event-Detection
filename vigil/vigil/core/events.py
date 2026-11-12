"""Event contract shared by every layer (AI engine, alerts, DB, UI).

Qt-free on purpose. The AI engine produces `Event`s; the UI and database only consume them.
Human-review state (Pending / Confirmed / False alarm) is NOT part of an Event: it belongs
to the saved incident record created later from an Event.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

BBox = tuple[float, float, float, float]   # x1, y1, x2, y2 in frame pixels


class EventType(str, Enum):
    """Values are the exact labels shown in the UI."""
    FIGHT = "Possible fight"
    FALL = "Sudden fall"
    RESTRICTED_AREA = "Restricted area entry"
    CROWD = "Crowd formation"


@dataclass(frozen=True)
class Detection:
    """One detected person in one frame. `track_id` stays None until tracking (A2)."""
    box: BBox
    confidence: float
    track_id: int | None = None

    @property
    def width(self) -> float:
        return self.box[2] - self.box[0]

    @property
    def height(self) -> float:
        return self.box[3] - self.box[1]

    @property
    def center(self) -> tuple[float, float]:
        return (self.box[0] + self.box[2]) / 2, (self.box[1] + self.box[3]) / 2

    @property
    def foot_point(self) -> tuple[float, float]:
        """Bottom-centre of the box: where the person stands (used for zone tests)."""
        return (self.box[0] + self.box[2]) / 2, self.box[3]

    @property
    def aspect(self) -> float:
        """height / width: ~2-3 standing, <1 lying down (used for fall detection)."""
        return self.height / self.width if self.width > 0 else 0.0


@dataclass(frozen=True)
class Event:
    type: EventType
    confidence: float                 # 0..1
    source_id: str                    # camera id as text, or "upload" for a video file
    source_label: str                 # e.g. "Main Gate" / "Video file"
    timestamp: datetime               # wall-clock time of detection
    frame_index: int
    video_time_s: float | None = None  # position in the file (uploads); None for live
    detections: tuple[Detection, ...] = ()   # people involved, for drawing boxes

    @property
    def confidence_pct(self) -> int:
        return round(self.confidence * 100)
