from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class TimelineClip:
    id: str
    track: str
    source: str
    start: float = 0.0
    duration: float = 5.0
    label: str = ""
    enabled: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TimelineClip":
        return cls(
            id=str(data.get("id", "")),
            track=str(data.get("track", "video")),
            source=str(data.get("source", "")),
            start=max(0.0, float(data.get("start", 0.0))),
            duration=max(0.1, float(data.get("duration", 5.0))),
            label=str(data.get("label", "")),
            enabled=bool(data.get("enabled", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TimelineDocument:
    version: int = 1
    fps: int = 30
    clips: list[TimelineClip] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return max((clip.start + clip.duration for clip in self.clips if clip.enabled), default=0.0)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TimelineDocument":
        clips = [TimelineClip.from_dict(item) for item in data.get("clips", []) if isinstance(item, dict)]
        return cls(version=int(data.get("version", 1)), fps=max(1, int(data.get("fps", 30))), clips=clips)

    def to_dict(self) -> dict[str, Any]:
        return {"version": self.version, "fps": self.fps, "duration": self.duration, "clips": [c.to_dict() for c in self.clips]}
