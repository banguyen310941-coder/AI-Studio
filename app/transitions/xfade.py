from __future__ import annotations

from app.transitions.transition_registry import TransitionRegistry


class XFadeCompiler:
    """Biên dịch transition sang đoạn filter FFmpeg xfade."""

    def __init__(self, registry: TransitionRegistry | None = None) -> None:
        self.registry = registry or TransitionRegistry()

    def compile(self, transition: dict, *, offset: float) -> str:
        preset = self.registry.require(str(transition.get("type", "cross_dissolve")))
        duration = max(0.1, float(transition.get("duration", preset.default_duration)))
        safe_offset = max(0.0, float(offset))
        return (
            f"xfade=transition={preset.ffmpeg_name}:"
            f"duration={duration:.3f}:offset={safe_offset:.3f}"
        )
