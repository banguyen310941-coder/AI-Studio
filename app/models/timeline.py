from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class TimelineClip:
    id: str
    track: str
    name: str
    source: str = ""
    start: float = 0.0
    duration: float = 5.0
    volume: float = 1.0
    enabled: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TimelineClip":
        return cls(
            id=str(data.get("id", "")),
            track=str(data.get("track", "video")),
            name=str(data.get("name", "Clip")),
            source=str(data.get("source", "")),
            start=max(0.0, float(data.get("start", 0.0))),
            duration=max(0.1, float(data.get("duration", 5.0))),
            volume=min(1.0, max(0.0, float(data.get("volume", 1.0)))),
            enabled=bool(data.get("enabled", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TimelineDocument:
    fps: int = 30
    width: int = 1920
    height: int = 1080
    clips: list[TimelineClip] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return max((clip.start + clip.duration for clip in self.clips if clip.enabled), default=0.0)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TimelineDocument":
        return cls(
            fps=max(1, int(data.get("fps", 30))),
            width=max(16, int(data.get("width", 1920))),
            height=max(16, int(data.get("height", 1080))),
            clips=[TimelineClip.from_dict(item) for item in data.get("clips", [])],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "fps": self.fps,
            "width": self.width,
            "height": self.height,
            "duration": self.duration,
            "clips": [clip.to_dict() for clip in self.clips],
        }
