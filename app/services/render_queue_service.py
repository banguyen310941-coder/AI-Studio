from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import time
import uuid


@dataclass
class RenderJob:
    id: str
    project_name: str
    project_dir: str
    shot_number: int
    scene_number: int
    title: str
    prompt: str
    output_path: str
    status: str = "Chờ render"
    progress: int = 0
    error: str = ""
    created_at: float = 0.0


class RenderQueueService:
    def __init__(self, projects_root: Path) -> None:
        self.projects_root = projects_root
        self.queue_file = projects_root / "render_queue.json"

    def load_queue(self) -> list[RenderJob]:
        if not self.queue_file.exists():
            return []

        try:
            payload = json.loads(self.queue_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

        jobs: list[RenderJob] = []
        for row in payload.get("jobs", []):
            try:
                jobs.append(RenderJob(**row))
            except TypeError:
                continue
        return jobs

    def save_queue(self, jobs: list[RenderJob]) -> None:
        self.projects_root.mkdir(parents=True, exist_ok=True)
        self.queue_file.write_text(
            json.dumps(
                {"jobs": [asdict(job) for job in jobs]},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def create_jobs_from_project(self, project_dir: Path) -> list[RenderJob]:
        storyboard_path = project_dir / "storyboard.json"
        director_path = project_dir / "director_plan.json"

        rows: list[dict] = []
        if storyboard_path.exists():
            try:
                payload = json.loads(storyboard_path.read_text(encoding="utf-8"))
                rows = payload.get("shots", [])
            except (OSError, json.JSONDecodeError):
                rows = []
        elif director_path.exists():
            try:
                payload = json.loads(director_path.read_text(encoding="utf-8"))
                for scene in payload.get("scenes", []):
                    for shot in scene.get("shots", []):
                        rows.append(
                            {
                                "shot_number": shot.get("number", 0),
                                "scene_number": scene.get("number", 0),
                                "title": shot.get("title", ""),
                                "veo_prompt": shot.get("veo_prompt", ""),
                            }
                        )
            except (OSError, json.JSONDecodeError):
                rows = []

        render_dir = project_dir / "renders"
        render_dir.mkdir(parents=True, exist_ok=True)

        jobs: list[RenderJob] = []
        for index, row in enumerate(rows, start=1):
            shot_number = int(row.get("shot_number") or row.get("number") or index)
            scene_number = int(row.get("scene_number") or 1)
            prompt = str(row.get("veo_prompt") or row.get("prompt") or "")
            title = str(row.get("title") or f"Shot {shot_number}")
            output_path = render_dir / f"shot_{shot_number:03d}.mp4"

            jobs.append(
                RenderJob(
                    id=uuid.uuid4().hex,
                    project_name=project_dir.name,
                    project_dir=str(project_dir),
                    shot_number=shot_number,
                    scene_number=scene_number,
                    title=title,
                    prompt=prompt,
                    output_path=str(output_path),
                    created_at=time.time(),
                )
            )

        return jobs

    @staticmethod
    def reset_failed(jobs: list[RenderJob]) -> None:
        for job in jobs:
            if job.status == "Lỗi":
                job.status = "Chờ render"
                job.progress = 0
                job.error = ""

    @staticmethod
    def next_pending_index(jobs: list[RenderJob]) -> int:
        for index, job in enumerate(jobs):
            if job.status in {"Chờ render", "Đã tạm dừng"}:
                return index
        return -1
