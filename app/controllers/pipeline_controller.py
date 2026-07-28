from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal

from app.workers.video_pipeline_worker import VideoPipelineWorker


class PipelineController(QObject):
    """
    Điều phối pipeline tạo toàn bộ video trong luồng nền.

    API tương thích với ProjectPage hiện tại:
    - start(project_path, scenes)
    - cancel()
    - is_running()

    Controller phát tín hiệu trực tiếp và đồng thời chuyển tiếp qua EventBus
    nếu EventBus được cung cấp.
    """

    progress_changed = Signal(int, str)
    scene_completed = Signal(int, str)
    pipeline_completed = Signal(str)
    pipeline_failed = Signal(str)
    running_changed = Signal(bool)
    pipeline_finished = Signal()

    def __init__(
        self,
        parent: QObject | None = None,
        event_bus: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self.event_bus = event_bus
        self.worker: VideoPipelineWorker | None = None

        self._running = False
        self._cancel_requested = False
        self._terminal_signal_emitted = False

    # =========================================================
    # STATE
    # =========================================================

    def is_running(self) -> bool:
        return (
            self._running
            and self.worker is not None
            and self.worker.isRunning()
        )

    def _set_running(
        self,
        running: bool,
    ) -> None:
        running = bool(running)

        if self._running == running:
            return

        self._running = running

        self.running_changed.emit(
            running
        )

        self._emit_event_bus(
            "pipeline_running_changed",
            running,
        )

    # =========================================================
    # START
    # =========================================================

    def start(
        self,
        project_path: Path | str,
        scenes: list[dict[str, Any]],
    ) -> bool:
        """
        Bắt đầu pipeline.

        Trả về False nếu pipeline khác đang chạy.
        Trả về True nếu worker đã được khởi động.
        """

        if self.is_running():
            return False

        clean_scenes = self._validate_scenes(
            scenes
        )

        resolved_project_path = Path(
            project_path
        ).expanduser().resolve()

        resolved_project_path.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._dispose_finished_worker()

        self._cancel_requested = False
        self._terminal_signal_emitted = False

        self.worker = VideoPipelineWorker(
            project_path=resolved_project_path,
            scenes=deepcopy(clean_scenes),
        )

        self.worker.progress_changed.connect(
            self._handle_progress
        )

        self.worker.scene_completed.connect(
            self._handle_scene_completed
        )

        self.worker.pipeline_completed.connect(
            self._handle_completed
        )

        self.worker.pipeline_failed.connect(
            self._handle_failed
        )

        self.worker.finished.connect(
            self._handle_worker_finished
        )

        self._set_running(
            True
        )

        self.worker.start()
        return True

    # =========================================================
    # CANCEL
    # =========================================================

    def cancel(self) -> bool:
        """
        Yêu cầu dừng pipeline an toàn.

        Worker sẽ kết thúc sau khi tác vụ hiện tại kiểm tra cờ hủy.
        """

        if not self.is_running():
            return False

        if self.worker is None:
            return False

        self._cancel_requested = True
        self.worker.cancel()

        self._handle_progress(
            0,
            "Đang yêu cầu dừng...",
        )

        return True

    # =========================================================
    # WORKER EVENTS
    # =========================================================

    def _handle_progress(
        self,
        progress: int,
        message: str,
    ) -> None:
        safe_progress = max(
            0,
            min(int(progress), 100),
        )

        clean_message = str(
            message
        )

        self.progress_changed.emit(
            safe_progress,
            clean_message,
        )

        self._emit_event_bus(
            "pipeline_progress",
            safe_progress,
            clean_message,
        )

    def _handle_scene_completed(
        self,
        scene_number: int,
        video_path: str,
    ) -> None:
        scene_number = int(
            scene_number
        )
        video_path = str(
            video_path
        )

        self.scene_completed.emit(
            scene_number,
            video_path,
        )

        self._emit_event_bus(
            "pipeline_scene_completed",
            scene_number,
            video_path,
        )

    def _handle_completed(
        self,
        final_video_path: str,
    ) -> None:
        if self._terminal_signal_emitted:
            return

        self._terminal_signal_emitted = True

        final_video_path = str(
            final_video_path
        )

        self.pipeline_completed.emit(
            final_video_path
        )

        self._emit_event_bus(
            "pipeline_completed",
            final_video_path,
        )

    def _handle_failed(
        self,
        error_message: str,
    ) -> None:
        if self._terminal_signal_emitted:
            return

        clean_message = str(
            error_message
        ).strip()

        # Khi người dùng chủ động dừng, đây không phải lỗi cần bật
        # QMessageBox. ProjectPage sẽ cập nhật trạng thái trong
        # handle_pipeline_finished().
        if self._cancel_requested:
            return

        self._terminal_signal_emitted = True

        self.pipeline_failed.emit(
            clean_message
        )

        self._emit_event_bus(
            "pipeline_failed",
            clean_message,
        )

    def _handle_worker_finished(
        self,
    ) -> None:
        self._set_running(
            False
        )

        self.pipeline_finished.emit()

        self._emit_event_bus(
            "pipeline_finished"
        )

        worker = self.worker
        self.worker = None

        if worker is not None:
            worker.deleteLater()

        self._cancel_requested = False

    # =========================================================
    # VALIDATION
    # =========================================================

    @staticmethod
    def _validate_scenes(
        scenes: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not isinstance(
            scenes,
            list,
        ):
            raise TypeError(
                "Danh sách cảnh không hợp lệ."
            )

        if not scenes:
            raise ValueError(
                "Không có cảnh để tạo video."
            )

        validated: list[dict[str, Any]] = []

        for index, scene in enumerate(
            scenes,
            start=1,
        ):
            if not isinstance(
                scene,
                dict,
            ):
                raise TypeError(
                    f"Cảnh {index} không phải dictionary."
                )

            validated.append(
                dict(scene)
            )

        return validated

    # =========================================================
    # CLEANUP
    # =========================================================

    def _dispose_finished_worker(
        self,
    ) -> None:
        if self.worker is None:
            return

        if self.worker.isRunning():
            raise RuntimeError(
                "Pipeline trước vẫn đang chạy."
            )

        self.worker.deleteLater()
        self.worker = None

    def shutdown(
        self,
        wait_ms: int = 3000,
    ) -> bool:
        """
        Yêu cầu dừng và chờ worker khi ứng dụng chuẩn bị đóng.

        Trả về True nếu worker đã dừng trong thời gian chờ.
        """

        if self.worker is None:
            return True

        if not self.worker.isRunning():
            self._dispose_finished_worker()
            return True

        self.cancel()

        stopped = self.worker.wait(
            max(0, int(wait_ms))
        )

        return bool(
            stopped
        )

    # =========================================================
    # EVENT BUS
    # =========================================================

    def _emit_event_bus(
        self,
        signal_name: str,
        *args: object,
    ) -> None:
        if self.event_bus is None:
            return

        signal = getattr(
            self.event_bus,
            signal_name,
            None,
        )

        if signal is None:
            return

        emit = getattr(
            signal,
            "emit",
            None,
        )

        if emit is None:
            return

        emit(
            *args
        )