from __future__ import annotations


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def apply_easing(name: str, progress: float) -> float:
    """Trả về tiến độ 0..1 cho preview và renderer."""
    t = clamp01(progress)
    if name == "ease-in":
        return t * t
    if name == "ease-out":
        return 1.0 - (1.0 - t) * (1.0 - t)
    if name == "ease-in-out":
        return 2.0 * t * t if t < 0.5 else 1.0 - ((-2.0 * t + 2.0) ** 2) / 2.0
    return t
