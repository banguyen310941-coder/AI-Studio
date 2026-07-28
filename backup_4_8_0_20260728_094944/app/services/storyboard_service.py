from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import json


@dataclass
class StoryboardShot:
    shot_number: int
    scene_number: int
    title: str
    visual_description: str
    camera: str
    duration_seconds: int
    veo_prompt: str
    status: str = "Chưa dựng"
    asset_path: str = ""


class StoryboardService:
    def load_from_project(self, project_dir: Path) -> list[StoryboardShot]:
        storyboard_path = project_dir / "storyboard.json"
        if storyboard_path.exists():
            try:
                payload = json.loads(storyboard_path.read_text(encoding="utf-8"))
                rows = payload.get("shots", [])
                return [
                    StoryboardShot(
                        shot_number=int(row.get("shot_number", 0)),
                        scene_number=int(row.get("scene_number", 0)),
                        title=str(row.get("title", "")),
                        visual_description=str(row.get("visual_description", "")),
                        camera=str(row.get("camera", "")),
                        duration_seconds=int(row.get("duration_seconds", 8)),
                        veo_prompt=str(row.get("veo_prompt", "")),
                        status=str(row.get("status", "Chưa dựng")),
                        asset_path=str(row.get("asset_path", "")),
                    )
                    for row in rows
                ]
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                return []

        director_plan_path = project_dir / "director_plan.json"
        if not director_plan_path.exists():
            return []

        try:
            payload = json.loads(director_plan_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

        shots: list[StoryboardShot] = []
        for scene in payload.get("scenes", []):
            scene_number = int(scene.get("number", 0))
            for shot in scene.get("shots", []):
                shots.append(
                    StoryboardShot(
                        shot_number=int(shot.get("number", 0)),
                        scene_number=scene_number,
                        title=str(shot.get("title", "")),
                        visual_description=str(shot.get("description", "")),
                        camera=str(shot.get("camera", "")),
                        duration_seconds=8,
                        veo_prompt=str(shot.get("veo_prompt", "")),
                    )
                )

        return shots

    def save(self, project_dir: Path, shots: list[StoryboardShot]) -> Path:
        project_dir.mkdir(parents=True, exist_ok=True)
        path = project_dir / "storyboard.json"
        path.write_text(
            json.dumps(
                {"shots": [asdict(shot) for shot in shots]},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self.save_timeline(project_dir, shots)
        return path

    def save_timeline(self, project_dir: Path, shots: list[StoryboardShot]) -> Path:
        current_time = 0
        clips = []

        for shot in shots:
            clips.append(
                {
                    "shot_number": shot.shot_number,
                    "scene_number": shot.scene_number,
                    "title": shot.title,
                    "start_seconds": current_time,
                    "duration_seconds": shot.duration_seconds,
                    "end_seconds": current_time + shot.duration_seconds,
                    "asset_path": shot.asset_path,
                    "status": shot.status,
                }
            )
            current_time += shot.duration_seconds

        path = project_dir / "timeline.json"
        path.write_text(
            json.dumps(
                {
                    "duration_seconds": current_time,
                    "clips": clips,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return path
