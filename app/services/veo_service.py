from __future__ import annotations

import os
import time

from dotenv import load_dotenv
from pathlib import Path
from typing import Callable

from app.models.film_project import FilmProject, FilmShot


ProgressCallback = Callable[[int, str], None]


class VeoServiceError(RuntimeError):
    pass


class VeoService:
    """Kết nối Gemini API / Veo và tải từng shot về máy."""

    def __init__(self, api_key: str | None = None) -> None:
        load_dotenv()
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    def ensure_ready(self) -> None:
        if not self.api_key:
            raise VeoServiceError(
                "Chưa có GEMINI_API_KEY. Hãy thêm khóa Gemini API vào file .env hoặc biến môi trường."
            )
        try:
            from google import genai  # noqa: F401
            from google.genai import types  # noqa: F401
        except ImportError as exc:
            raise VeoServiceError(
                "Thiếu thư viện google-genai. Chạy: pip install --upgrade google-genai"
            ) from exc

    def render_project(
        self,
        project: FilmProject,
        project_dir: Path,
        progress: ProgressCallback | None = None,
        stop_requested: Callable[[], bool] | None = None,
    ) -> FilmProject:
        self.ensure_ready()
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)
        clips_dir = project_dir / "clips"
        clips_dir.mkdir(parents=True, exist_ok=True)
        total = len(project.shots)

        for position, shot in enumerate(project.shots, start=1):
            if stop_requested and stop_requested():
                break
            output_path = clips_dir / f"shot_{shot.index:04d}.mp4"
            if output_path.is_file() and output_path.stat().st_size > 0:
                shot.status = "done"
                shot.video_path = str(output_path)
                continue

            shot.status = "rendering"
            shot.error = ""
            project.save(project_dir / "film_project.json")
            if progress:
                progress(int((position - 1) / max(1, total) * 100), f"Đang gửi shot {position}/{total} tới Veo")

            try:
                config = types.GenerateVideosConfig(
                    aspect_ratio=project.aspect_ratio,
                    resolution=project.resolution,
                )
                operation = client.models.generate_videos(
                    model=project.veo_model,
                    prompt=shot.veo_prompt,
                    config=config,
                )
                while not operation.done:
                    if stop_requested and stop_requested():
                        shot.status = "waiting"
                        project.save(project_dir / "film_project.json")
                        return project
                    time.sleep(10)
                    operation = client.operations.get(operation)

                if not operation.response or not operation.response.generated_videos:
                    raise VeoServiceError("Veo hoàn thành nhưng không trả về video.")
                generated = operation.response.generated_videos[0]
                client.files.download(file=generated.video)
                generated.video.save(str(output_path))
                shot.video_path = str(output_path)
                shot.status = "done"
            except Exception as exc:  # SDK có nhiều loại lỗi mạng/API
                shot.status = "failed"
                shot.error = str(exc)
            project.save(project_dir / "film_project.json")
            if progress:
                progress(int(position / max(1, total) * 100), f"Đã xử lý shot {position}/{total}")

        return project
