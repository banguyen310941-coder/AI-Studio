from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.services.video_pipeline_service import (
    VideoPipelineService,
)


class VideoPipelineWorker(QThread):
    progress_changed = Signal(int, str)
    scene_completed = Signal(int, str)
    pipeline_completed = Signal(str)
    pipeline_failed = Signal(str)

    def __init__(
        self,
        project_path: Path,
        scenes: list[dict],
    ) -> None:
        super().__init__()

        self.project_path = Path(project_path)
        self.scenes = scenes
        self.cancel_requested = False

    def cancel(self) -> None:
        self.cancel_requested = True

    def is_cancel_requested(self) -> bool:
        return self.cancel_requested

    def emit_progress(
        self,
        progress: int,
        message: str,
    ) -> None:
        self.progress_changed.emit(
            progress,
            message,
        )

    def emit_scene_completed(
        self,
        scene_number: int,
        video_path: Path,
    ) -> None:
        self.scene_completed.emit(
            scene_number,
            str(video_path),
        )

    def run(self) -> None:
        try:
            pipeline_service = VideoPipelineService(
                project_path=self.project_path,
                scenes=self.scenes,
                progress_callback=self.emit_progress,
                scene_completed_callback=(
                    self.emit_scene_completed
                ),
                cancel_callback=self.is_cancel_requested,
            )

            final_video_path = pipeline_service.run()

            self.pipeline_completed.emit(
                str(final_video_path)
            )

        except Exception as error:
            self.pipeline_failed.emit(
                str(error)
            )