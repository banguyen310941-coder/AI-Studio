import json
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Project:
    name: str
    path: Path


class ProjectManager:
    def __init__(self) -> None:
        project_root = Path(__file__).resolve().parent.parent
        self.projects_directory = project_root / "projects"

        self.projects_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    def get_projects(self) -> list[Project]:
        projects: list[Project] = []

        for project_path in self.projects_directory.iterdir():
            if project_path.is_dir():
                projects.append(
                    Project(
                        name=project_path.name,
                        path=project_path,
                    )
                )

        return sorted(
            projects,
            key=lambda project: project.name.lower(),
        )

    def create_project(self, project_name: str) -> bool:
        project_path = self.projects_directory / project_name

        if project_path.exists():
            return False

        project_path.mkdir(
            parents=True,
            exist_ok=False,
        )

        (project_path / "images").mkdir(exist_ok=True)
        (project_path / "audio").mkdir(exist_ok=True)
        (project_path / "video").mkdir(exist_ok=True)

        return True

    def delete_project(self, project_name: str) -> bool:
        project_path = self.projects_directory / project_name

        if not project_path.exists():
            return False

        shutil.rmtree(project_path)
        return True

    def save_script(
        self,
        project_name: str,
        script_content: str,
    ) -> bool:
        project_path = self.projects_directory / project_name

        if not project_path.exists():
            return False

        script_path = project_path / "script.txt"

        script_path.write_text(
            script_content,
            encoding="utf-8",
        )

        return True

    def load_script(self, project_name: str) -> str:
        script_path = (
            self.projects_directory
            / project_name
            / "script.txt"
        )

        if not script_path.exists():
            return ""

        return script_path.read_text(encoding="utf-8")

    def save_scenes(
        self,
        project_name: str,
        scenes: list[dict],
    ) -> bool:
        project_path = self.projects_directory / project_name

        if not project_path.exists():
            return False

        scenes_path = project_path / "scenes.json"

        scenes_path.write_text(
            json.dumps(
                {"scenes": scenes},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return True

    def load_scenes(
        self,
        project_name: str,
    ) -> list[dict]:
        scenes_path = (
            self.projects_directory
            / project_name
            / "scenes.json"
        )

        if not scenes_path.exists():
            return []

        try:
            data = json.loads(
                scenes_path.read_text(encoding="utf-8")
            )
        except (json.JSONDecodeError, OSError):
            return []

        scenes = data.get("scenes", [])

        if not isinstance(scenes, list):
            return []

        return scenes