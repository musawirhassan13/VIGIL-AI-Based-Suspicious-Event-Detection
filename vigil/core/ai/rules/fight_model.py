"""MobileNetV2 violence classifier rule used by VIGIL.

The checkpoint is produced by train_fight_model.py. This is a frame-based
Normal-vs-Violence baseline, not a temporal fight-action recognition model.
If the checkpoint cannot be loaded, the original motion-based FightRule is
used as a safe fallback.
"""
from __future__ import annotations

from collections import deque
from pathlib import Path
import warnings

import cv2
import numpy as np
from PIL import Image

from ...events import EventType
from .base import FrameContext, Rule, RuleHit
from .fight import FightRule

CLASSES = ("Normal", "Violence")
DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[4] / "models" / "fight_mobilenetv2.pth"


class FightModelRule(Rule):
    type = EventType.FIGHT
    cooldown_s = 30.0

    def __init__(
        self,
        model_path: str | Path = DEFAULT_MODEL_PATH,
        violence_threshold: float = 0.70,
        sample_interval_s: float = 0.24,
        inference_interval_s: float = 1.0,
    ) -> None:
        self.model_path = Path(model_path)
        self.violence_threshold = float(violence_threshold)
        self.sample_interval_s = float(sample_interval_s)
        self.inference_interval_s = float(inference_interval_s)
        self._fallback = FightRule()
        self._model = None
        self._torch = None
        self._frames = deque()
        self._frames_per_video = 5
        self._image_size = 160
        self._mean = (0.485, 0.456, 0.406)
        self._std = (0.229, 0.224, 0.225)
        self._violence_index = 1
        self._last_sample_s = float("-inf")
        self._last_inference_s = float("-inf")
        self._load_error: str | None = None
        self._warned = False

    def _load_model(self) -> None:
        if self._model is not None or self._load_error is not None:
            return

        try:
            import torch
            import torch.nn as nn
            from torchvision.models import mobilenet_v2

            if not self.model_path.is_file():
                raise FileNotFoundError(
                    f"Fight model checkpoint not found: {self.model_path}"
                )

            checkpoint = torch.load(
                self.model_path, map_location="cpu", weights_only=False
            )
            if checkpoint.get("architecture") != "mobilenet_v2":
                raise ValueError("Checkpoint architecture is not mobilenet_v2")

            classes = tuple(checkpoint.get("classes", CLASSES))
            if "Violence" not in classes:
                raise ValueError(f"Checkpoint classes do not contain Violence: {classes}")

            class MobileNetVideoClassifier(nn.Module):
                def __init__(self) -> None:
                    super().__init__()
                    self.network = mobilenet_v2(weights=None)
                    in_features = self.network.classifier[1].in_features
                    self.network.classifier[1] = nn.Linear(in_features, len(classes))

                def forward(self, video_frames):
                    batch_size, frame_count, channels, height, width = video_frames.shape
                    flat_frames = video_frames.reshape(
                        batch_size * frame_count, channels, height, width
                    )
                    frame_logits = self.network(flat_frames)
                    frame_logits = frame_logits.reshape(batch_size, frame_count, -1)
                    return frame_logits.mean(dim=1)

            model = MobileNetVideoClassifier()
            model.load_state_dict(checkpoint["model_state_dict"], strict=True)
            model.eval()

            self._frames_per_video = int(checkpoint.get("frames_per_video", 5))
            self._image_size = int(checkpoint.get("image_size", 160))
            normalization = checkpoint.get("normalization", {})
            self._mean = tuple(normalization.get("mean", self._mean))
            self._std = tuple(normalization.get("std", self._std))
            if self._frames_per_video < 1 or self._image_size < 1:
                raise ValueError("Invalid frames_per_video or image_size in checkpoint")

            self._violence_index = classes.index("Violence")
            self._frames = deque(maxlen=self._frames_per_video)
            self._torch = torch
            self._model = model

        except Exception as exc:  # noqa: BLE001 - use the established rule if model is unavailable
            self._load_error = f"{type(exc).__name__}: {exc}"
            if not self._warned:
                warnings.warn(
                    f"VIGIL fight model unavailable ({self._load_error}); "
                    "falling back to the existing motion-based FightRule.",
                    RuntimeWarning,
                    stacklevel=2,
                )
                self._warned = True

    def _preprocess(self, frame: object):
        if not isinstance(frame, np.ndarray) or frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError("FightModelRule expects a BGR HxWx3 numpy frame")

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb).resize(
            (self._image_size, self._image_size), Image.Resampling.BILINEAR
        )
        array = np.asarray(image, dtype=np.float32) / 255.0
        tensor = self._torch.from_numpy(array.copy()).permute(2, 0, 1)
        mean = self._torch.tensor(self._mean, dtype=tensor.dtype).view(3, 1, 1)
        std = self._torch.tensor(self._std, dtype=tensor.dtype).view(3, 1, 1)
        return (tensor - mean) / std

    def evaluate(self, ctx: FrameContext) -> list[RuleHit]:
        # Older call sites without frames continue to use the original rule.
        if ctx.frame is None:
            return self._fallback.evaluate(ctx)

        self._load_model()
        if self._model is None:
            return self._fallback.evaluate(ctx)

        if ctx.now_s - self._last_sample_s >= self.sample_interval_s:
            self._frames.append(self._preprocess(ctx.frame))
            self._last_sample_s = ctx.now_s

        if len(self._frames) < self._frames_per_video:
            return []
        if ctx.now_s - self._last_inference_s < self.inference_interval_s:
            return []

        self._last_inference_s = ctx.now_s
        video_tensor = self._torch.stack(list(self._frames), dim=0).unsqueeze(0)

        with self._torch.inference_mode():
            logits = self._model(video_tensor)
            probabilities = self._torch.softmax(logits, dim=1)[0]
            violence_confidence = float(probabilities[self._violence_index].item())

        if violence_confidence < self.violence_threshold:
            return []

        involved = tuple(
            sorted(ctx.detections, key=lambda detection: detection.confidence, reverse=True)[:2]
        )
        return [
            RuleHit(
                EventType.FIGHT,
                violence_confidence,
                involved,
                "violence-model",
            )
        ]

    def reset(self) -> None:
        self._frames.clear()
        self._last_sample_s = float("-inf")
        self._last_inference_s = float("-inf")
        self._fallback.reset()
