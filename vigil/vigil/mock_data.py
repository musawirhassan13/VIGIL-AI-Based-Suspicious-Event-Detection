"""Static mock data. Replaced by the SQLite layer in a later phase."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Camera:
    name: str
    location: str
    stream: str
    online: bool


@dataclass(frozen=True)
class Incident:
    time: str
    source: str
    event: str
    confidence: int
    status: str  # Pending | Confirmed | False alarm


@dataclass(frozen=True)
class VideoEvent:
    event: str
    timestamp: str


STATS = [("Cameras online", "4 / 6"), ("Alerts today", "12"),
         ("Pending review", "5"), ("Videos analyzed", "3")]

CAMERAS = [
    Camera("CAM 01", "Main Gate", "rtsp://…/stream1", True),
    Camera("CAM 02", "Lab Corridor", "rtsp://…/stream2", True),
    Camera("CAM 03", "Cafeteria", "rtsp://…/stream3", True),
    Camera("CAM 04", "Library Entrance", "rtsp://…/stream4", False),
]
NEW_CAMERA_DRAFT = ("CAM 05", "Parking Lot A", "rtsp://user:pass@192.168.1.20:554/stream1")

# (title, "Source · time")
ALERTS = [
    ("Possible fight", "Main Gate · 14:32"),
    ("Restricted area entry", "Lab Corridor · 14:05"),
    ("Sudden fall", "Cafeteria · 13:48"),
    ("Crowd formation", "Library Entrance · 12:10"),
]

SYSTEM_STATUS = ["OpenCV", "YOLO", "Tracker", "SQLite", "ESP8266"]

VIDEO_FILE = "cctv_main_gate_yesterday.mp4"
VIDEO_PROGRESS = 0.68
VIDEO_MARKERS = [0.18, 0.34, 0.52]
VIDEO_EVENTS = [VideoEvent("Possible fight", "00:14:32"),
                VideoEvent("Sudden fall", "00:27:10"),
                VideoEvent("Restricted area entry", "00:41:55")]

INCIDENTS = [
    Incident("14:32", "Main Gate", "Possible fight", 87, "Pending"),
    Incident("14:05", "Lab Corridor", "Restricted area", 92, "Confirmed"),
    Incident("13:48", "Cafeteria", "Sudden fall", 74, "Pending"),
    Incident("12:10", "Library", "Crowd formation", 69, "False alarm"),
    Incident("Upload", "Video file", "Possible fight", 81, "Pending"),
]
STATUS_KIND = {"Pending": "red", "Confirmed": "green", "False alarm": "purple"}

# Fake detections: (x, y, w, h) as fractions of the frame + "alert" | "normal"
SCENE_FIGHT = [(0.30, 0.25, 0.166, 0.56, "alert"), (0.50, 0.30, 0.145, 0.51, "alert"),
               (0.72, 0.35, 0.105, 0.48, "normal")]
SCENE_PAIR = [(0.30, 0.25, 0.17, 0.56, "alert"), (0.51, 0.29, 0.15, 0.50, "alert")]
SCENE_SINGLE = [(0.40, 0.28, 0.13, 0.62, "normal")]
SCENE_TWO_CALM = [(0.20, 0.38, 0.11, 0.58, "normal"), (0.55, 0.33, 0.11, 0.60, "normal")]
