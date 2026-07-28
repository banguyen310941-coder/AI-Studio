from __future__ import annotations

from app.transitions.transition_model import SUPPORTED_EASINGS


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def apply_easing(name: str, progress: float) -> float:
    """Trả về tiến độ 0..1 theo easing đã chọn."""
    t = clamp01(progress)
    if name not in SUPPORTED_EASINGS:
        name = "ease-in-out"
    if name == "linear":
        return t
    if name == "ease-in":
        return t * t
    if name == "ease-out":
        return 1.0 - (1.0 - t) * (1.0 - t)
    return 2.0 * t * t if t < 0.5 else 1.0 - ((-2.0 * t + 2.0) ** 2) / 2.0
