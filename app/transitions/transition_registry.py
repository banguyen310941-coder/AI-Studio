from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class TransitionPreset:
    id: str
    name: str
    category: str
    default_duration: float
    ffmpeg_name: str


class TransitionRegistry:
    def __init__(self, presets: Iterable[TransitionPreset] | None = None) -> None:
        self._presets: dict[str, TransitionPreset] = {}
        for preset in presets or default_presets():
            self.register(preset)

    def register(self, preset: TransitionPreset) -> None:
        if not preset.id:
            raise ValueError("Preset id không được để trống.")
        self._presets[preset.id] = preset

    def get(self, preset_id: str) -> TransitionPreset | None:
        return self._presets.get(preset_id)

    def require(self, preset_id: str) -> TransitionPreset:
        preset = self.get(preset_id)
        if preset is None:
            raise ValueError(f"Transition không được hỗ trợ: {preset_id}")
        return preset

    def all(self) -> tuple[TransitionPreset, ...]:
        return tuple(self._presets.values())


def default_presets() -> tuple[TransitionPreset, ...]:
    return (
        TransitionPreset("cross_dissolve", "Cross Dissolve", "Cơ bản", 1.0, "fade"),
        TransitionPreset("fade", "Fade", "Cơ bản", 0.8, "fade"),
        TransitionPreset("dip_to_black", "Dip to Black", "Cơ bản", 0.8, "fadeblack"),
        TransitionPreset("wipe_left", "Wipe Left", "Wipe", 0.7, "wipeleft"),
        TransitionPreset("wipe_right", "Wipe Right", "Wipe", 0.7, "wiperight"),
        TransitionPreset("slide_left", "Slide Left", "Slide", 0.7, "slideleft"),
        TransitionPreset("slide_right", "Slide Right", "Slide", 0.7, "slideright"),
        TransitionPreset("zoom", "Zoom", "Chuyển động", 0.6, "zoomin"),
        TransitionPreset("blur", "Blur", "Hiệu ứng", 0.8, "fade"),
    )
