"""Hardware test: a tiny local web server plays the ESP8266 and records the requests."""
import os
import sys
import tempfile
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication  # noqa: E402

from vigil import theme  # noqa: E402
from vigil.core.alert_device import AlertSender, build_url, check_status, send_alert  # noqa: E402
from vigil.device_monitor import CONNECTED, DISCONNECTED, NO_ADDRESS, DeviceMonitor  # noqa: E402
from vigil.sidebar import Sidebar  # noqa: E402
from vigil.core.events import Event, EventType  # noqa: E402
from vigil.pages.settings import SettingsPage  # noqa: E402
from vigil.settings_store import SettingsStore  # noqa: E402

app = QApplication([])
theme.apply(app)
HITS: list[str] = []
STATUS = [200]


class Fake(BaseHTTPRequestHandler):
    def do_GET(self):
        HITS.append(self.path)
        self.send_response(STATUS[0])
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *a):
        pass


server = HTTPServer(("127.0.0.1", 0), Fake)
threading.Thread(target=server.serve_forever, daemon=True).start()
ADDR = f"127.0.0.1:{server.server_port}"


def wait(cond, secs=5.0):
    t = time.time()
    while not cond() and time.time() - t < secs:
        app.processEvents()
        time.sleep(0.01)
    return cond()


def settings(**kw):
    s = SettingsStore(Path(tempfile.mkdtemp()) / "s.json")
    s.update({"device_address": ADDR, "led": True, "buzzer": True, **kw})
    return s


def ev():
    return Event(EventType.CROWD, 0.8, "1", "CAM 01", datetime.now(), 1)


def test_build_url_and_send():
    assert build_url("192.168.1.50") == "http://192.168.1.50/alert?led=1&buzzer=1"
    assert build_url("http://192.168.1.50:8080/", led=False) == "http://192.168.1.50:8080/alert?led=0&buzzer=1"
    assert build_url("bad host") is None and build_url("1.2.3.4:99999") is None and build_url("") is None
    HITS.clear()
    assert send_alert(ADDR) == (True, "Alert sent") and HITS == ["/alert?led=1&buzzer=1"]
    assert send_alert(ADDR, led=False, buzzer=True)[0] and HITS[-1] == "/alert?led=0&buzzer=1"
    STATUS[0] = 404
    assert send_alert(ADDR) == (False, "Device replied HTTP 404")
    STATUS[0] = 200
    assert send_alert("127.0.0.1:9", timeout=1.0) == (False, "Device unreachable")
    assert send_alert("not a host")[1] == "Invalid device address"


def test_alert_sender():
    HITS.clear()
    s = settings()
    sender = AlertSender(s, min_interval_s=0.3)
    sender.notify(ev())
    assert wait(lambda: len(HITS) == 1) and HITS[0] == "/alert?led=1&buzzer=1"
    assert wait(lambda: sender.last_result == (True, "Alert sent"))
    sender.notify(ev())                                   # too soon: ignored
    time.sleep(0.2)
    assert len(HITS) == 1
    time.sleep(0.2)
    sender.notify(ev())
    assert wait(lambda: len(HITS) == 2)
    s.update({"led": False, "buzzer": False})
    time.sleep(0.4)
    sender.notify(ev())                                   # both off: nothing sent
    s.update({"led": True, "buzzer": True, "device_address": ""})
    time.sleep(0.4)
    sender.notify(ev())                                   # no address: nothing sent
    time.sleep(0.3)
    assert len(HITS) == 2
    dead = AlertSender(settings(device_address="127.0.0.1:9"))
    dead.notify(ev())                                     # unreachable device must never raise
    assert wait(lambda: dead.last_result == (False, "Device unreachable"))


def test_settings_test_device_button():
    HITS.clear()
    page = SettingsPage(settings(buzzer=False))
    page.show()
    page._test_btn.click()
    assert wait(lambda: page._test_result.text() == "Alert sent") and HITS == ["/alert?led=1&buzzer=0"]
    page.addr.setText("127.0.0.1:9")
    page._test_btn.click()
    assert wait(lambda: page._test_result.text() == "Device unreachable")
    page.shutdown()


def test_main_window_live_event_reaches_device():
    from vigil.main_window import MainWindow
    HITS.clear()
    w = MainWindow()
    w.show()
    w.settings.update({"device_address": ADDR, "led": True, "buzzer": True})
    w.live.event_detected.emit(ev())                      # as if a camera raised an alert
    assert wait(lambda: HITS == ["/alert?led=1&buzzer=1"])
    assert len(w.incidents.all()) == 1                    # and it still reaches Incident History
    w.close()


def test_check_status():
    HITS.clear()
    assert check_status(ADDR) == (True, "Connected") and HITS == ["/status"]
    assert check_status("127.0.0.1:9", timeout=1.0) == (False, "Not connected")
    assert check_status("bad host")[1] == "Invalid device address"
    STATUS[0] = 500
    assert check_status(ADDR)[0] is False
    STATUS[0] = 200


def test_device_monitor_states_sidebar_and_settings_badge():
    s = settings(device_address="")
    mon = DeviceMonitor(s)
    seen = []
    mon.status_changed.connect(lambda st, ad: seen.append(st))
    bar = Sidebar()
    mon.status_changed.connect(lambda st, ad: bar.set_device_status(st))
    page = SettingsPage(s, mon)
    page.show()
    mon.start()
    assert wait(lambda: seen == [NO_ADDRESS]) and bar._device.text() == "ESP8266 · No IP set"
    assert not page._conn.isVisible()
    s.update({"device_address": ADDR})
    mon.refresh()
    assert wait(lambda: seen[-1] == CONNECTED) and bar._device.text() == "ESP8266 · Connected"
    assert page._conn.isVisible() and page._conn.text() == "Connected"
    s.update({"device_address": "127.0.0.1:9"})
    mon.refresh()
    assert wait(lambda: seen[-1] == DISCONNECTED) and bar._device.text() == "ESP8266 · Not connected"
    assert page._conn.text() == "Not connected"
    page.addr.setText(ADDR)                                # Save Settings re-checks immediately
    page._save()
    assert wait(lambda: seen[-1] == CONNECTED) and page._conn.text() == "Connected"
    mon.stop()
    assert mon.wait(4000)


def test_main_window_shows_real_connection():
    from vigil.main_window import MainWindow
    w = MainWindow()
    w.show()
    w.settings.update({"device_address": ADDR})
    w.device.refresh()
    assert wait(lambda: w.sidebar._device.text() == "ESP8266 · Connected")
    w.settings.update({"device_address": "127.0.0.1:9"})
    w.device.refresh()
    assert wait(lambda: w.sidebar._device.text() == "ESP8266 · Not connected")
    w.close()
    assert w.device.isFinished()


if __name__ == "__main__":
    for fn in (test_build_url_and_send, test_alert_sender, test_settings_test_device_button,
               test_main_window_live_event_reaches_device, test_check_status,
               test_device_monitor_states_sidebar_and_settings_badge, test_main_window_shows_real_connection):
        fn()
        print("ok", fn.__name__)
    for w in app.topLevelWidgets():
        w.close()
        w.deleteLater()
    app.processEvents()
    print("ALL OK")
