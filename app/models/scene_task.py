from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class SceneTaskStatus(str, Enum):
    """
    Trạng thái xử lý của một cảnh trong video workflow.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class SceneTask:
    """
    Đại diện cho một tác vụ xử lý một cảnh.
    """

    scene_number: int
    scene_data: dict[str, Any]
    project_path: Path

    status: SceneTaskStatus = SceneTaskStatus.PENDING
    retry_count: int = 0
    max_retries: int = 2
    error_message: str = ""

    image_path: Path = field(init=False)
    audio_path: Path = field(init=False)
    subtitle_path: Path = field(init=False)
    video_path: Path = field(init=False)

    def __post_init__(self) -> None:
        if self.scene_number < 1:
            raise ValueError(
                "Số thứ tự cảnh phải lớn hơn hoặc bằng 1."
            )

        self.project_path = Path(
            self.project_path
        )

        self.image_path = (
            self.project_path
            / "images"
            / f"scene_{self.scene_number:02d}.png"
        )
        self.audio_path = (
            self.project_path
            / "audio"
            / f"scene_{self.scene_number:02d}.mp3"
        )
        self.subtitle_path = (
            self.project_path
            / "subtitles"
            / f"scene_{self.scene_number:02d}.srt"
        )
        self.video_path = (
            self.project_path
            / "video"
            / f"scene_{self.scene_number:02d}.mp4"
        )

    @property
    def title(self) -> str:
        return str(
            self.scene_data.get(
                "title",
                f"Cảnh {self.scene_number}",
            )
        ).strip()

    @property
    def image_prompt(self) -> str:
        return str(
            self.scene_data.get(
                "image_prompt",
                "",
            )
        ).strip()

    @property
    def narration(self) -> str:
        return str(
            self.scene_data.get(
                "narration",
                "",
            )
        ).strip()

    @property
    def screen_text(self) -> str:
        return str(
            self.scene_data.get(
                "screen_text",
                "",
            )
        ).strip()

    def mark_running(self) -> None:
        self.status = SceneTaskStatus.RUNNING
        self.error_message = ""

    def mark_completed(self) -> None:
        self.status = SceneTaskStatus.COMPLETED
        self.error_message = ""

    def mark_failed(
        self,
        error: Exception | str,
    ) -> None:
        self.status = SceneTaskStatus.FAILED
        self.error_message = str(error)

    def mark_cancelled(self) -> None:
        self.status = SceneTaskStatus.CANCELLED

    def can_retry(self) -> bool:
        return (
            self.status == SceneTaskStatus.FAILED
            and self.retry_count < self.max_retries
        )

    def prepare_retry(self) -> bool:
        if not self.can_retry():
            return False

        self.retry_count += 1
        self.status = SceneTaskStatus.PENDING
        self.error_message = ""

        return True