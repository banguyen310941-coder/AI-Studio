from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from app.models.film_project import FilmProject


class FilmAssemblyError(RuntimeError):
    pass


class FilmAssemblyService:
    def __init__(self) -> None:
        self.ffmpeg = shutil.which("ffmpeg")

    def assemble(
        self,
        project: FilmProject,
        output_path: Path,
        progress: Callable[[int, str], None] | None = None,
    ) -> Path:
        if not self.ffmpeg:
            raise FilmAssemblyError("Không tìm thấy FFmpeg. Hãy cài FFmpeg trước khi xuất phim.")
        clips = [Path(shot.video_path) for shot in project.shots if shot.status == "done" and Path(shot.video_path).is_file()]
        if not clips:
            raise FilmAssemblyError("Chưa có clip Veo nào để ghép.")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="ai_film_concat_") as tmp:
            concat_file = Path(tmp) / "clips.txt"
            concat_file.write_text(
                "\n".join(f"file '{str(path.resolve()).replace(chr(39), chr(39)+chr(92)+chr(39)+chr(39))}'" for path in clips),
                encoding="utf-8",
            )
            if progress:
                progress(20, "Đang chuẩn bị danh sách clip")
            command = [
                self.ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
                "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(output_path),
            ]
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                raise FilmAssemblyError(result.stderr.strip() or "FFmpeg không thể ghép phim.")
        if progress:
            progress(100, "Đã xuất phim hoàn chỉnh")
        return output_path
