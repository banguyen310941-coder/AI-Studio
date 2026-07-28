from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class TransitionPreset:
    id: str
    name: str
    category: str
    default_duration: float
    ffmpeg_name: str
    description: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class TransitionRegistry:
    """Đăng ký preset transition và ánh xạ sang FFmpeg xfade."""

    def __init__(self, presets: Iterable[TransitionPreset] | None = None) -> None:
        self._items: dict[str, TransitionPreset] = {}
        for preset in presets or self.default_presets():
            self.register(preset)

    def register(self, preset: TransitionPreset, *, replace: bool = False) -> None:
        if preset.id in self._items and not replace:
            raise ValueError(f"Transition đã được đăng ký: {preset.id}")
        self._items[preset.id] = preset

    def get(self, preset_id: str) -> TransitionPreset | None:
        return self._items.get(preset_id)

    def require(self, preset_id: str) -> TransitionPreset:
        preset = self.get(preset_id)
        if preset is None:
            raise ValueError(f"Transition không được hỗ trợ: {preset_id}")
        return preset

    def all(self) -> tuple[TransitionPreset, ...]:
        return tuple(self._items.values())

    def as_dicts(self) -> tuple[dict[str, object], ...]:
        return tuple(item.to_dict() for item in self.all())

    @staticmethod
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
            TransitionPreset("blur", "Blur", "Hiệu ứng", 0.8, "fadegrays"),
        )
