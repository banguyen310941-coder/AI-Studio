from __future__ import annotations

from copy import deepcopy
from typing import Any

from PySide6.QtCore import QObject, Signal

from app.core.logger import get_logger


logger = get_logger(__name__)


class ProjectModel(QObject):
    """
    Nguồn dữ liệu trung tâm của dự án đang mở.

    ProjectModel không trực tiếp thao tác với giao diện hoặc file.

    Trách nhiệm:
    - Lưu tên dự án hiện tại.
    - Lưu chủ đề video.
    - Lưu danh sách cảnh.
    - Chuẩn hóa dữ liệu cảnh.
    - Theo dõi trạng thái đã thay đổi.
    - Phát tín hiệu khi dữ liệu thay đổi.

    Mọi dữ liệu trả ra đều được deepcopy để tránh code bên ngoài
    vô tình sửa trực tiếp dữ liệu bên trong model.
    """

    project_changed = Signal()
    scenes_changed = Signal(list)
    scene_changed = Signal(int, dict)
    dirty_changed = Signal(bool)

    SCENE_FIELDS = (
        "title",
        "visual",
        "narration",
        "screen_text",
        "image_prompt",
    )

    def __init__(
        self,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self._project_name = ""
        self._topic = ""
        self._scenes: list[dict[str, str]] = []
        self._dirty = False

        logger.info(
            "ProjectModel đã được khởi tạo."
        )

    def initialize(
        self,
        project_name: str,
        scenes: list[dict[str, Any]] | None = None,
        topic: str = "",
        mark_clean: bool = True,
    ) -> None:
        """
        Khởi tạo dữ liệu của dự án đang mở.

        Dùng khi:
        - Mở một dự án.
        - Chuyển sang dự án khác.
        - Tạo dự án mới.

        Nếu mark_clean=True, dự án được xem là vừa tải từ file
        và chưa có thay đổi chưa lưu.
        """

        clean_project_name = project_name.strip()

        if not clean_project_name:
            raise ValueError(
                "Tên dự án không được để trống."
            )

        self._project_name = clean_project_name
        self._topic = topic.strip()
        self._scenes = self._normalize_scenes(
            scenes or []
        )

        self._set_dirty(
            not mark_clean
        )

        logger.info(
            "Đã khởi tạo ProjectModel. project=%s, scenes=%s",
            self._project_name,
            len(self._scenes),
        )

        self.project_changed.emit()
        self.scenes_changed.emit(
            self.get_scenes()
        )

    def clear(self) -> None:
        """
        Xóa toàn bộ dữ liệu dự án khỏi model.
        """

        self._project_name = ""
        self._topic = ""
        self._scenes.clear()

        self._set_dirty(False)

        logger.info(
            "Đã xóa dữ liệu ProjectModel."
        )

        self.project_changed.emit()
        self.scenes_changed.emit([])

    def get_project_name(self) -> str:
        return self._project_name

    def set_project_name(
        self,
        project_name: str,
    ) -> bool:
        """
        Đổi tên dự án trong model.

        Trả về True nếu dữ liệu thực sự thay đổi.
        """

        clean_project_name = project_name.strip()

        if not clean_project_name:
            raise ValueError(
                "Tên dự án không được để trống."
            )

        if clean_project_name == self._project_name:
            return False

        self._project_name = clean_project_name
        self._mark_changed()

        logger.info(
            "Đã đổi tên dự án thành %s.",
            clean_project_name,
        )

        return True

    def get_topic(self) -> str:
        return self._topic

    def set_topic(
        self,
        topic: str,
    ) -> bool:
        """
        Cập nhật chủ đề video.
        """

        clean_topic = topic.strip()

        if clean_topic == self._topic:
            return False

        self._topic = clean_topic
        self._mark_changed()

        logger.debug(
            "Đã cập nhật chủ đề dự án."
        )

        return True

    def get_scenes(self) -> list[dict[str, str]]:
        """
        Trả về bản sao danh sách cảnh.
        """

        return deepcopy(
            self._scenes
        )

    def set_scenes(
        self,
        scenes: list[dict[str, Any]],
        description: str = "Cập nhật danh sách cảnh",
        mark_dirty: bool = True,
    ) -> bool:
        """
        Thay toàn bộ danh sách cảnh.

        Dùng khi:
        - AI tạo lại kịch bản.
        - Undo/Redo khôi phục snapshot.
        - Đồng bộ dữ liệu từ bên ngoài.
        """

        normalized_scenes = (
            self._normalize_scenes(
                scenes
            )
        )

        if normalized_scenes == self._scenes:
            return False

        self._scenes = normalized_scenes

        if mark_dirty:
            self._mark_changed()
        else:
            self.project_changed.emit()

        self.scenes_changed.emit(
            self.get_scenes()
        )

        logger.info(
            "%s. scene_count=%s",
            description,
            len(self._scenes),
        )

        return True

    def get_scene_count(self) -> int:
        return len(
            self._scenes
        )

    def has_scenes(self) -> bool:
        return bool(
            self._scenes
        )

    def get_scene(
        self,
        scene_number: int,
    ) -> dict[str, str] | None:
        """
        Trả về một cảnh theo số thứ tự bắt đầu từ 1.
        """

        index = self._scene_number_to_index(
            scene_number
        )

        if index >= len(self._scenes):
            return None

        return deepcopy(
            self._scenes[index]
        )

    def update_scene(
        self,
        scene_number: int,
        scene_data: dict[str, Any],
    ) -> bool:
        """
        Cập nhật toàn bộ dữ liệu của một cảnh.

        scene_number bắt đầu từ 1.
        """

        index = self._scene_number_to_index(
            scene_number
        )

        if index >= len(self._scenes):
            raise IndexError(
                f"Không tìm thấy Cảnh {scene_number}."
            )

        normalized_scene = (
            self._normalize_scene(
                scene_data
            )
        )

        if normalized_scene == self._scenes[index]:
            return False

        self._scenes[index] = normalized_scene
        self._mark_changed()

        self.scene_changed.emit(
            scene_number,
            deepcopy(normalized_scene),
        )

        logger.debug(
            "Đã cập nhật Cảnh %s.",
            scene_number,
        )

        return True

    def update_scene_field(
        self,
        scene_number: int,
        field_name: str,
        value: Any,
    ) -> bool:
        """
        Cập nhật một trường của một cảnh.

        Ví dụ:

            update_scene_field(
                1,
                "narration",
                "Nội dung mới",
            )
        """

        if field_name not in self.SCENE_FIELDS:
            raise KeyError(
                (
                    f"Trường cảnh không hợp lệ: {field_name}. "
                    f"Các trường hợp lệ: {self.SCENE_FIELDS}"
                )
            )

        index = self._scene_number_to_index(
            scene_number
        )

        if index >= len(self._scenes):
            raise IndexError(
                f"Không tìm thấy Cảnh {scene_number}."
            )

        clean_value = (
            ""
            if value is None
            else str(value)
        )

        if (
            self._scenes[index][field_name]
            == clean_value
        ):
            return False

        self._scenes[index][field_name] = (
            clean_value
        )

        self._mark_changed()

        self.scene_changed.emit(
            scene_number,
            deepcopy(self._scenes[index]),
        )

        logger.debug(
            "Đã cập nhật %s của Cảnh %s.",
            field_name,
            scene_number,
        )

        return True

    def add_scene(
        self,
        scene_data: dict[str, Any] | None = None,
        position: int | None = None,
    ) -> int:
        """
        Thêm một cảnh mới.

        Nếu position=None, cảnh được thêm vào cuối.

        position là vị trí theo kiểu người dùng, bắt đầu từ 1.

        Trả về số thứ tự của cảnh vừa thêm.
        """

        normalized_scene = (
            self._normalize_scene(
                scene_data or {}
            )
        )

        if position is None:
            self._scenes.append(
                normalized_scene
            )
            scene_number = len(
                self._scenes
            )
        else:
            if position <= 0:
                raise ValueError(
                    "Vị trí cảnh phải lớn hơn 0."
                )

            insert_index = min(
                position - 1,
                len(self._scenes),
            )

            self._scenes.insert(
                insert_index,
                normalized_scene,
            )

            scene_number = (
                insert_index + 1
            )

        self._mark_changed()

        self.scenes_changed.emit(
            self.get_scenes()
        )

        logger.info(
            "Đã thêm Cảnh %s.",
            scene_number,
        )

        return scene_number

    def remove_scene(
        self,
        scene_number: int,
    ) -> dict[str, str]:
        """
        Xóa một cảnh và trả về dữ liệu cảnh đã xóa.
        """

        index = self._scene_number_to_index(
            scene_number
        )

        if index >= len(self._scenes):
            raise IndexError(
                f"Không tìm thấy Cảnh {scene_number}."
            )

        removed_scene = self._scenes.pop(
            index
        )

        self._mark_changed()

        self.scenes_changed.emit(
            self.get_scenes()
        )

        logger.info(
            "Đã xóa Cảnh %s.",
            scene_number,
        )

        return deepcopy(
            removed_scene
        )

    def move_scene(
        self,
        scene_number: int,
        new_position: int,
    ) -> bool:
        """
        Di chuyển một cảnh sang vị trí mới.

        scene_number và new_position đều bắt đầu từ 1.
        """

        old_index = self._scene_number_to_index(
            scene_number
        )

        if old_index >= len(self._scenes):
            raise IndexError(
                f"Không tìm thấy Cảnh {scene_number}."
            )

        if new_position <= 0:
            raise ValueError(
                "Vị trí mới phải lớn hơn 0."
            )

        new_index = min(
            new_position - 1,
            len(self._scenes) - 1,
        )

        if old_index == new_index:
            return False

        scene = self._scenes.pop(
            old_index
        )

        self._scenes.insert(
            new_index,
            scene,
        )

        self._mark_changed()

        self.scenes_changed.emit(
            self.get_scenes()
        )

        logger.info(
            "Đã di chuyển Cảnh %s đến vị trí %s.",
            scene_number,
            new_index + 1,
        )

        return True

    def create_snapshot(
        self,
    ) -> dict[str, Any]:
        """
        Tạo snapshot để HistoryService lưu lại.
        """

        return {
            "project_name": self._project_name,
            "topic": self._topic,
            "scenes": self.get_scenes(),
        }

    def restore_snapshot(
        self,
        snapshot: dict[str, Any],
        mark_dirty: bool = True,
    ) -> None:
        """
        Khôi phục dữ liệu từ snapshot.

        Hàm này sẽ được dùng cho Undo/Redo.
        """

        if not isinstance(
            snapshot,
            dict,
        ):
            raise TypeError(
                "Snapshot dự án phải là dict."
            )

        project_name = str(
            snapshot.get(
                "project_name",
                self._project_name,
            )
        ).strip()

        if project_name:
            self._project_name = project_name

        self._topic = str(
            snapshot.get(
                "topic",
                "",
            )
        )

        scenes = snapshot.get(
            "scenes",
            [],
        )

        if not isinstance(
            scenes,
            list,
        ):
            raise TypeError(
                "Danh sách scenes trong snapshot phải là list."
            )

        self._scenes = self._normalize_scenes(
            scenes
        )

        self._set_dirty(
            mark_dirty
        )

        self.project_changed.emit()
        self.scenes_changed.emit(
            self.get_scenes()
        )

        logger.info(
            "Đã khôi phục snapshot dự án. scenes=%s",
            len(self._scenes),
        )

    def is_dirty(self) -> bool:
        """
        Trả về True nếu dự án có thay đổi chưa lưu.
        """

        return self._dirty

    def mark_clean(self) -> None:
        """
        Đánh dấu dự án đã được lưu.
        """

        self._set_dirty(False)

        logger.debug(
            "ProjectModel đã được đánh dấu clean."
        )

    def mark_dirty(self) -> None:
        """
        Đánh dấu dự án có thay đổi chưa lưu.
        """

        self._set_dirty(True)

    def _mark_changed(self) -> None:
        self._set_dirty(True)
        self.project_changed.emit()

    def _set_dirty(
        self,
        dirty: bool,
    ) -> None:
        dirty = bool(
            dirty
        )

        if dirty == self._dirty:
            return

        self._dirty = dirty

        self.dirty_changed.emit(
            self._dirty
        )

    @classmethod
    def _normalize_scenes(
        cls,
        scenes: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        if not isinstance(
            scenes,
            list,
        ):
            raise TypeError(
                "Danh sách cảnh phải là list."
            )

        normalized_scenes: list[
            dict[str, str]
        ] = []

        for scene in scenes:
            normalized_scenes.append(
                cls._normalize_scene(
                    scene
                )
            )

        return normalized_scenes

    @classmethod
    def _normalize_scene(
        cls,
        scene: dict[str, Any],
    ) -> dict[str, str]:
        if not isinstance(
            scene,
            dict,
        ):
            raise TypeError(
                "Dữ liệu cảnh phải là dict."
            )

        normalized_scene: dict[str, str] = {}

        for field_name in cls.SCENE_FIELDS:
            value = scene.get(
                field_name,
                "",
            )

            normalized_scene[field_name] = (
                ""
                if value is None
                else str(value)
            )

        return normalized_scene

    @staticmethod
    def _scene_number_to_index(
        scene_number: int,
    ) -> int:
        if scene_number <= 0:
            raise ValueError(
                "Số thứ tự cảnh phải lớn hơn 0."
            )

        return scene_number - 1