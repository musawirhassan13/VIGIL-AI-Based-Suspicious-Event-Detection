"""Run a detector over a video file at a sampling rate.

Video Analysis can automatically select the RGB half of side-by-side
Depth + RGB recordings. Other videos remain full-frame.
"""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import cv2
import numpy as np

from ..capture import FrameSource
from ..events import Detection
from .detector import PersonDetector
from .tracker import PersonTracker


@dataclass(frozen=True)
class VideoInfo:
    fps: float
    frame_count: int
    width: int
    height: int

    @property
    def duration_s(self) -> float:
        return self.frame_count / self.fps if self.fps else 0.0


@dataclass(frozen=True)
class FrameResult:
    frame_index: int
    time_s: float
    detections: list[Detection]
    frame: np.ndarray


def video_info(path: str) -> VideoInfo:
    cap = cv2.VideoCapture(path)
    try:
        if not cap.isOpened():
            raise FileNotFoundError(f"Cannot open video: {path}")
        return VideoInfo(
            float(cap.get(cv2.CAP_PROP_FPS)) or 25.0,
            int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )
    finally:
        cap.release()


def _select_view(frame: np.ndarray, view: str) -> np.ndarray:
    """Return the requested view. Auto selects right half for wide SBS clips."""
    if view == "full":
        return frame
    if view == "right":
        return frame[:, frame.shape[1] // 2:].copy()
    if view == "left":
        return frame[:, :frame.shape[1] // 2].copy()
    if view != "auto":
        raise ValueError("view must be 'auto', 'full', 'left', or 'right'")

    height, width = frame.shape[:2]
    # The supplied Depth + RGB sample is 640x240 (2.67:1).
    # Normal 16:9 CCTV footage is not cropped by this threshold.
    if height > 0 and width / height >= 2.4:
        return frame[:, width // 2:].copy()
    return frame


def scan_video(
    path: str,
    detector: PersonDetector,
    sample_fps: float = 10.0,
    max_frames: int | None = None,
    tracker: PersonTracker | None = None,
    view: str = "full",
) -> Iterator[FrameResult]:
    """Yield sampled frames; optional tracking adds a stable track_id."""
    info = video_info(path)
    step = max(1, round(info.fps / max(0.1, sample_fps)))
    source = FrameSource(path)
    if not source.open():
        raise FileNotFoundError(f"Cannot open video: {path}")
    if tracker is not None:
        tracker.reset()

    index, sampled = 0, 0
    try:
        while max_frames is None or sampled < max_frames:
            ok, frame = source.read()
            if not ok or frame is None:
                break
            if index % step == 0:
                selected_frame = _select_view(frame, view)
                detections = detector.detect(selected_frame)
                if tracker is not None:
                    detections = tracker.update(detections, index)
                yield FrameResult(index, index / info.fps, detections, selected_frame)
                sampled += 1
            index += 1
    finally:
        source.release()
