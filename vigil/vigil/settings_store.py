"""Persistent app settings (JSON in the user's config folder)."""
import copy
import json
import os
from pathlib import Path

from PySide6.QtCore import QObject, QStandardPaths, Signal

DEFAULTS = {
    "confidence": 70,          # alert threshold, %
    "fps": 10,                 # analysis sampling rate
    "events": {"Possible fight": True, "Sudden fall": True,
               "Restricted area entry": True, "Crowd formation": False},
    "clip_seconds": 20,
    "retention_days": 90,
    "storage_dir": "./evidence",
    "device_address": "192.168.1.50",   # ESP8266, "host" or "host:port"
    "led": True,
    "buzzer": True,
}


class SettingsStore(QObject):
    changed = Signal()

    def __init__(self, path: Path | None = None):
        super().__init__()
        if path is None:
            base = QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation) \
                or str(Path.home() / ".vigil")
            path = Path(base) / "settings.json"
        self._path = Path(path)
        self._data = self._load()

    def _load(self) -> dict:
        data = copy.deepcopy(DEFAULTS)
        try:
            raw = json.loads(self._path.read_text("utf-8"))
        except (OSError, ValueError):
            return data
        if not isinstance(raw, dict):
            return data
        for key, value in raw.items():
            if key not in data:
                continue
            if key == "events" and isinstance(value, dict):
                data["events"].update({n: bool(b) for n, b in value.items() if n in data["events"]})
            elif type(value) is type(data[key]):
                data[key] = value
        return data

    def get(self, key: str):
        return copy.deepcopy(self._data[key])

    def all(self) -> dict:
        return copy.deepcopy(self._data)

    def update(self, values: dict) -> None:
        """Merge, write atomically, then notify. Raises OSError if the file can't be written."""
        new = {**self._data, **copy.deepcopy(values)}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(new, indent=2), "utf-8")
        os.replace(tmp, self._path)
        self._data = new
        self.changed.emit()
