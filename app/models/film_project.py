from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(slots=True)
class FilmShot:
    index: int
    act: int
    scene: int
    title: str
    duration_seconds: int
    narration: str
    veo_prompt: str
    status: str = "waiting"
    video_path: str = ""
    error: str = ""


@dataclass(slots=True)
class FilmProject:
    title: str
    idea: str
    genre: str
    target_minutes: int
    aspect_ratio: str
    resolution: str
    veo_model: str
    shots: list[FilmShot] = field(default_factory=list)

    @property
    def target_seconds(self) -> int:
        return self.target_minutes * 60

    @property
    def completed_shots(self) -> int:
        return sum(1 for shot in self.shots if shot.status == "done" and shot.video_path)

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> "FilmProject":
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["shots"] = [FilmShot(**item) for item in payload.get("shots", [])]
        return cls(**payload)
