/*
  VIGIL - ESP8266 alert device
  ---------------------------------------------------------------------------
  Board : NodeMCU / Wemos D1 mini (ESP8266). Arduino IDE -> install the
          "ESP8266 by ESP8266 Community" board package, then select your board.

  Wiring:
    Buzzer  (+)  -> D4            Buzzer (-) -> GND      (active buzzer)
    LED     (+)  -> 220 ohm -> D7 LED    (-) -> GND

  What the VIGIL app calls (same Wi-Fi / modem as this board):
    http://<esp-ip>/alert?led=1&buzzer=1   LED + buzzer on for ~5 s (optional &ms=3000)
    http://<esp-ip>/status                 online check -> app shows "Connected"
    http://<esp-ip>/off                    stop the alert
    http://<esp-ip>/                       small test page (status + Test / Stop buttons)

  After upload, open Serial Monitor (115200) to read the IP address, then type
  that IP in VIGIL -> Settings -> Device address -> Save Settings.
  Tip: in your modem, reserve this IP for the board (or set USE_STATIC_IP 1)
  so the address never changes.
*/
#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>

// ---------- EDIT THESE ----------
const char* WIFI_SSID = "YOUR_WIFI_NAME";
const char* WIFI_PASS = "YOUR_WIFI_PASSWORD";

#define USE_STATIC_IP 0                        // 1 = fixed IP below (must match your modem's network)
IPAddress STATIC_IP(192, 168, 1, 50);
IPAddress GATEWAY(192, 168, 1, 1);             // your modem
IPAddress SUBNET(255, 255, 255, 0);
IPAddress DNS_SERVER(192, 168, 1, 1);

const uint8_t LED_PIN    = D7;                 // GPIO13
const uint8_t BUZZER_PIN = D4;                 // GPIO2
const bool BUZZER_ACTIVE_HIGH = true;          // false if your buzzer module turns on with LOW
// --------------------------------

const unsigned long DEFAULT_ALERT_MS = 5000;   // how long one alert lasts
const unsigned long BEEP_MS = 250;             // buzzer beep on/off period

ESP8266WebServer server(80);
bool alertActive = false;
bool useLed = true, useBuzzer = true, beepOn = false;
unsigned long alertEnd = 0, lastBeep = 0;

void setLed(bool on)    { digitalWrite(LED_PIN, on ? HIGH : LOW); }
void setBuzzer(bool on) { digitalWrite(BUZZER_PIN, (on == BUZZER_ACTIVE_HIGH) ? HIGH : LOW); }

void stopAlert() {
  alertActive = false;
  beepOn = false;
  setLed(false);
  setBuzzer(false);
}

void startAlert(bool led, bool buzzer, unsigned long ms) {
  useLed = led;
  useBuzzer = buzzer;
  alertActive = true;
  alertEnd = millis() + ms;
  lastBeep = millis();
  beepOn = buzzer;
  setLed(led);
  setBuzzer(buzzer);
}

void handleAlert() {
  bool led    = server.hasArg("led")    ? server.arg("led")    != "0" : true;
  bool buzzer = server.hasArg("buzzer") ? server.arg("buzzer") != "0" : true;
  unsigned long ms = server.hasArg("ms") ? (unsigned long)server.arg("ms").toInt() : DEFAULT_ALERT_MS;
  if (ms < 500 || ms > 60000) ms = DEFAULT_ALERT_MS;
  startAlert(led, buzzer, ms);
  server.send(200, "application/json", "{\"ok\":true}");
}

void handleOff() {
  stopAlert();
  server.send(200, "application/json", "{\"ok\":true}");
}

void handleStatus() {
  String json = "{\"device\":\"vigil-esp8266\",\"ip\":\"" + WiFi.localIP().toString() +
                "\",\"alert\":" + (alertActive ? "true" : "false") + "}";
  server.send(200, "application/json", json);
}

void handleRoot() {
  String html =
    "<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'>"
    "<title>VIGIL ESP8266</title><style>body{font-family:sans-serif;background:#1a1118;color:#f2e7e2;"
    "padding:24px}a{display:inline-block;margin:8px 8px 0 0;padding:12px 18px;border-radius:8px;"
    "background:#7b48c2;color:#fff;text-decoration:none}.s{background:#3a2849}</style></head><body>"
    "<h2>VIGIL alert device</h2><p>Status: <b>online</b><br>IP: " + WiFi.localIP().toString() +
    "<br>Alert: " + String(alertActive ? "ACTIVE" : "idle") + "</p>"
    "<a href='/alert?led=1&buzzer=1'>Test alert</a><a class='s' href='/off'>Stop</a></body></html>";
  server.send(200, "text/html", html);
}

void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
#if USE_STATIC_IP
  WiFi.config(STATIC_IP, GATEWAY, SUBNET, DNS_SERVER);
#endif
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Connecting to Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("Connected. Type this IP in VIGIL Settings: ");
  Serial.println(WiFi.localIP());
}

void setup() {
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  stopAlert();                                  // note: D4 (GPIO2) is HIGH during boot, a short chirp is normal
  Serial.begin(115200);
  connectWifi();
  server.on("/", handleRoot);
  server.on("/alert", handleAlert);
  server.on("/off", handleOff);
  server.on("/status", handleStatus);
  server.begin();
  Serial.println("HTTP server started");
}

void loop() {
  server.handleClient();
  if (alertActive) {
    unsigned long now = millis();
    if ((long)(now - alertEnd) >= 0) {
      stopAlert();
    } else if (useBuzzer && (now - lastBeep) >= BEEP_MS) {   // beep-beep pattern
      lastBeep = now;
      beepOn = !beepOn;
      setBuzzer(beepOn);
    }
  }
}
