from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget,
)

from app.widgets.scene_card import SceneCard


class SceneListView(QWidget):
    """
    Widget quản lý danh sách SceneCard.

    Trách nhiệm:
    - Tạo SceneCard khi có cảnh mới.
    - Cập nhật SceneCard hiện có.
    - Xóa SceneCard thừa.
    - Chuyển tiếp các tín hiệu chỉnh sửa và tạo media.
    - Cung cấp API tìm và cập nhật từng SceneCard.

    SceneListView không trực tiếp thao tác với ProjectModel.
    ProjectPage vẫn là thành phần kết nối View với Model.
    """

    scene_field_changed = Signal(
        int,
        str,
        str,
    )

    image_requested = Signal(
        int,
        str,
    )

    voice_requested = Signal(
        int,
        str,
    )

    video_requested = Signal(
        int,
    )

    scene_count_changed = Signal(
        int,
    )

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._scene_cards: list[SceneCard] = []
        self._updating_scenes = False

        self._build_ui()

    def _build_ui(self) -> None:
        self.scene_layout = QVBoxLayout(self)

        self.scene_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.scene_layout.setSpacing(
            15
        )

        self.scene_layout.addStretch()

    def set_scenes(
        self,
        scenes: list[dict[str, Any]],
    ) -> None:
        """
        Đồng bộ danh sách SceneCard với danh sách cảnh.

        Nếu số lượng cảnh không thay đổi, các card hiện có chỉ được
        cập nhật bằng set_data(), không bị xóa và tạo lại.

        Nếu có thêm cảnh, chỉ tạo những card còn thiếu.

        Nếu giảm số cảnh, chỉ xóa những card dư.
        """

        if not isinstance(
            scenes,
            list,
        ):
            raise TypeError(
                "Danh sách cảnh phải là list."
            )

        self._updating_scenes = True

        try:
            self._remove_extra_cards(
                target_count=len(scenes)
            )

            for index, scene_data in enumerate(
                scenes,
                start=1,
            ):
                if not isinstance(
                    scene_data,
                    dict,
                ):
                    raise TypeError(
                        (
                            "Dữ liệu Cảnh "
                            f"{index} phải là dict."
                        )
                    )

                if index <= len(
                    self._scene_cards
                ):
                    self._update_existing_card(
                        scene_number=index,
                        scene_data=scene_data,
                    )
                else:
                    self._create_card(
                        scene_number=index,
                        scene_data=scene_data,
                    )

            self._renumber_cards()

        finally:
            self._updating_scenes = False

        self.scene_count_changed.emit(
            len(self._scene_cards)
        )

    def _create_card(
        self,
        scene_number: int,
        scene_data: dict[str, Any],
    ) -> SceneCard:
        """
        Tạo một SceneCard mới và kết nối tín hiệu.
        """

        card = SceneCard(
            scene_number=scene_number,
            title=self._get_text(
                scene_data,
                "title",
            ),
            visual=self._get_text(
                scene_data,
                "visual",
            ),
            narration=self._get_text(
                scene_data,
                "narration",
            ),
            screen_text=self._get_text(
                scene_data,
                "screen_text",
            ),
            image_prompt=self._get_text(
                scene_data,
                "image_prompt",
            ),
        )

        card.field_changed.connect(
            self._handle_field_changed
        )

        card.image_requested.connect(
            self.image_requested.emit
        )

        card.voice_requested.connect(
            self.voice_requested.emit
        )

        card.video_requested.connect(
            self.video_requested.emit
        )

        self._scene_cards.append(
            card
        )

        insert_position = (
            self.scene_layout.count() - 1
        )

        self.scene_layout.insertWidget(
            insert_position,
            card,
        )

        return card

    def _update_existing_card(
        self,
        scene_number: int,
        scene_data: dict[str, Any],
    ) -> None:
        """
        Cập nhật một card đã tồn tại mà không dựng lại widget.
        """

        card = self._scene_cards[
            scene_number - 1
        ]

        if (
            card.scene_number
            != scene_number
        ):
            card.set_scene_number(
                scene_number
            )

        card.set_data(
            scene_data
        )

    def _remove_extra_cards(
        self,
        target_count: int,
    ) -> None:
        """
        Xóa những SceneCard vượt quá số lượng cảnh cần hiển thị.
        """

        while (
            len(self._scene_cards)
            > target_count
        ):
            card = self._scene_cards.pop()

            self.scene_layout.removeWidget(
                card
            )

            card.deleteLater()

    def _renumber_cards(self) -> None:
        """
        Đồng bộ lại số thứ tự của tất cả SceneCard.
        """

        for scene_number, card in enumerate(
            self._scene_cards,
            start=1,
        ):
            if (
                card.scene_number
                != scene_number
            ):
                card.set_scene_number(
                    scene_number
                )

    def _handle_field_changed(
        self,
        scene_number: int,
        field_name: str,
        value: str,
    ) -> None:
        """
        Chuyển tiếp thay đổi từ SceneCard lên ProjectPage.
        """

        if self._updating_scenes:
            return

        self.scene_field_changed.emit(
            scene_number,
            field_name,
            value,
        )

    def clear(self) -> None:
        """
        Xóa toàn bộ SceneCard.
        """

        while self._scene_cards:
            card = self._scene_cards.pop()

            self.scene_layout.removeWidget(
                card
            )

            card.deleteLater()

        self.scene_count_changed.emit(
            0
        )

    def get_card(
        self,
        scene_number: int,
    ) -> SceneCard | None:
        """
        Trả về SceneCard theo số thứ tự bắt đầu từ 1.
        """

        if scene_number <= 0:
            return None

        index = scene_number - 1

        if index >= len(
            self._scene_cards
        ):
            return None

        return self._scene_cards[index]

    def get_cards(
        self,
    ) -> list[SceneCard]:
        """
        Trả về bản sao danh sách SceneCard.
        """

        return list(
            self._scene_cards
        )

    def get_scene_count(self) -> int:
        return len(
            self._scene_cards
        )

    def update_scene(
        self,
        scene_number: int,
        scene_data: dict[str, Any],
    ) -> bool:
        """
        Cập nhật riêng một SceneCard.

        Trả về False nếu không tìm thấy card.
        """

        card = self.get_card(
            scene_number
        )

        if card is None:
            return False

        self._updating_scenes = True

        try:
            card.set_data(
                scene_data
            )

        finally:
            self._updating_scenes = False

        return True

    def display_image(
        self,
        scene_number: int,
        image_path: Path,
    ) -> bool:
        """
        Hiển thị ảnh của một cảnh.
        """

        card = self.get_card(
            scene_number
        )

        if card is None:
            return False

        card.display_image(
            image_path
        )

        return True

    def display_voice(
        self,
        scene_number: int,
        audio_path: Path,
    ) -> bool:
        """
        Hiển thị trạng thái giọng đọc của một cảnh.
        """

        card = self.get_card(
            scene_number
        )

        if card is None:
            return False

        card.display_voice(
            audio_path
        )

        return True

    def display_video(
        self,
        scene_number: int,
        video_path: Path,
    ) -> bool:
        """
        Hiển thị trạng thái video của một cảnh.
        """

        card = self.get_card(
            scene_number
        )

        if card is None:
            return False

        card.display_video(
            video_path
        )

        return True

    def set_image_loading(
        self,
        scene_number: int,
        loading: bool,
    ) -> bool:
        """
        Cập nhật trạng thái tạo ảnh của một cảnh.
        """

        card = self.get_card(
            scene_number
        )

        if card is None:
            return False

        card.set_image_loading(
            loading
        )

        return True

    def set_voice_loading(
        self,
        scene_number: int,
        loading: bool,
    ) -> bool:
        """
        Cập nhật trạng thái tạo giọng đọc của một cảnh.
        """

        card = self.get_card(
            scene_number
        )

        if card is None:
            return False

        card.set_voice_loading(
            loading
        )

        return True

    def set_video_loading(
        self,
        scene_number: int,
        loading: bool,
    ) -> bool:
        """
        Cập nhật trạng thái tạo video của một cảnh.
        """

        card = self.get_card(
            scene_number
        )

        if card is None:
            return False

        card.set_video_loading(
            loading
        )

        return True

    @staticmethod
    def _get_text(
        scene_data: dict[str, Any],
        field_name: str,
    ) -> str:
        value = scene_data.get(
            field_name,
            "",
        )

        if value is None:
            return ""

        return str(value)