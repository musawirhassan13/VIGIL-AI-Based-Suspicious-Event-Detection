"""In-memory incident registry (same idea as CameraStore).

Phase 6 replaces the internals with the SQLite `incidents` table; keep this public API
(all / get / add_event / add_events / set_status + incidents_changed) so the UI does not change.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from PySide6.QtCore import QObject, Signal

from .core.events import Event, EventType

# Incident.status values (same strings the UI shows)
PENDING, CONFIRMED, FALSE_ALARM = "Pending", "Confirmed", "False alarm"


@dataclass
class Incident:
    id: int
    type: EventType
    confidence: float                  # 0..1
    source_id: str                     # camera id as text, or "upload"
    source_label: str                  # "Main Gate" / "Video file"
    detected_at: datetime
    status: str = PENDING
    video_path: str | None = None      # uploaded file, so the clip can be replayed later
    video_time_s: float | None = None  # position of the event inside that file
    frame_index: int = 0

    @property
    def confidence_pct(self) -> int:
        return round(self.confidence * 100)


class IncidentStore(QObject):
    incidents_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._incidents: list[Incident] = []
        self._next_id = 1

    def all(self) -> list[Incident]:
        """Newest first."""
        return list(reversed(self._incidents))

    def get(self, incident_id: int) -> Incident | None:
        return next((i for i in self._incidents if i.id == incident_id), None)

    def add_event(self, event: Event, video_path: str | None = None) -> Incident:
        inc = self._make(event, video_path)
        self.incidents_changed.emit()
        return inc

    def add_events(self, events: list[Event], video_path: str | None = None) -> list[Incident]:
        made = [self._make(e, video_path) for e in events]
        if made:
            self.incidents_changed.emit()
        return made

    def set_status(self, incident_id: int, status: str) -> None:
        inc = self.get(incident_id)
        if inc is None or inc.status == status:
            return
        inc.status = status
        self.incidents_changed.emit()

    def _make(self, e: Event, video_path: str | None) -> Incident:
        inc = Incident(self._next_id, e.type, e.confidence, e.source_id, e.source_label, e.timestamp,
                       PENDING, video_path, e.video_time_s, e.frame_index)
        self._next_id += 1
        self._incidents.append(inc)
        return inc