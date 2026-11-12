"""ESP8266 alert device: one simple HTTP request turns the LED and buzzer on. Qt-free.

The ESP8266 sketch (hardware/esp8266_alert/esp8266_alert.ino) answers:
    GET http://<device-ip>/alert?led=1&buzzer=1   -> LED (D7) + buzzer (D4) on for a few seconds
    GET http://<device-ip>/status                 -> 200 when the device is online (connection check)
    GET http://<device-ip>/off                    -> stop the alert
If you use a different sketch, change ALERT_PATH / STATUS_PATH below.
"""
from __future__ import annotations

import logging
import re
import threading
import time
import urllib.error
import urllib.request

log = logging.getLogger("vigil")

ALERT_PATH = "/alert"      # <-- change these two to match your ESP8266 sketch
STATUS_PATH = "/status"
TIMEOUT_S = 2.0

_NO_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # LAN device: ignore system proxy


def _base(address: str) -> str | None:
    """'192.168.1.50' or '192.168.1.50:8080' (http:// allowed) -> 'http://host[:port]', or None if invalid."""
    text = re.sub(r"^https?://", "", address.strip()).rstrip("/")
    host, _, port = text.partition(":")
    if not host or not re.fullmatch(r"[A-Za-z0-9.\-]+", host):
        return None
    if port and (not port.isdigit() or not 0 < int(port) < 65536):
        return None
    return f"http://{host}{':' + port if port else ''}"


def build_url(address: str, led: bool = True, buzzer: bool = True, path: str = ALERT_PATH) -> str | None:
    base = _base(address)
    return None if base is None else f"{base}{path}?led={int(led)}&buzzer={int(buzzer)}"


def check_status(address: str, timeout: float = 1.5) -> tuple[bool, str]:
    """Is the ESP8266 online? Blocking (use a thread). Returns (connected, message)."""
    base = _base(address)
    if base is None:
        return False, "Invalid device address"
    try:
        with _NO_PROXY.open(base + STATUS_PATH, timeout=timeout) as resp:
            return (True, "Connected") if 200 <= resp.status < 300 else (False, "Not connected")
    except (urllib.error.URLError, OSError, ValueError):
        return False, "Not connected"


def send_alert(address: str, led: bool = True, buzzer: bool = True,
               timeout: float = TIMEOUT_S) -> tuple[bool, str]:
    """Blocking call (use a thread). Returns (ok, short message)."""
    url = build_url(address, led, buzzer)
    if url is None:
        return False, "Invalid device address"
    try:
        with _NO_PROXY.open(url, timeout=timeout) as resp:
            return (True, "Alert sent") if 200 <= resp.status < 300 else (False, f"HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        return False, f"Device replied HTTP {e.code}"
    except (urllib.error.URLError, OSError, ValueError):
        return False, "Device unreachable"


class AlertSender:
    """Sends an alert to the ESP8266 for every live event, without ever blocking the UI.
    Reads device_address / led / buzzer from the SettingsStore at the moment of the event."""

    def __init__(self, settings, min_interval_s: float = 1.0):
        self._settings = settings
        self._min_interval = min_interval_s
        self._lock = threading.Lock()
        self._busy = False
        self._last = float("-inf")
        self.last_result: tuple[bool, str] | None = None

    def notify(self, event=None) -> None:
        """Connect this to LiveManager.event_detected."""
        address = str(self._settings.get("device_address")).strip()
        led, buzzer = bool(self._settings.get("led")), bool(self._settings.get("buzzer"))
        if not address or not (led or buzzer):
            return
        now = time.monotonic()
        with self._lock:
            if self._busy or now - self._last < self._min_interval:
                return
            self._busy, self._last = True, now
        threading.Thread(target=self._run, args=(address, led, buzzer, event),
                         name="vigil-alert", daemon=True).start()

    def _run(self, address: str, led: bool, buzzer: bool, event) -> None:
        try:
            ok, msg = send_alert(address, led, buzzer)
            self.last_result = (ok, msg)
            label = f"{event.type.value} " if event is not None else ""
            (log.info if ok else log.warning)("ESP8266 %s%s: %s", label, address, msg)
        finally:
            with self._lock:
                self._busy = False
