"""
Train a binary Normal-vs-Violence video classifier for VIGIL.

Dataset layout:
    DATA_ROOT/
        Train/
            Normal/*.avi
            Violence/*.avi
        Test/
            Normal/*.avi
            Violence/*.avi

Example (PowerShell):
    python train_fight_model.py --data-root "D:\\SCVD\\SCVD_converted_sec_split"

The model is a MobileNetV2 frame classifier. It samples several frames from
each clip and averages their logits to produce one video-level prediction.
This is a baseline, not a motion-aware model.
"""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
from torchvision.models import MobileNet_V2_Weights, mobilenet_v2


CLASSES = ("Normal", "Violence")
VIDEO_EXTENSIONS = {".avi", ".mp4", ".mov", ".mkv"}


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def collect_videos(split_dir: Path) -> Tuple[List[Path], List[int]]:
    paths: List[Path] = []
    labels: List[int] = []

    for label, class_name in enumerate(CLASSES):
        class_dir = split_dir / class_name
        if not class_dir.is_dir():
            raise FileNotFoundError(
                f"Missing class folder: {class_dir}\n"
                f"Expected folders named: {', '.join(CLASSES)}"
            )

        class_files = sorted(
            p for p in class_dir.iterdir()
            if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
        )
        paths.extend(class_files)
        labels.extend([label] * len(class_files))

    if not paths:
        raise RuntimeError(f"No videos found under {split_dir}")

    return paths, labels


def stratified_train_val_indices(
    labels: List[int], val_fraction: float, seed: int
) -> Tuple[List[int], List[int]]:
    rng = random.Random(seed)
    train_indices: List[int] = []
    val_indices: List[int] = []

    for class_id in range(len(CLASSES)):
        class_indices = [i for i, y in enumerate(labels) if y == class_id]
        rng.shuffle(class_indices)

        if len(class_indices) < 2:
            raise RuntimeError(
                f"Need at least 2 training videos for class {CLASSES[class_id]}"
            )

        n_val = max(1, int(round(len(class_indices) * val_fraction)))
        n_val = min(n_val, len(class_indices) - 1)
        val_indices.extend(class_indices[:n_val])
        train_indices.extend(class_indices[n_val:])

    rng.shuffle(train_indices)
    rng.shuffle(val_indices)
    return train_indices, val_indices


def read_sampled_frames(
    video_path: Path, frames_per_video: int, image_size: int
) -> List[Image.Image]:
    """Decode evenly spaced frames, returning RGB PIL images."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"OpenCV could not open video: {video_path}")

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if frame_count <= 0:
        cap.release()
        raise RuntimeError(f"Video has no readable frames: {video_path}")

    indices = np.linspace(
        0, max(0, frame_count - 1),
        num=min(frames_per_video, frame_count),
        dtype=np.int64,
    )
    indices = sorted(set(int(i) for i in indices))

    frames: List[Image.Image] = []
    for frame_index in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = cap.read()
        if not ok or frame is None:
            continue

        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(frame).resize(
            (image_size, image_size), Image.Resampling.BILINEAR
        )
        frames.append(image)

    cap.release()

    if not frames:
        raise RuntimeError(f"Could not decode any frames from: {video_path}")

    # Keep a consistent number of frames for batching.
    while len(frames) < frames_per_video:
        frames.append(frames[-1].copy())

    return frames[:frames_per_video]


class VideoDataset(Dataset):
    def __init__(
        self,
        paths: List[Path],
        labels: List[int],
        frames_per_video: int,
        image_size: int,
        training: bool,
    ) -> None:
        self.paths = paths
        self.labels = labels
        self.frames_per_video = frames_per_video

        self.transform = transforms.Compose([
            transforms.RandomHorizontalFlip(p=0.5) if training
            else transforms.Lambda(lambda image: image),
            transforms.ColorJitter(
                brightness=0.12, contrast=0.12, saturation=0.08
            ) if training else transforms.Lambda(lambda image: image),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=(0.485, 0.456, 0.406),
                std=(0.229, 0.224, 0.225),
            ),
        ])
        self.frames_per_video = frames_per_video
        self.image_size = image_size

    def __len__(self) -> int:
        return len(self.paths)

    def __getitem__(self, index: int):
        frames = read_sampled_frames(
            self.paths[index], self.frames_per_video, self.image_size
        )
        tensor_frames = torch.stack([self.transform(frame) for frame in frames])
        return tensor_frames, torch.tensor(self.labels[index], dtype=torch.long)


class MobileNetVideoClassifier(nn.Module):
    def __init__(self, pretrained: bool = True) -> None:
        super().__init__()
        weights = MobileNet_V2_Weights.DEFAULT if pretrained else None
        self.network = mobilenet_v2(weights=weights)

        # Freeze the pretrained feature extractor; train only the final head.
        for parameter in self.network.features.parameters():
            parameter.requires_grad = False

        in_features = self.network.classifier[1].in_features
        self.network.classifier[1] = nn.Linear(in_features, len(CLASSES))

    def forward(self, video_frames: torch.Tensor) -> torch.Tensor:
        # Input: [batch, frames, channels, height, width]
        batch_size, frame_count, channels, height, width = video_frames.shape
        flat_frames = video_frames.reshape(
            batch_size * frame_count, channels, height, width
        )
        frame_logits = self.network(flat_frames)
        frame_logits = frame_logits.reshape(batch_size, frame_count, -1)
        return frame_logits.mean(dim=1)


def calculate_metrics(y_true: List[int], y_pred: List[int]) -> dict:
    confusion = np.zeros((2, 2), dtype=np.int64)
    for truth, prediction in zip(y_true, y_pred):
        confusion[truth, prediction] += 1

    accuracy = float(np.trace(confusion) / max(1, confusion.sum()))
    per_class = {}
    for class_id, class_name in enumerate(CLASSES):
        tp = int(confusion[class_id, class_id])
        fp = int(confusion[:, class_id].sum() - tp)
        fn = int(confusion[class_id, :].sum() - tp)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall else 0.0
        )
        per_class[class_name] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": int(confusion[class_id, :].sum()),
        }

    return {
        "accuracy": accuracy,
        "confusion_matrix": confusion.tolist(),
        "per_class": per_class,
    }


def run_evaluation(model, loader, device, criterion=None):
    model.eval()
    all_labels: List[int] = []
    all_predictions: List[int] = []
    total_loss = 0.0
    total_items = 0

    with torch.no_grad():
        for videos, labels in loader:
            videos = videos.to(device)
            labels = labels.to(device)
            logits = model(videos)

            if criterion is not None:
                total_loss += float(criterion(logits, labels).item()) * labels.size(0)

            predictions = logits.argmax(dim=1)
            all_labels.extend(labels.cpu().tolist())
            all_predictions.extend(predictions.cpu().tolist())
            total_items += labels.size(0)

    metrics = calculate_metrics(all_labels, all_predictions)
    average_loss = total_loss / max(1, total_items) if criterion else None
    return average_loss, metrics


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train VIGIL's MobileNetV2 Normal-vs-Violence baseline."
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path(r"D:\SCVD\SCVD_converted_sec_split"),
        help="Dataset root containing Train and Test folders.",
    )
    parser.add_argument("--output", type=Path, default=Path("models/fight_mobilenetv2.pth"))
    parser.add_argument("--frames", type=int, default=5)
    parser.add_argument("--image-size", type=int, default=160)
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--batch-size", type=int, default=2,
                        help="Number of videos per batch; keep small on an 8 GB CPU laptop.")
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--val-fraction", type=float, default=0.15)
    parser.add_argument("--patience", type=int, default=4)
    parser.add_argument("--workers", type=int, default=0,
                        help="0 is safest on Windows.")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if args.frames < 1 or args.image_size < 32 or args.epochs < 1:
        parser.error("--frames, --epochs must be >= 1 and --image-size must be >= 32")
    if not 0.05 <= args.val_fraction <= 0.4:
        parser.error("--val-fraction must be between 0.05 and 0.4")

    seed_everything(args.seed)
    torch.set_num_threads(max(1, min(4, torch.get_num_threads())))
    device = torch.device("cpu")
    print(f"Device: {device}")
    print(f"Dataset: {args.data_root.resolve()}")

    train_root = args.data_root / "Train"
    test_root = args.data_root / "Test"
    train_paths, train_labels = collect_videos(train_root)
    test_paths, test_labels = collect_videos(test_root)

    train_indices, val_indices = stratified_train_val_indices(
        train_labels, args.val_fraction, args.seed
    )
    subset_paths = [train_paths[i] for i in train_indices]
    subset_labels = [train_labels[i] for i in train_indices]
    val_paths = [train_paths[i] for i in val_indices]
    val_labels = [train_labels[i] for i in val_indices]

    print("\nDataset split:")
    for class_id, class_name in enumerate(CLASSES):
        train_count = sum(y == class_id for y in subset_labels)
        val_count = sum(y == class_id for y in val_labels)
        test_count = sum(y == class_id for y in test_labels)
        print(
            f"  {class_name:8s} train={train_count:4d} "
            f"validation={val_count:4d} test={test_count:4d}"
        )
    print(f"  Total    train={len(subset_paths)} "
          f"validation={len(val_paths)} test={len(test_paths)}")

    train_ds = VideoDataset(
        subset_paths, subset_labels, args.frames, args.image_size, training=True
    )
    val_ds = VideoDataset(
        val_paths, val_labels, args.frames, args.image_size, training=False
    )
    test_ds = VideoDataset(
        test_paths, test_labels, args.frames, args.image_size, training=False
    )

    loader_args = {
        "batch_size": args.batch_size,
        "num_workers": args.workers,
        "pin_memory": False,
    }
    train_loader = DataLoader(train_ds, shuffle=True, **loader_args)
    val_loader = DataLoader(val_ds, shuffle=False, **loader_args)
    test_loader = DataLoader(test_ds, shuffle=False, **loader_args)

    print("\nLoading pretrained MobileNetV2 weights...")
    model = MobileNetVideoClassifier(pretrained=True).to(device)

    # Balanced class weights reduce the effect of the modest class-count difference.
    class_counts = np.bincount(np.asarray(subset_labels), minlength=2)
    class_weights = len(subset_labels) / (
        len(CLASSES) * np.maximum(class_counts, 1)
    )
    criterion = nn.CrossEntropyLoss(
        weight=torch.tensor(class_weights, dtype=torch.float32, device=device)
    )
    optimizer = torch.optim.AdamW(
        (p for p in model.parameters() if p.requires_grad),
        lr=args.learning_rate,
        weight_decay=1e-4,
    )

    best_val_loss = float("inf")
    best_epoch = 0
    epochs_without_improvement = 0
    args.output.parent.mkdir(parents=True, exist_ok=True)

    print("\nStarting training...")
    for epoch in range(1, args.epochs + 1):
        model.train()
        running_loss = 0.0
        seen = 0
        start_time = time.time()

        for batch_index, (videos, labels) in enumerate(train_loader, start=1):
            videos = videos.to(device)
            labels = labels.to(device)

            optimizer.zero_grad(set_to_none=True)
            logits = model(videos)
            loss = criterion(logits, labels)
            loss.backward()
            optimizer.step()

            running_loss += float(loss.item()) * labels.size(0)
            seen += labels.size(0)

            if batch_index % 25 == 0 or batch_index == len(train_loader):
                print(
                    f"\rEpoch {epoch}/{args.epochs} "
                    f"batch {batch_index}/{len(train_loader)}",
                    end="",
                    flush=True,
                )

        train_loss = running_loss / max(1, seen)
        val_loss, val_metrics = run_evaluation(
            model, val_loader, device, criterion
        )
        elapsed = time.time() - start_time

        print(
            f"\nEpoch {epoch:02d}: train_loss={train_loss:.4f} "
            f"val_loss={val_loss:.4f} "
            f"val_accuracy={val_metrics['accuracy']:.4f} "
            f"time={elapsed:.1f}s"
        )

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_epoch = epoch
            epochs_without_improvement = 0
            torch.save({
                "model_state_dict": model.state_dict(),
                "classes": list(CLASSES),
                "architecture": "mobilenet_v2",
                "frames_per_video": args.frames,
                "image_size": args.image_size,
                "normalization": {
                    "mean": [0.485, 0.456, 0.406],
                    "std": [0.229, 0.224, 0.225],
                },
                "best_epoch": best_epoch,
                "validation_loss": best_val_loss,
                "validation_metrics": val_metrics,
                "dataset_root": str(args.data_root.resolve()),
                "seed": args.seed,
            }, args.output)
            print(f"  Saved best checkpoint: {args.output}")
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= args.patience:
                print("Early stopping: validation loss did not improve.")
                break

    print(f"\nBest epoch: {best_epoch}; best validation loss: {best_val_loss:.4f}")
    print("Loading best checkpoint for final untouched Test evaluation...")
    checkpoint = torch.load(args.output, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint["model_state_dict"])

    test_loss, test_metrics = run_evaluation(
        model, test_loader, device, criterion
    )
    print("\n========== FINAL TEST RESULTS ==========")
    print(f"Test loss: {test_loss:.4f}")
    print(f"Video-level accuracy: {test_metrics['accuracy']:.4f}")
    print("Confusion matrix (rows=true, columns=predicted; Normal, Violence):")
    print(np.asarray(test_metrics["confusion_matrix"]))
    for class_name, values in test_metrics["per_class"].items():
        print(
            f"{class_name:8s} "
            f"precision={values['precision']:.4f} "
            f"recall={values['recall']:.4f} "
            f"f1={values['f1']:.4f} "
            f"support={values['support']}"
        )

    metrics_path = args.output.with_name(args.output.stem + "_test_metrics.json")
    with metrics_path.open("w", encoding="utf-8") as file:
        json.dump(test_metrics, file, indent=2)

    print("\nSaved model:", args.output.resolve())
    print("Saved test metrics:", metrics_path.resolve())
    print(
        "\nReminder: this model averages independent frame predictions. "
        "It is a baseline violence classifier, not a temporal fight-action model."
    )


if __name__ == "__main__":
    main()
