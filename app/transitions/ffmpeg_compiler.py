from __future__ import annotations

from dataclasses import dataclass

from app.transitions.transition_model import TransitionModel
from app.transitions.transition_registry import TransitionRegistry


@dataclass(frozen=True, slots=True)
class CompiledTransition:
    filter_expression: str
    duration: float
    offset: float


class FFmpegTransitionCompiler:
    """Biên dịch TransitionModel thành filter xfade của FFmpeg."""

    def __init__(self, registry: TransitionRegistry | None = None) -> None:
        self.registry = registry or TransitionRegistry()

    def compile(self, transition: TransitionModel, *, offset: float) -> CompiledTransition:
        preset = self.registry.require(transition.type)
        duration = max(0.1, float(transition.duration))
        safe_offset = max(0.0, float(offset))
        expression = (
            f"xfade=transition={preset.ffmpeg_name}:"
            f"duration={duration:.3f}:offset={safe_offset:.3f}"
        )
        return CompiledTransition(expression, round(duration, 3), round(safe_offset, 3))
