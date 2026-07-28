from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class Project:
    name: str
    path: Path
    modified_at: datetime
    file_count: int
    size_bytes: int

    @property
    def size_text(self) -> str:
        size = float(self.size_bytes)
        units = ("B", "KB", "MB", "GB")

        for unit in units:
            if size < 1024 or unit == units[-1]:
                if unit == "B":
                    return f"{int(size)} {unit}"
                return f"{size:.1f} {unit}"
            size /= 1024

        return f"{self.size_bytes} B"


class ProjectManager:
    def __init__(self) -> None:
        project_root = Path(__file__).resolve().parent.parent
        self.projects_directory = project_root / "projects"
        self.projects_directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _project_stats(project_path: Path) -> tuple[int, int]:
        file_count = 0
        size_bytes = 0

        try:
            for item in project_path.rglob("*"):
                if not item.is_file():
                    continue
                file_count += 1
                try:
                    size_bytes += item.stat().st_size
                except OSError:
                    pass
        except OSError:
            pass

        return file_count, size_bytes

    def get_projects(self) -> list[Project]:
        projects: list[Project] = []

        try:
            candidates = list(self.projects_directory.iterdir())
        except OSError:
            return []

        for project_path in candidates:
            if not project_path.is_dir():
                continue

            try:
                modified_at = datetime.fromtimestamp(project_path.stat().st_mtime)
            except OSError:
                modified_at = datetime.fromtimestamp(0)

            file_count, size_bytes = self._project_stats(project_path)
            projects.append(
                Project(
                    name=project_path.name,
                    path=project_path,
                    modified_at=modified_at,
                    file_count=file_count,
                    size_bytes=size_bytes,
                )
            )

        return sorted(
            projects,
            key=lambda project: project.modified_at,
            reverse=True,
        )

    def get_project(self, project_name: str) -> Project | None:
        for project in self.get_projects():
            if project.name == project_name:
                return project
        return None

    def create_project(self, project_name: str) -> bool:
        project_path = self.projects_directory / project_name

        if project_path.exists():
            return False

        project_path.mkdir(parents=True, exist_ok=False)
        for folder_name in ("images", "audio", "video", "exports"):
            (project_path / folder_name).mkdir(exist_ok=True)

        metadata = {
            "name": project_name,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "version": 1,
        }
        (project_path / "project.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return True

    def delete_project(self, project_name: str) -> bool:
        project_path = self.projects_directory / project_name
        if not project_path.exists():
            return False
        shutil.rmtree(project_path)
        return True

    def save_script(self, project_name: str, script_content: str) -> bool:
        project_path = self.projects_directory / project_name
        if not project_path.exists():
            return False

        (project_path / "script.txt").write_text(
            script_content,
            encoding="utf-8",
        )
        return True

    def load_script(self, project_name: str) -> str:
        script_path = self.projects_directory / project_name / "script.txt"
        if not script_path.exists():
            return ""
        return script_path.read_text(encoding="utf-8")

    def save_scenes(self, project_name: str, scenes: list[dict]) -> bool:
        project_path = self.projects_directory / project_name
        if not project_path.exists():
            return False

        (project_path / "scenes.json").write_text(
            json.dumps({"scenes": scenes}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return True

    def load_scenes(self, project_name: str) -> list[dict]:
        scenes_path = self.projects_directory / project_name / "scenes.json"
        if not scenes_path.exists():
            return []

        try:
            data = json.loads(scenes_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

        scenes = data.get("scenes", [])
        return scenes if isinstance(scenes, list) else []
