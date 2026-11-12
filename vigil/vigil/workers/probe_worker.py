"""Runs the 'Test Connection' check off the UI thread."""
from PySide6.QtCore import QThread, Signal

from ..core.capture import parse_source, probe_source


class ProbeWorker(QThread):
    probe_done = Signal(str, bool, str)   # source text, ok, message

    def __init__(self, source_text: str, parent=None):
        super().__init__(parent)
        self._text = source_text.strip()

    def run(self) -> None:
        try:
            result = probe_source(parse_source(self._text))
        except ValueError as e:
            self.probe_done.emit(self._text, False, str(e))
            return
        except Exception as e:  # noqa: BLE001 - never let a probe crash the thread silently
            self.probe_done.emit(self._text, False, f"Error: {e}")
            return
        self.probe_done.emit(self._text, result.ok, result.message)