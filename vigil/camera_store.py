"""In-memory camera registry.

Phase 6 replaces the internals with the SQLite `cameras` table; keep this public API
(all / get / add / update / set_status + signals) so the UI does not change.
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

# Camera.status values
UNKNOWN, ONLINE, OFFLINE = "unknown", "online", "offline"


@dataclass
class CameraConfig:
    id: int
    name: str
    location: str
    source: str            # RTSP URL, "0" for webcam, etc.
    status: str = UNKNOWN

    @property
    def label(self) -> str:
        return f"{self.name} · {self.location}" if self.location else self.name


class CameraStore(QObject):
    cameras_changed = Signal()          # camera added or edited
    status_changed = Signal(int, str)   # camera_id, new status

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cameras: list[CameraConfig] = []
        self._next_id = 1

    def all(self) -> list[CameraConfig]:
        return list(self._cameras)

    def get(self, camera_id: int) -> CameraConfig | None:
        return next((c for c in self._cameras if c.id == camera_id), None)

    def add(self, name: str, location: str, source: str, status: str = UNKNOWN) -> CameraConfig:
        cam = CameraConfig(self._next_id, name, location, source, status)
        self._next_id += 1
        self._cameras.append(cam)
        self.cameras_changed.emit()
        return cam

    def update(self, camera_id: int, name: str, location: str, source: str) -> None:
        cam = self.get(camera_id)
        if cam is None:
            return
        if source != cam.source:
            cam.status = UNKNOWN
        cam.name, cam.location, cam.source = name, location, source
        self.cameras_changed.emit()

    def set_status(self, camera_id: int, status: str) -> None:
        cam = self.get(camera_id)
        if cam is None or cam.status == status:
            return
        cam.status = status
        self.status_changed.emit(camera_id, status)