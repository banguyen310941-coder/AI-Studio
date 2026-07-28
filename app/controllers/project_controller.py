from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal

from app.models.project_model import ProjectModel
from app.project_manager import ProjectManager
from app.services.history_service import HistoryService


class ProjectController(QObject):
    """
    Điều phối việc mở, lưu và quản lý đường dẫn của dự án hiện tại.

    ProjectPage chỉ hiển thị giao diện và hộp thoại. Controller này:
    - Chọn dự án hiện tại.
    - Tải dữ liệu vào ProjectModel.
    - Khởi tạo HistoryService.
    - Lưu cảnh và file kịch bản.
    - Quản lý snapshot đã lưu gần nhất.
    - Cung cấp đường dẫn dự án và video hoàn chỉnh.
    """

    project_loading = Signal(str)
    project_loaded = Signal(str, int)
    project_load_failed = Signal(str)

    project_saving = Signal()
    project_saved = Signal(int)
    project_save_failed = Signal(str)

    current_project_changed = Signal(str)

    def __init__(
        self,
        project_manager: ProjectManager,
        project_model: ProjectModel | None = None,
        history_service: HistoryService | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self.project_manager = project_manager
        self.project_model = project_model
        self.history_service = history_service

        self.current_project_name = ""
        self._saved_snapshot: dict[str, Any] | None = None

    # =========================================================
    # DEPENDENCIES
    # =========================================================

    def set_project_model(
        self,
        project_model: ProjectModel,
    ) -> None:
        self.project_model = project_model

    def set_history_service(
        self,
        history_service: HistoryService,
    ) -> None:
        self.history_service = history_service

    def _require_project_model(self) -> ProjectModel:
        if self.project_model is None:
            raise RuntimeError(
                "ProjectController chưa được gắn ProjectModel."
            )

        return self.project_model

    def _require_history_service(self) -> HistoryService:
        if self.history_service is None:
            raise RuntimeError(
                "ProjectController chưa được gắn HistoryService."
            )

        return self.history_service

    # =========================================================
    # CURRENT PROJECT
    # =========================================================

    def set_current_project(
        self,
        project_name: str,
    ) -> None:
        clean_name = project_name.strip()

        if not clean_name:
            raise ValueError(
                "Tên dự án không được để trống."
            )

        changed = (
            clean_name
            != self.current_project_name
        )

        self.current_project_name = clean_name

        if changed:
            self.current_project_changed.emit(
                clean_name
            )

    def clear_current_project(self) -> None:
        self.current_project_name = ""
        self._saved_snapshot = None

    def ensure_project_selected(self) -> None:
        if not self.current_project_name:
            raise RuntimeError(
                "Chưa chọn dự án để thao tác."
            )

    # =========================================================
    # PATHS
    # =========================================================

    def get_project_path(self) -> Path:
        self.ensure_project_selected()

        return (
            Path(self.project_manager.projects_directory)
            / self.current_project_name
        )

    def get_final_video_path(self) -> Path:
        return (
            self.get_project_path()
            / "output"
            / "final_video.mp4"
        )

    # =========================================================
    # LOAD
    # =========================================================

    def open_project(
        self,
        project_name: str,
    ) -> bool:
        """
        Tải dự án vào ProjectModel và khởi tạo lịch sử.

        Trả về True khi thành công.
        """

        clean_name = project_name.strip()

        if not clean_name:
            self.project_load_failed.emit(
                "Tên dự án không được để trống."
            )
            return False

        self.project_loading.emit(
            clean_name
        )

        try:
            self.set_current_project(
                clean_name
            )

            scenes = self.project_manager.load_scenes(
                self.current_project_name
            )

            if scenes is None:
                scenes = []

            if not isinstance(scenes, list):
                raise TypeError(
                    "Dữ liệu cảnh của dự án không hợp lệ."
                )

            model = self._require_project_model()
            history = self._require_history_service()

            model.initialize(
                project_name=self.current_project_name,
                scenes=scenes,
                topic="",
                mark_clean=True,
            )

            initial_snapshot = (
                model.create_snapshot()
            )

            self._saved_snapshot = deepcopy(
                initial_snapshot
            )

            history.initialize(
                initial_state=initial_snapshot,
                description="Mở dự án",
            )

            self.project_loaded.emit(
                self.current_project_name,
                len(scenes),
            )
            return True

        except Exception as error:
            self.project_load_failed.emit(
                str(error)
            )
            return False

    def load_project(
        self,
        project_name: str,
    ) -> list[dict]:
        """
        API tương thích với code cũ.

        Chỉ tải và trả về danh sách cảnh, không cập nhật model/history.
        """

        self.set_current_project(
            project_name
        )

        scenes = self.project_manager.load_scenes(
            self.current_project_name
        )

        if scenes is None:
            return []

        if not isinstance(scenes, list):
            raise TypeError(
                "Dữ liệu cảnh của dự án không hợp lệ."
            )

        return scenes

    # =========================================================
    # SAVE
    # =========================================================

    def save_current_project(self) -> bool:
        """
        Lưu dữ liệu hiện tại trong ProjectModel.
        """

        self.project_saving.emit()

        try:
            self.ensure_project_selected()

            model = self._require_project_model()
            scenes = model.get_scenes()

            if not scenes:
                raise ValueError(
                    "Không có dữ liệu cảnh để lưu."
                )

            saved = self._save_scenes(
                scenes
            )

            if not saved:
                raise RuntimeError(
                    "Không thể lưu dữ liệu dự án."
                )

            model.mark_clean()

            self._saved_snapshot = deepcopy(
                model.create_snapshot()
            )

            self.project_saved.emit(
                len(scenes)
            )
            return True

        except Exception as error:
            self.project_save_failed.emit(
                str(error)
            )
            return False

    def save_project(
        self,
        scenes: list[dict],
    ) -> bool:
        """
        API tương thích với code cũ.
        """

        self.ensure_project_selected()

        if not scenes:
            return False

        return self._save_scenes(
            scenes
        )

    def _save_scenes(
        self,
        scenes: list[dict],
    ) -> bool:
        scenes_saved = (
            self.project_manager.save_scenes(
                self.current_project_name,
                scenes,
            )
        )

        if not scenes_saved:
            return False

        script_text = self.create_script_text(
            scenes
        )

        return bool(
            self.project_manager.save_script(
                self.current_project_name,
                script_text,
            )
        )

    # =========================================================
    # SAVED STATE
    # =========================================================

    def get_saved_snapshot(
        self,
    ) -> dict[str, Any] | None:
        if self._saved_snapshot is None:
            return None

        return deepcopy(
            self._saved_snapshot
        )

    def snapshot_matches_saved(
        self,
        snapshot: dict[str, Any],
    ) -> bool:
        """
        Kiểm tra snapshot có giống trạng thái đã lưu gần nhất không.
        """

        if self._saved_snapshot is None:
            return False

        return (
            snapshot.get("project_name")
            == self._saved_snapshot.get(
                "project_name"
            )
            and snapshot.get("topic", "")
            == self._saved_snapshot.get(
                "topic",
                "",
            )
            and snapshot.get("scenes", [])
            == self._saved_snapshot.get(
                "scenes",
                [],
            )
        )

    # =========================================================
    # SCRIPT EXPORT
    # =========================================================

    @staticmethod
    def create_script_text(
        scenes: list[dict],
    ) -> str:
        sections: list[str] = []

        for index, scene in enumerate(
            scenes,
            start=1,
        ):
            sections.append(
                (
                    f"CẢNH {index}: "
                    f"{scene.get('title', '')}\n\n"
                    "Hình ảnh:\n"
                    f"{scene.get('visual', '')}\n\n"
                    "Lời đọc:\n"
                    f"{scene.get('narration', '')}\n\n"
                    "Chữ trên màn hình:\n"
                    f"{scene.get('screen_text', '')}\n\n"
                    "Prompt ảnh:\n"
                    f"{scene.get('image_prompt', '')}"
                )
            )

        separator = (
            "\n\n"
            + "-" * 50
            + "\n\n"
        )

        return separator.join(
            sections
        )
