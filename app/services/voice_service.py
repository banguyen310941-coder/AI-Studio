from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import platform
import re
import subprocess


@dataclass
class VoiceSegment:
    scene_number: int
    title: str
    text: str
    voice: str
    rate: int
    output_path: str
    status: str = "Chưa tạo"
    error: str = ""


class VoiceService:
    def __init__(self, projects_root: Path) -> None:
        self.projects_root = projects_root

    @staticmethod
    def available_voices() -> list[str]:
        if platform.system() != "Darwin":
            return ["System Default"]

        try:
            result = subprocess.run(
                ["say", "-v", "?"],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return ["System Default"]

        voices: list[str] = []
        for line in result.stdout.splitlines():
            match = re.match(r"^(\S+)", line.strip())
            if match:
                name = match.group(1)
                if name not in voices:
                    voices.append(name)

        return voices or ["System Default"]

    def load_segments(self, project_dir: Path) -> list[VoiceSegment]:
        voice_plan = project_dir / "voice_plan.json"
        if voice_plan.exists():
            try:
                payload = json.loads(voice_plan.read_text(encoding="utf-8"))
                return [
                    VoiceSegment(
                        scene_number=int(row.get("scene_number", 0)),
                        title=str(row.get("title", "")),
                        text=str(row.get("text", "")),
                        voice=str(row.get("voice", "System Default")),
                        rate=int(row.get("rate", 180)),
                        output_path=str(row.get("output_path", "")),
                        status=str(row.get("status", "Chưa tạo")),
                        error=str(row.get("error", "")),
                    )
                    for row in payload.get("segments", [])
                ]
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                return []

        director_path = project_dir / "director_plan.json"
        if not director_path.exists():
            return []

        try:
            payload = json.loads(director_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

        audio_dir = project_dir / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)

        segments: list[VoiceSegment] = []
        for scene in payload.get("scenes", []):
            scene_number = int(scene.get("number", 0))
            title = str(scene.get("title", f"Cảnh {scene_number}"))
            narration = str(scene.get("narration", "")).strip()
            if not narration:
                narration = str(scene.get("purpose", "")).strip()

            segments.append(
                VoiceSegment(
                    scene_number=scene_number,
                    title=title,
                    text=narration,
                    voice="System Default",
                    rate=180,
                    output_path=str(audio_dir / f"scene_{scene_number:03d}.aiff"),
                )
            )

        return segments

    @staticmethod
    def save_plan(project_dir: Path, segments: list[VoiceSegment]) -> Path:
        project_dir.mkdir(parents=True, exist_ok=True)
        path = project_dir / "voice_plan.json"
        path.write_text(
            json.dumps(
                {"segments": [asdict(segment) for segment in segments]},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return path

    @staticmethod
    def create_subtitle_file(project_dir: Path, segments: list[VoiceSegment]) -> Path:
        current_seconds = 0
        entries: list[str] = []

        for index, segment in enumerate(segments, start=1):
            word_count = max(1, len(segment.text.split()))
            duration = max(3, round(word_count / 2.6))
            start = current_seconds
            end = current_seconds + duration
            entries.extend(
                [
                    str(index),
                    f"{VoiceService._srt_time(start)} --> {VoiceService._srt_time(end)}",
                    segment.text.strip(),
                    "",
                ]
            )
            current_seconds = end

        path = project_dir / "subtitles.srt"
        path.write_text("\n".join(entries), encoding="utf-8")
        return path

    @staticmethod
    def _srt_time(seconds: int) -> str:
        hours, remaining = divmod(seconds, 3600)
        minutes, seconds = divmod(remaining, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},000"
