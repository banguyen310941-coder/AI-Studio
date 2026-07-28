from collections.abc import Callable
from pathlib import Path

from app.agents.image_agent import ImageAgent
from app.agents.voice_agent import VoiceAgent
from app.models.scene_task import SceneTask
from app.services.scene_task_queue import SceneTaskQueue
from app.subtitle_builder import SubtitleBuilder
from app.video_builder import VideoBuilder


ProgressCallback = Callable[[int, str], None]
SceneCompletedCallback = Callable[[int, Path], None]
CancelCallback = Callable[[], bool]


class PipelineCancelledError(RuntimeError):
    """
    Lỗi riêng dùng khi người dùng chủ động dừng pipeline.
    """


class VideoPipelineService:
    """
    Quy trình dựng video dựa trên SceneTaskQueue.

    Mỗi cảnh là một SceneTask độc lập. Khi một cảnh lỗi,
    pipeline chỉ thử lại cảnh đó. Những ảnh và giọng đọc
    đã tạo thành công được sử dụng lại ở lần thử tiếp theo.
    """

    def __init__(
        self,
        project_path: Path,
        scenes: list[dict],
        progress_callback: ProgressCallback | None = None,
        scene_completed_callback: SceneCompletedCallback | None = None,
        cancel_callback: CancelCallback | None = None,
        max_retries: int = 2,
    ) -> None:
        self.project_path = Path(project_path)
        self.scenes = scenes
        self.progress_callback = progress_callback
        self.scene_completed_callback = scene_completed_callback
        self.cancel_callback = cancel_callback
        self.max_retries = max_retries

        self.image_agent = ImageAgent()
        self.voice_agent = VoiceAgent()
        self.subtitle_builder = SubtitleBuilder()
        self.video_builder = VideoBuilder()

        self.task_queue: SceneTaskQueue | None = None

    def run(self) -> Path:
        if not self.scenes:
            raise ValueError(
                "Dự án chưa có cảnh để dựng video."
            )

        self.create_project_directories()

        self.task_queue = SceneTaskQueue(
            project_path=self.project_path,
            scenes=self.scenes,
            max_retries=self.max_retries,
        )

        total_scenes = len(self.task_queue)

        while self.task_queue.has_pending():
            self.check_cancelled()

            task = self.task_queue.next_task()

            if task is None:
                break

            try:
                self.process_task(
                    task=task,
                    total_scenes=total_scenes,
                )
                task.mark_completed()

                self.report_scene_completed(
                    scene_number=task.scene_number,
                    video_path=task.video_path,
                )

                completed_count = len(
                    self.task_queue.completed_tasks()
                )

                self.report_progress(
                    self.scene_progress(completed_count, total_scenes),
                    (
                        f"Đã hoàn thành Cảnh "
                        f"{task.scene_number}/{total_scenes}"
                    ),
                )

            except PipelineCancelledError:
                task.mark_cancelled()
                self.task_queue.cancel_pending()
                raise

            except Exception as error:
                task.mark_failed(error)

                if self.task_queue.retry_task(task):
                    self.report_progress(
                        self.current_queue_progress(total_scenes),
                        (
                            f"Cảnh {task.scene_number} gặp lỗi. "
                            f"Đang thử lại lần "
                            f"{task.retry_count}/{task.max_retries}..."
                        ),
                    )
                    continue

                raise RuntimeError(
                    (
                        f"Cảnh {task.scene_number} thất bại sau "
                        f"{task.retry_count + 1} lần xử lý.\n"
                        f"Chi tiết: {task.error_message}"
                    )
                ) from error

        self.check_cancelled()

        scene_video_paths = [
            task.video_path
            for task in self.task_queue.tasks
        ]

        for task in self.task_queue.tasks:
            self.validate_file(
                task.video_path,
                f"video của Cảnh {task.scene_number}",
            )

        self.report_progress(
            95,
            "Đang ghép các cảnh thành video hoàn chỉnh...",
        )

        final_path = self.video_builder.merge_scene_videos(
            scene_paths=scene_video_paths,
            output_path=self.get_final_video_path(),
        )

        self.validate_file(
            final_path,
            "video hoàn chỉnh",
        )

        self.report_progress(
            100,
            "Video hoàn chỉnh đã được tạo.",
        )

        return final_path

    def process_task(
        self,
        task: SceneTask,
        total_scenes: int,
    ) -> None:
        task.mark_running()

        self.report_progress(
            self.current_queue_progress(total_scenes),
            (
                f"Cảnh {task.scene_number}/{total_scenes}: "
                f"đang chuẩn bị..."
            ),
        )

        self.create_scene_image(task)
        self.check_cancelled()

        self.create_scene_voice(task)
        self.check_cancelled()

        self.create_scene_subtitle(task)
        self.check_cancelled()

        self.create_scene_video(task)
        self.check_cancelled()

    def create_scene_image(
        self,
        task: SceneTask,
    ) -> None:
        if task.image_path.exists():
            self.validate_file(
                task.image_path,
                f"ảnh của Cảnh {task.scene_number}",
            )
            self.report_task_message(
                task,
                "sử dụng ảnh có sẵn...",
            )
            return

        if not task.image_prompt:
            raise ValueError(
                f"Cảnh {task.scene_number} chưa có prompt tạo ảnh."
            )

        self.report_task_message(
            task,
            "AI đang tạo ảnh...",
        )

        image_path = self.image_agent.generate(
            prompt=task.image_prompt,
            output_path=task.image_path,
        )

        self.validate_file(
            image_path,
            f"ảnh của Cảnh {task.scene_number}",
        )

    def create_scene_voice(
        self,
        task: SceneTask,
    ) -> None:
        if task.audio_path.exists():
            self.validate_file(
                task.audio_path,
                f"giọng đọc của Cảnh {task.scene_number}",
            )
            self.report_task_message(
                task,
                "sử dụng giọng đọc có sẵn...",
            )
            return

        if not task.narration:
            raise ValueError(
                f"Cảnh {task.scene_number} chưa có lời đọc."
            )

        self.report_task_message(
            task,
            "AI đang tạo giọng đọc...",
        )

        audio_path = self.voice_agent.generate(
            narration=task.narration,
            output_path=task.audio_path,
        )

        self.validate_file(
            audio_path,
            f"giọng đọc của Cảnh {task.scene_number}",
        )

    def create_scene_subtitle(
        self,
        task: SceneTask,
    ) -> None:
        if not task.narration:
            raise ValueError(
                (
                    f"Cảnh {task.scene_number} "
                    "chưa có lời đọc để tạo phụ đề."
                )
            )

        self.report_task_message(
            task,
            "đang tạo phụ đề...",
        )

        duration = self.video_builder.get_audio_duration(
            task.audio_path
        )

        subtitle_path = (
            self.subtitle_builder
            .create_scene_subtitle(
                narration=task.narration,
                duration=duration,
                output_path=task.subtitle_path,
            )
        )

        self.validate_file(
            subtitle_path,
            f"phụ đề của Cảnh {task.scene_number}",
        )

    def create_scene_video(
        self,
        task: SceneTask,
    ) -> None:
        self.report_task_message(
            task,
            "FFmpeg đang dựng video và chèn phụ đề...",
        )

        video_path = self.video_builder.create_scene_video(
            image_path=task.image_path,
            audio_path=task.audio_path,
            output_path=task.video_path,
            scene_number=task.scene_number,
            subtitle_path=task.subtitle_path,
        )

        self.validate_file(
            video_path,
            f"video của Cảnh {task.scene_number}",
        )

    def create_project_directories(self) -> None:
        for directory_name in (
            "images",
            "audio",
            "subtitles",
            "video",
            "output",
        ):
            (
                self.project_path
                / directory_name
            ).mkdir(
                parents=True,
                exist_ok=True,
            )

    def get_final_video_path(self) -> Path:
        return (
            self.project_path
            / "output"
            / "final_video.mp4"
        )

    def scene_progress(
        self,
        completed_count: int,
        total_scenes: int,
    ) -> int:
        return int(
            completed_count
            / total_scenes
            * 90
        )

    def current_queue_progress(
        self,
        total_scenes: int,
    ) -> int:
        if self.task_queue is None:
            return 0

        return self.scene_progress(
            len(self.task_queue.completed_tasks()),
            total_scenes,
        )

    def report_task_message(
        self,
        task: SceneTask,
        message: str,
    ) -> None:
        total_scenes = (
            len(self.task_queue)
            if self.task_queue is not None
            else len(self.scenes)
        )

        self.report_progress(
            self.current_queue_progress(total_scenes),
            f"Cảnh {task.scene_number}: {message}",
        )

    def report_progress(
        self,
        progress: int,
        message: str,
    ) -> None:
        if self.progress_callback is None:
            return

        self.progress_callback(
            max(0, min(progress, 100)),
            message,
        )

    def report_scene_completed(
        self,
        scene_number: int,
        video_path: Path,
    ) -> None:
        if self.scene_completed_callback is None:
            return

        self.scene_completed_callback(
            scene_number,
            video_path,
        )

    def check_cancelled(self) -> None:
        if (
            self.cancel_callback is not None
            and self.cancel_callback()
        ):
            raise PipelineCancelledError(
                "Quá trình tạo video đã được dừng."
            )

    def validate_file(
        self,
        file_path: Path,
        description: str,
    ) -> None:
        file_path = Path(file_path)

        if not file_path.exists():
            raise RuntimeError(
                f"Không thể tạo {description}."
            )

        if file_path.stat().st_size == 0:
            raise RuntimeError(
                f"File {description} không có dữ liệu."
            )