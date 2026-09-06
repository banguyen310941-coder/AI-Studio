from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal

from app.agents.script_agent import ScriptAgent
from app.models.project_model import ProjectModel
from app.services.history_service import HistoryService


class ScriptController(QObject):
    """
    Điều phối việc tạo kịch bản AI.

    Trách nhiệm:
    - Kiểm tra chủ đề.
    - Gọi ScriptAgent.
    - Cập nhật ProjectModel.
    - Lưu snapshot vào HistoryService.
    - Phát signal để giao diện cập nhật trạng thái.
    """

    generation_started = Signal()
    generation_finished = Signal(int)
    generation_failed = Signal(str)

    warning_requested = Signal(str, str)

    def __init__(
        self,
        project_model: ProjectModel,
        history_service: HistoryService,
        parent: QObject | None = None,
        script_agent: ScriptAgent | None = None,
    ) -> None:
        super().__init__(parent)

        self.project_model = project_model
        self.history_service = history_service
        self.script_agent = (
            script_agent
            if script_agent is not None
            else ScriptAgent()
        )

        self._running = False

    def is_running(self) -> bool:
        return self._running

    def generate(
        self,
        topic: str,
    ) -> bool:
        """
        Tạo kịch bản từ chủ đề.

        Trả về True nếu thao tác hoàn tất thành công.
        Trả về False nếu thiếu chủ đề, đang chạy hoặc phát sinh lỗi.
        """

        clean_topic = topic.strip()

        if not clean_topic:
            self.warning_requested.emit(
                "Thiếu chủ đề",
                "Bạn hãy nhập chủ đề video trước.",
            )
            return False

        if self._running:
            return False

        self._running = True
        self.generation_started.emit()

        try:
            scenes = self.script_agent.generate(
                clean_topic
            )

            normalized_scenes = self._normalize_scenes(
                scenes
            )

            topic_changed = self.project_model.set_topic(
                clean_topic
            )

            scenes_changed = self.project_model.set_scenes(
                scenes=normalized_scenes,
                description="AI tạo kịch bản",
                mark_dirty=True,
            )

            if topic_changed or scenes_changed:
                self.history_service.push(
                    state=self.project_model.create_snapshot(),
                    description="AI tạo kịch bản",
                )

            self.generation_finished.emit(
                len(normalized_scenes)
            )
            return True

        except Exception as error:
            self.generation_failed.emit(
                str(error)
            )
            return False

        finally:
            self._running = False

    @staticmethod
    def _normalize_scenes(
        scenes: Any,
    ) -> list[dict[str, Any]]:
        """
        Kiểm tra kết quả từ ScriptAgent và chuẩn hóa về list[dict].
        """

        if not isinstance(scenes, list):
            raise TypeError(
                "ScriptAgent phải trả về một danh sách cảnh."
            )

        normalized: list[dict[str, Any]] = []

        for index, scene in enumerate(
            scenes,
            start=1,
        ):
            if not isinstance(scene, dict):
                raise TypeError(
                    f"Cảnh {index} không phải là dictionary."
                )

            normalized.append(
                dict(scene)
            )

        return normalized
