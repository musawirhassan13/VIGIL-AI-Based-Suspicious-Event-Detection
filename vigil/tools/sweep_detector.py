"""Which YOLO setting actually sees the people in YOUR video?

Samples a few frames and prints the average number of people found for different confidence /
image-size / model combinations. Use it when a CCTV clip shows many people but VIGIL finds few.

    python tools/sweep_detector.py n001_converted.avi
    python tools/sweep_detector.py n001_converted.avi --weights models/yolov8n.pt yolov8s.pt --frames 15
"""
import argparse
import sys

import cv2
from ultralytics import YOLO

CONFS = (0.4, 0.25, 0.15)
SIZES = (640, 960, 1280)


def sample_frames(path: str, count: int):
    cap = cv2.VideoCapture(path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    wanted = [int(total * (i + 0.5) / count) for i in range(count)] if total > 0 else list(range(count))
    frames = []
    for idx in wanted:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if ok:
            frames.append(frame)
    cap.release()
    return frames


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--weights", nargs="+", default=["yolov8n.pt"])
    ap.add_argument("--frames", type=int, default=12)
    a = ap.parse_args()

    frames = sample_frames(a.video, a.frames)
    if not frames:
        print("Could not read any frame from the video")
        return 1
    h, w = frames[0].shape[:2]
    print(f"{a.video}: {w}x{h}, {len(frames)} frames sampled\n")

    for weights in a.weights:
        model = YOLO(weights)
        print(f"== {weights} ==")
        print(f"{'imgsz':>6} {'conf':>5}   avg people   max")
        for size in SIZES:
            for conf in CONFS:
                counts = [len(model.predict(f, classes=[0], conf=conf, imgsz=size, verbose=False)[0].boxes)
                          for f in frames]
                print(f"{size:>6} {conf:>5}   {sum(counts) / len(counts):>10.1f}   {max(counts):>3}")
        print()
    print("Pick the cheapest row whose 'avg people' is close to what you count by eye.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
