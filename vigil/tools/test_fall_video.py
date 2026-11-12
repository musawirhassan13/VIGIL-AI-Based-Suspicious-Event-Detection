"""
VIGIL Fall Video Test
Pipeline: RGB video -> YOLO -> PersonTracker -> FallRule -> EventEngine

For side-by-side Depth + RGB videos, the default view is the RIGHT half.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import cv2

from vigil.core.ai.detector import YoloPersonDetector
from vigil.core.ai.tracker import PersonTracker
from vigil.core.ai.event_engine import EventEngine, build_default_rules
from vigil.core.events import EventType


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args():
    parser = argparse.ArgumentParser(description="Test VIGIL fall detection on a video.")
    parser.add_argument("video", help="Input video path")
    parser.add_argument("--view", choices=["right", "left", "full"], default="right",
                        help="Which part of a side-by-side video to process")
    parser.add_argument("--out", default=None, help="Annotated output video path")
    parser.add_argument("--model", default=None, help="YOLO model path")
    parser.add_argument("--conf", type=float, default=0.35)
    parser.add_argument("--imgsz", type=int, default=416)
    parser.add_argument("--sample-fps", type=float, default=5.0)
    parser.add_argument("--device", default="cpu")
    return parser.parse_args()


def select_view(frame, view):
    if view == "full":
        return frame

    height, width = frame.shape[:2]
    middle = width // 2

    if view == "right":
        return frame[:, middle:].copy()

    return frame[:, :middle].copy()


def draw_detections(frame, detections):
    for det in detections:
        x1, y1, x2, y2 = map(int, det.box)
        track_id = det.track_id if det.track_id is not None else "?"
        confidence = det.confidence

        cv2.rectangle(frame, (x1, y1), (x2, y2), (180, 70, 220), 2)
        cv2.putText(
            frame,
            f"Person {track_id} | {confidence:.2f}",
            (x1, max(20, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (180, 70, 220),
            2,
        )


def main():
    args = parse_args()

    video_path = Path(args.video)
    if not video_path.is_absolute():
        video_path = PROJECT_ROOT / video_path

    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    model_path = args.model
    if model_path is None:
        local_model = PROJECT_ROOT / "models" / "yolov8n.pt"
        model_path = str(local_model) if local_model.exists() else "yolov8n.pt"

    output_path = (
        Path(args.out) if args.out
        else video_path.with_name(video_path.stem + "_fall_test.mp4")
    )
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    source_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / source_fps if source_fps > 0 else 0

    ok, first_frame = cap.read()
    if not ok:
        raise RuntimeError("Video has no readable frames.")

    first_view = select_view(first_frame, args.view)
    height, width = first_view.shape[:2]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(output_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        source_fps,
        (width, height),
    )

    if not writer.isOpened():
        raise RuntimeError(f"Cannot create output video: {output_path}")

    print("\n========== VIGIL FALL VIDEO TEST ==========")
    print(f"Video       : {video_path.name}")
    print(f"Resolution  : {width}x{height}")
    print(f"FPS         : {source_fps:.1f}")
    print(f"Duration    : {duration:.2f}s")
    print(f"View        : {args.view}")
    print(f"Sample FPS  : {args.sample_fps}")
    print("Loading YOLO model...")

    detector = YoloPersonDetector(
        model_path=model_path,
        conf=args.conf,
        imgsz=args.imgsz,
        device=args.device,
    )

    tracker = PersonTracker()
    fall_engine = EventEngine(
        source_id="fall_test",
        source_label=video_path.name,
        rules=build_default_rules(),
        min_confidence=0.0,
        enabled={EventType.FALL},
    )

    sample_interval = 1.0 / max(0.5, args.sample_fps)
    last_inference_time = -math.inf
    last_detections = []
    frame_index = 0
    sampled_frames = 0
    person_frames = 0
    fall_events = []

    print("Processing video...\n")

    try:
        while True:
            if frame_index == 0:
                frame = first_frame
                ok = True
            else:
                ok, frame = cap.read()

            if not ok:
                break

            video_time = frame_index / source_fps
            view_frame = select_view(frame, args.view)

            if video_time - last_inference_time >= sample_interval:
                detections = detector.detect(view_frame)
                tracked = tracker.update(detections, frame_index)

                last_detections = tracked
                sampled_frames += 1
                person_frames += bool(tracked)
                last_inference_time = video_time

                events = fall_engine.process(
                    tracker=tracker,
                    detections=tracked,
                    frame_index=frame_index,
                    now_s=video_time,
                    frame_size=(width, height),
                    video_time_s=video_time,
                )

                for event in events:
                    fall_events.append(event)
                    print(
                        f"[FALL ALERT] time={video_time:.2f}s "
                        f"confidence={event.confidence:.2f} "
                        f"frame={frame_index}"
                    )

            draw_detections(view_frame, last_detections)

            status = "FALL DETECTED" if fall_events else "MONITORING"
            color = (0, 0, 255) if fall_events else (0, 200, 0)

            cv2.putText(
                view_frame,
                status,
                (15, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                color,
                2,
            )

            writer.write(view_frame)
            frame_index += 1

    finally:
        cap.release()
        writer.release()

    print("\n========== TEST SUMMARY ==========")
    print(f"Frames processed : {frame_index}")
    print(f"Frames sampled   : {sampled_frames}")
    print(f"Frames with people: {person_frames}")
    print(f"Fall alerts      : {len(fall_events)}")
    print(f"Output video     : {output_path}")
    print("==================================\n")


if __name__ == "__main__":
    main()