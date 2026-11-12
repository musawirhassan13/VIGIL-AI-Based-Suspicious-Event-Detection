"""A1-A3 harness: run YOLO person detection + tracking + event rules (crowd, restricted area, fall) on a video file, no UI.

    python tools/detect_video.py clip.mp4 --out annotated.mp4
    python tools/detect_video.py clip.mp4 --zone 0.5,0.4,1.0,1.0 --min-crowd 4
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2  # noqa: E402

from vigil.core.ai.detector import YoloPersonDetector  # noqa: E402
from vigil.core.ai.draw import draw_detections, draw_zones  # noqa: E402
from vigil.core.ai.event_engine import EventEngine  # noqa: E402
from vigil.core.ai.rules import CrowdRule, FallRule, RestrictedAreaRule, Zone  # noqa: E402
from vigil.core.ai.tracker import PersonTracker  # noqa: E402
from vigil.core.ai.video_scan import scan_video, video_info  # noqa: E402


def fmt_time(seconds: float) -> str:
    return f"{int(seconds // 60):02d}:{seconds % 60:04.1f}"


def parse_zone(text: str, index: int) -> Zone:
    x1, y1, x2, y2 = (float(v) for v in text.split(","))
    return Zone.rect(f"Zone {index + 1}", x1, y1, x2, y2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--weights", default="yolov8n.pt")
    ap.add_argument("--conf", type=float, default=0.4, help="YOLO person confidence")
    ap.add_argument("--fps", type=float, default=10.0, help="sampling rate")
    ap.add_argument("--out", help="write annotated video here")
    ap.add_argument("--max-frames", type=int)
    ap.add_argument("--no-track", action="store_true", help="disable tracking (also disables events)")
    ap.add_argument("--zone", action="append", default=[],
                    help="restricted zone x1,y1,x2,y2 as 0-1 fractions of the frame (repeatable)")
    ap.add_argument("--min-crowd", type=int, default=5, help="people needed for Crowd formation")
    ap.add_argument("--min-conf", type=float, default=0.7, help="event confidence threshold")
    a = ap.parse_args()

    info = video_info(a.video)
    print(f"{a.video}: {info.width}x{info.height} @ {info.fps:.1f} fps, {info.duration_s:.1f}s")
    det = YoloPersonDetector(a.weights, conf=a.conf)
    det.warmup()

    zones = [parse_zone(z, i) for i, z in enumerate(a.zone)]
    tracker = None if a.no_track else PersonTracker()
    engine = None if a.no_track else EventEngine(
        "upload", "Video file", [CrowdRule(min_people=a.min_crowd), RestrictedAreaRule(zones), FallRule()],
        min_confidence=a.min_conf)

    writer = None
    if a.out:
        writer = cv2.VideoWriter(a.out, cv2.VideoWriter_fourcc(*"mp4v"), a.fps, (info.width, info.height))
    counts, ids, found, t0 = [], set(), [], time.perf_counter()
    for r in scan_video(a.video, det, a.fps, a.max_frames, tracker):
        counts.append(len(r.detections))
        ids.update(d.track_id for d in r.detections if d.track_id is not None)
        events = engine.process(tracker, r.detections, r.frame_index, r.time_s,
                                (info.width, info.height), r.time_s) if engine else []
        for ev in events:
            found.append(ev)
            print(f"  EVENT {fmt_time(r.time_s)}  {ev.type.value}  {ev.confidence_pct}%")
        if writer:
            draw_zones(r.frame, zones)
            draw_detections(r.frame, r.detections)
            for ev in events:
                draw_detections(r.frame, ev.detections, alert=True)
            writer.write(r.frame)
    elapsed = time.perf_counter() - t0
    if writer:
        writer.release()
    n = len(counts)
    if not n:
        print("No frames processed")
        return 1
    print(f"sampled {n} frames | people avg {sum(counts) / n:.1f} max {max(counts)} | "
          f"{elapsed / n * 1000:.0f} ms/frame ({n / elapsed:.1f} fps)")
    if tracker is not None:
        print(f"unique people tracked (IDs): {len(ids)} | events found: {len(found)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())