"""OpenCV video-source access.

Qt-free on purpose: shared by Live Camera mode now and Video Analysis mode later.
A *source* is an int (webcam index), an RTSP/HTTP URL, or a video file path.
"""
from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

# Must be set before the first RTSP capture is opened: prefer TCP (fewer dropped
# packets / grey frames than UDP on most CCTV hardware).
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")

import cv2  # noqa: E402
import numpy as np  # noqa: E402

Source = int | str

OPEN_TIMEOUT_MS = 5000
READ_TIMEOUT_MS = 5000


def parse_source(text: str) -> Source:
    """'0' -> 0 (webcam index); anything else is kept as a URL / file path."""
    text = str(text).strip()
    if not text:
        raise ValueError("Source is empty")
    return int(text) if text.isdigit() else text


def is_network_source(source: Source) -> bool:
    return isinstance(source, str) and "://" in source


def describe_source(source: Source | str) -> str:
    """Short, credential-free label for tables, e.g. 'rtsp://…/stream1'."""
    try:
        src = parse_source(str(source))
    except ValueError:
        return ""
    if isinstance(src, int):
        return f"Webcam {src}"
    if is_network_source(src):
        parts = urlsplit(src)
        return f"{parts.scheme}://…{parts.path or ''}"
    return os.path.basename(src)


class FrameSource:
    """Thin wrapper around cv2.VideoCapture. One instance per thread."""

    def __init__(self, source: Source):
        self._source = source
        self._cap: cv2.VideoCapture | None = None

    def open(self) -> bool:
        self.release()
        cap = self._create_capture()
        if cap is None or not cap.isOpened():
            if cap is not None:
                cap.release()
            return False
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # keep live latency low (best effort)
        except cv2.error:
            pass
        self._cap = cap
        return True

    def _create_capture(self) -> cv2.VideoCapture | None:
        src = self._source
        try:
            if isinstance(src, int):
                backends = [cv2.CAP_DSHOW, cv2.CAP_ANY] if sys.platform == "win32" else [cv2.CAP_ANY]
                for backend in backends:
                    cap = cv2.VideoCapture(src, backend)
                    if cap.isOpened():
                        return cap
                    cap.release()
                return None
            if is_network_source(src):
                params = [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, OPEN_TIMEOUT_MS,
                          cv2.CAP_PROP_READ_TIMEOUT_MSEC, READ_TIMEOUT_MS]
                return cv2.VideoCapture(src, cv2.CAP_FFMPEG, params)
            return cv2.VideoCapture(src)  # local file
        except cv2.error:
            return None

    def read(self) -> tuple[bool, np.ndarray | None]:
        if self._cap is None:
            return False, None
        try:
            ok, frame = self._cap.read()
        except cv2.error:
            return False, None
        return bool(ok), frame if ok else None

    @property
    def fps(self) -> float:
        return float(self._cap.get(cv2.CAP_PROP_FPS)) if self._cap else 0.0

    @property
    def frame_size(self) -> tuple[int, int]:
        if not self._cap:
            return 0, 0
        return (int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None


@dataclass(frozen=True)
class ProbeResult:
    ok: bool
    message: str
    width: int = 0
    height: int = 0


def probe_source(source: Source, read_attempts: int = 10) -> ProbeResult:
    """Blocking connectivity test (run it off the UI thread)."""
    fs = FrameSource(source)
    try:
        if not fs.open():
            return ProbeResult(False, "Cannot open source")
        for _ in range(read_attempts):
            ok, frame = fs.read()
            if ok and frame is not None:
                h, w = frame.shape[:2]
                return ProbeResult(True, "Connection OK", w, h)
            time.sleep(0.1)
        return ProbeResult(False, "No frames received")
    finally:
        fs.release()