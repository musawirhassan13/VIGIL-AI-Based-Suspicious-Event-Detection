"""Sudden fall detection for tracked people.

A fall candidate requires:
1. The same track was previously upright.
2. It becomes low/wide within drop_window_s and its box height decreases.
3. It remains in the lying posture with limited centre drift for stay_s.

This is a geometry-based rule using RGB person bounding boxes, not a trained
fall-classification model.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import hypot

from ...events import EventType
from .base import FrameContext, Rule, RuleHit


@dataclass
class _State:
    last_seen: float
    last_upright_t: float | None = None
    upright_aspect: float = 0.0
    upright_height: float = 0.0
    lying_since: float | None = None
    lying_center: tuple[float, float] = (0.0, 0.0)
    drop_time: float = 0.0
    fired: bool = False


class FallRule(Rule):
    type = EventType.FALL

    def __init__(
        self,
        upright_aspect: float = 1.4,
        lying_aspect: float = 0.85,
        drop_window_s: float = 1.0,
        stay_s: float = 0.5,
        height_ratio: float = 0.75,
        still_ratio: float = 0.6,
        state_ttl_s: float = 2.0,
        edge_margin_px: int = 3,
        cooldown_s: float = 30.0,
    ):
        if upright_aspect <= lying_aspect:
            raise ValueError("upright_aspect must be greater than lying_aspect")
        if drop_window_s <= 0 or stay_s < 0 or state_ttl_s <= 0:
            raise ValueError("drop_window_s/state_ttl_s must be positive and stay_s non-negative")
        if not 0 < height_ratio <= 1:
            raise ValueError("height_ratio must be in (0, 1]")
        if still_ratio < 0 or edge_margin_px < 0 or cooldown_s < 0:
            raise ValueError("still_ratio, edge_margin_px and cooldown_s cannot be negative")

        self.upright_aspect = upright_aspect
        self.lying_aspect = lying_aspect
        self.drop_window_s = drop_window_s
        self.stay_s = stay_s
        self.height_ratio = height_ratio
        self.still_ratio = still_ratio
        self.state_ttl_s = state_ttl_s
        self.edge_margin_px = edge_margin_px
        self.cooldown_s = cooldown_s
        self._states: dict[int, _State] = {}

    def reset(self) -> None:
        self._states.clear()

    def evaluate(self, ctx: FrameContext) -> list[RuleHit]:
        frame_width = ctx.frame_size[0]
        now = ctx.now_s
        hits: list[RuleHit] = []

        for det in ctx.detections:
            if det.track_id is None or det.width <= 0 or det.height <= 0:
                continue

            x1, _, x2, _ = det.box
            if frame_width > 0 and (
                x1 <= self.edge_margin_px
                or x2 >= frame_width - self.edge_margin_px
            ):
                # A cropped person box has unreliable aspect/height geometry.
                continue

            state = self._states.setdefault(
                det.track_id, _State(last_seen=now)
            )
            state.last_seen = now

            aspect = det.aspect
            box_height = det.height
            center = det.center

            if aspect >= self.upright_aspect:
                # Refresh the upright reference while the person is standing.
                state.last_upright_t = now
                state.upright_aspect = aspect
                state.upright_height = box_height
                state.lying_since = None
                state.fired = False

            elif aspect <= self.lying_aspect and state.last_upright_t is not None:
                if state.lying_since is None:
                    gap = now - state.last_upright_t

                    if (
                        0.0 <= gap <= self.drop_window_s
                        and not state.fired
                        and box_height <= self.height_ratio * state.upright_height
                    ):
                        state.lying_since = now
                        state.lying_center = center
                        state.drop_time = gap

                else:
                    drift = hypot(
                        center[0] - state.lying_center[0],
                        center[1] - state.lying_center[1],
                    )

                    if drift > self.still_ratio * state.upright_height:
                        # Significant movement after going down: cancel candidate.
                        state.lying_since = None

                    elif now - state.lying_since >= self.stay_s and not state.fired:
                        state.fired = True

                        # Both terms are bounded to [0, 1].
                        speed_score = max(
                            0.0,
                            min(1.0, 1.0 - state.drop_time / self.drop_window_s),
                        )
                        shape_score = max(
                            0.0,
                            min(1.0, (state.upright_aspect - aspect) / 1.5),
                        )
                        confidence = min(
                            0.95,
                            max(0.0, 0.65 + 0.15 * speed_score + 0.15 * shape_score),
                        )

                        hits.append(
                            RuleHit(
                                self.type,
                                confidence,
                                (det,),
                                str(det.track_id),
                            )
                        )
            # Intermediate shapes retain the current candidate, as before.

        expired_ids = [
            track_id
            for track_id, state in self._states.items()
            if now - state.last_seen > self.state_ttl_s
        ]
        for track_id in expired_ids:
            del self._states[track_id]

        return hits
