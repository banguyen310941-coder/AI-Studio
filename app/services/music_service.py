from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import shutil


@dataclass
class MusicTrack:
    name: str
    kind: str
    source_path: str
    start_seconds: int
    duration_seconds: int
    volume: int
    fade_in_seconds: int
    fade_out_seconds: int
    loop: bool = False
    enabled: bool = True


class MusicService:
    SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".aiff", ".m4a", ".aac", ".flac"}

    def load_plan(self, project_dir: Path) -> list[MusicTrack]:
        path = project_dir / "music_plan.json"
        if not path.exists():
            return []

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

        tracks: list[MusicTrack] = []
        for row in payload.get("tracks", []):
            try:
                tracks.append(
                    MusicTrack(
                        name=str(row.get("name", "")),
                        kind=str(row.get("kind", "Nhạc nền")),
                        source_path=str(row.get("source_path", "")),
                        start_seconds=int(row.get("start_seconds", 0)),
                        duration_seconds=int(row.get("duration_seconds", 30)),
                        volume=int(row.get("volume", 70)),
                        fade_in_seconds=int(row.get("fade_in_seconds", 2)),
                        fade_out_seconds=int(row.get("fade_out_seconds", 2)),
                        loop=bool(row.get("loop", False)),
                        enabled=bool(row.get("enabled", True)),
                    )
                )
            except (TypeError, ValueError):
                continue
        return tracks

    @staticmethod
    def save_plan(project_dir: Path, tracks: list[MusicTrack]) -> Path:
        project_dir.mkdir(parents=True, exist_ok=True)
        path = project_dir / "music_plan.json"
        path.write_text(
            json.dumps(
                {"tracks": [asdict(track) for track in tracks]},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return path

    @staticmethod
    def copy_into_project(project_dir: Path, source_path: Path, kind: str) -> Path:
        folder = "music" if kind == "Nhạc nền" else "sfx"
        destination_dir = project_dir / "audio" / folder
        destination_dir.mkdir(parents=True, exist_ok=True)

        destination = destination_dir / source_path.name
        counter = 1
        while destination.exists() and destination.resolve() != source_path.resolve():
            destination = destination_dir / f"{source_path.stem}_{counter}{source_path.suffix}"
            counter += 1

        if source_path.resolve() != destination.resolve():
            shutil.copy2(source_path, destination)
        return destination

    @staticmethod
    def create_mix_manifest(project_dir: Path, tracks: list[MusicTrack]) -> Path:
        enabled_tracks = [track for track in tracks if track.enabled]
        total_duration = 0
        rows = []

        for track in enabled_tracks:
            end_seconds = track.start_seconds + track.duration_seconds
            total_duration = max(total_duration, end_seconds)
            rows.append(
                {
                    **asdict(track),
                    "end_seconds": end_seconds,
                    "gain": round(track.volume / 100, 2),
                }
            )

        path = project_dir / "audio" / "mix_manifest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "total_duration_seconds": total_duration,
                    "track_count": len(rows),
                    "tracks": rows,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return path
