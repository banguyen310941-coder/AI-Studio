from __future__ import annotations

from copy import deepcopy
from typing import Any

DEFAULT_COLOR_SETTINGS: dict[str, Any] = {
    "enabled": False,
    "brightness": 0.0,
    "contrast": 1.0,
    "saturation": 1.0,
    "gamma": 1.0,
    "temperature": 0.0,
    "tint": 0.0,
}


class ColorCorrectionService:
    """Lưu và cập nhật thiết lập màu trên từng video clip của TimelineService."""

    def __init__(self, timeline_service: Any) -> None:
        self.timeline_service = timeline_service

    def settings_for_clip(self, clip_id: str) -> dict[str, Any]:
        result = self.timeline_service.find_clip(clip_id)
        if result is None:
            return deepcopy(DEFAULT_COLOR_SETTINGS)
        track, clip = result
        if track.get("type") != "video":
            return deepcopy(DEFAULT_COLOR_SETTINGS)
        settings = deepcopy(DEFAULT_COLOR_SETTINGS)
        raw = clip.get("color_correction", {})
        if isinstance(raw, dict):
            settings.update(raw)
        return self._normalize(settings)

    def apply(self, clip_id: str, settings: dict[str, Any]) -> bool:
        result = self.timeline_service.find_clip(clip_id)
        if result is None:
            return False
        track, clip = result
        if track.get("type") != "video":
            return False
        self.timeline_service.checkpoint()
        clip["color_correction"] = self._normalize(settings)
        return True

    def reset(self, clip_id: str) -> bool:
        return self.apply(clip_id, DEFAULT_COLOR_SETTINGS)

    @staticmethod
    def _normalize(settings: dict[str, Any]) -> dict[str, Any]:
        def clamp(value: Any, low: float, high: float, default: float) -> float:
            try:
                number = float(value)
            except (TypeError, ValueError):
                number = default
            return max(low, min(high, number))

        return {
            "enabled": bool(settings.get("enabled", False)),
            "brightness": clamp(settings.get("brightness"), -1.0, 1.0, 0.0),
            "contrast": clamp(settings.get("contrast"), 0.0, 3.0, 1.0),
            "saturation": clamp(settings.get("saturation"), 0.0, 3.0, 1.0),
            "gamma": clamp(settings.get("gamma"), 0.1, 3.0, 1.0),
            "temperature": clamp(settings.get("temperature"), -1.0, 1.0, 0.0),
            "tint": clamp(settings.get("tint"), -1.0, 1.0, 0.0),
        }
