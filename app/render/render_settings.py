from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

from app.render.encoder_profiles import get_profile
from app.render.gpu_detector import GPUDetector


@dataclass(slots=True)
class RenderSettings:
    encoder_id: str = "auto"
    profile_id: str = "standard"

    def resolve_codec(self, ffmpeg_path: str = "ffmpeg") -> str:
        detector = GPUDetector(ffmpeg_path)
        if self.encoder_id == "auto":
            return detector.recommended().codec
        for item in detector.detect():
            if item.id == self.encoder_id and item.available:
                return item.codec
        return "libx264"

    def ffmpeg_args(self, ffmpeg_path: str = "ffmpeg") -> list[str]:
        return get_profile(self.profile_id).ffmpeg_args(self.resolve_codec(ffmpeg_path))

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict | None) -> "RenderSettings":
        data = data or {}
        return cls(str(data.get("encoder_id", "auto")), str(data.get("profile_id", "standard")))


class RenderSettingsStore:
    def __init__(self, path: str | Path = "data/render_settings.json") -> None:
        self.path = Path(path)

    def load(self) -> RenderSettings:
        try:
            return RenderSettings.from_dict(json.loads(self.path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            return RenderSettings()

    def save(self, settings: RenderSettings) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(settings.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return self.path
