"""Checks the ESP8266 every few seconds so the UI can show the REAL connection state."""
import threading

from PySide6.QtCore import QThread, Signal

from .core.alert_device import check_status

POLL_S = 3.0
CONNECTED, DISCONNECTED, NO_ADDRESS = "connected", "disconnected", "no_address"


class DeviceMonitor(QThread):
    status_changed = Signal(str, str)     # state (CONNECTED | DISCONNECTED | NO_ADDRESS), address

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._stop = threading.Event()
        self._wake = threading.Event()
        self.state = "unknown"

    def refresh(self) -> None:
        """Check again right now (call after the address changes)."""
        self._wake.set()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def run(self) -> None:
        last = None
        while not self._stop.is_set():
            address = str(self._settings.get("device_address")).strip()
            if not address:
                state = NO_ADDRESS
            else:
                state = CONNECTED if check_status(address)[0] else DISCONNECTED
            if (state, address) != last:
                last = (state, address)
                self.state = state
                self.status_changed.emit(state, address)
            if self._wake.wait(POLL_S):
                self._wake.clear()
