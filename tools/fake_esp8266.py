"""Pretends to be the ESP8266 so you can test VIGIL without hardware.
Run:  python tools/fake_esp8266.py        (listens on port 8080)
In VIGIL -> Settings -> Device address:  127.0.0.1:8080
"""
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/status":
            print(".", end="", flush=True)          # a dot = VIGIL checked that the device is online
        else:
            print(f"\n{datetime.now():%H:%M:%S}  GET {self.path}", flush=True)
        body = b"{\"ok\":true}"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


print(f"Fake ESP8266 listening on http://127.0.0.1:{PORT}  (Ctrl+C to stop)")
HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()