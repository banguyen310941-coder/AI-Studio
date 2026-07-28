from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)


class SceneEditorToolbar(QFrame):
    """
    Thanh công cụ chỉnh sửa danh sách cảnh.

    Toolbar không trực tiếp thao tác với ProjectModel.

    Nó chỉ phát tín hiệu để ProjectPage xử lý:

    - Thêm cảnh.
    - Nhân đôi cảnh.
    - Xóa cảnh.
    - Di chuyển cảnh lên.
    - Di chuyển cảnh xuống.
    - Chọn cảnh hiện tại.
    - Undo.
    - Redo.
    """

    add_scene_requested = Signal()
    duplicate_scene_requested = Signal(int)
    delete_scene_requested = Signal(int)
    move_scene_up_requested = Signal(int)
    move_scene_down_requested = Signal(int)

    scene_selected = Signal(int)

    undo_requested = Signal()
    redo_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._scene_count = 0
        self._updating_selector = False

        self.setObjectName("card")

        self._build_ui()
        self._connect_signals()
        self._update_controls()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)

        layout.setContentsMargins(
            16,
            12,
            16,
            12,
        )

        layout.setSpacing(8)

        title_label = QLabel(
            "Chỉnh sửa cảnh"
        )
        title_label.setObjectName(
            "cardTitle"
        )

        self.scene_selector = QComboBox()
        self.scene_selector.setMinimumWidth(
            130
        )
        self.scene_selector.setToolTip(
            "Chọn cảnh đang thao tác"
        )

        self.add_button = QPushButton(
            "➕ Thêm cảnh"
        )
        self.add_button.setObjectName(
            "secondaryButton"
        )
        self.add_button.setToolTip(
            "Thêm một cảnh mới vào cuối danh sách"
        )

        self.duplicate_button = QPushButton(
            "📄 Nhân đôi"
        )
        self.duplicate_button.setObjectName(
            "secondaryButton"
        )
        self.duplicate_button.setToolTip(
            "Tạo một bản sao của cảnh đang chọn"
        )

        self.delete_button = QPushButton(
            "🗑 Xóa"
        )
        self.delete_button.setObjectName(
            "secondaryButton"
        )
        self.delete_button.setToolTip(
            "Xóa cảnh đang chọn"
        )

        self.move_up_button = QPushButton(
            "↑ Lên"
        )
        self.move_up_button.setObjectName(
            "secondaryButton"
        )
        self.move_up_button.setToolTip(
            "Di chuyển cảnh đang chọn lên trên"
        )

        self.move_down_button = QPushButton(
            "↓ Xuống"
        )
        self.move_down_button.setObjectName(
            "secondaryButton"
        )
        self.move_down_button.setToolTip(
            "Di chuyển cảnh đang chọn xuống dưới"
        )

        self.undo_button = QPushButton(
            "↶ Hoàn tác"
        )
        self.undo_button.setObjectName(
            "secondaryButton"
        )
        self.undo_button.setToolTip(
            "Hoàn tác thay đổi gần nhất"
        )

        self.redo_button = QPushButton(
            "↷ Làm lại"
        )
        self.redo_button.setObjectName(
            "secondaryButton"
        )
        self.redo_button.setToolTip(
            "Khôi phục thay đổi vừa hoàn tác"
        )

        layout.addWidget(
            title_label
        )

        layout.addSpacing(8)

        layout.addWidget(
            self.scene_selector
        )

        layout.addWidget(
            self.add_button
        )

        layout.addWidget(
            self.duplicate_button
        )

        layout.addWidget(
            self.delete_button
        )

        layout.addWidget(
            self.move_up_button
        )

        layout.addWidget(
            self.move_down_button
        )

        layout.addStretch()

        layout.addWidget(
            self.undo_button
        )

        layout.addWidget(
            self.redo_button
        )

    def _connect_signals(self) -> None:
        self.scene_selector.currentIndexChanged.connect(
            self._handle_scene_selection
        )

        self.add_button.clicked.connect(
            self.add_scene_requested.emit
        )

        self.duplicate_button.clicked.connect(
            self._emit_duplicate_request
        )

        self.delete_button.clicked.connect(
            self._emit_delete_request
        )

        self.move_up_button.clicked.connect(
            self._emit_move_up_request
        )

        self.move_down_button.clicked.connect(
            self._emit_move_down_request
        )

        self.undo_button.clicked.connect(
            self.undo_requested.emit
        )

        self.redo_button.clicked.connect(
            self.redo_requested.emit
        )

    def set_scene_count(
        self,
        scene_count: int,
    ) -> None:
        """
        Đồng bộ số lượng cảnh vào combobox.

        Cảnh đang chọn sẽ được giữ lại khi có thể.
        """

        if scene_count < 0:
            raise ValueError(
                "Số lượng cảnh không được âm."
            )

        current_scene = (
            self.get_selected_scene_number()
        )

        self._scene_count = scene_count
        self._updating_selector = True

        try:
            self.scene_selector.clear()

            for scene_number in range(
                1,
                scene_count + 1,
            ):
                self.scene_selector.addItem(
                    f"Cảnh {scene_number}",
                    scene_number,
                )

            if scene_count > 0:
                target_scene = min(
                    max(current_scene, 1),
                    scene_count,
                )

                self.scene_selector.setCurrentIndex(
                    target_scene - 1
                )

        finally:
            self._updating_selector = False

        self._update_controls()

    def set_selected_scene(
        self,
        scene_number: int,
    ) -> bool:
        """
        Chọn một cảnh trong combobox.

        Trả về False nếu cảnh không tồn tại.
        """

        if (
            scene_number <= 0
            or scene_number > self._scene_count
        ):
            return False

        self._updating_selector = True

        try:
            self.scene_selector.setCurrentIndex(
                scene_number - 1
            )

        finally:
            self._updating_selector = False

        self._update_controls()

        return True

    def get_selected_scene_number(
        self,
    ) -> int:
        """
        Trả về số thứ tự cảnh đang chọn.

        Trả về 0 nếu chưa có cảnh.
        """

        if self._scene_count <= 0:
            return 0

        selected_data = (
            self.scene_selector.currentData()
        )

        if selected_data is None:
            return 0

        try:
            return int(selected_data)

        except (TypeError, ValueError):
            return 0

    def set_history_state(
        self,
        can_undo: bool,
        can_redo: bool,
        undo_description: str = "",
        redo_description: str = "",
    ) -> None:
        """
        Cập nhật trạng thái Undo/Redo.
        """

        self.undo_button.setEnabled(
            bool(can_undo)
        )

        self.redo_button.setEnabled(
            bool(can_redo)
        )

        if undo_description:
            self.undo_button.setToolTip(
                f"Hoàn tác: {undo_description}"
            )
        else:
            self.undo_button.setToolTip(
                "Không có thay đổi để hoàn tác"
            )

        if redo_description:
            self.redo_button.setToolTip(
                f"Làm lại: {redo_description}"
            )
        else:
            self.redo_button.setToolTip(
                "Không có thay đổi để làm lại"
            )

    def set_editing_enabled(
        self,
        enabled: bool,
    ) -> None:
        """
        Bật hoặc tắt các thao tác chỉnh sửa.

        Dùng khi pipeline đang chạy.
        """

        enabled = bool(enabled)

        self.add_button.setEnabled(
            enabled
        )

        has_scene = (
            enabled
            and self._scene_count > 0
        )

        self.scene_selector.setEnabled(
            has_scene
        )

        self.duplicate_button.setEnabled(
            has_scene
        )

        self.delete_button.setEnabled(
            has_scene
        )

        if has_scene:
            self._update_move_buttons()
        else:
            self.move_up_button.setEnabled(
                False
            )
            self.move_down_button.setEnabled(
                False
            )

    def _handle_scene_selection(
        self,
        index: int,
    ) -> None:
        if self._updating_selector:
            return

        if index < 0:
            self._update_controls()
            return

        scene_number = (
            self.get_selected_scene_number()
        )

        self._update_controls()

        if scene_number > 0:
            self.scene_selected.emit(
                scene_number
            )

    def _emit_duplicate_request(
        self,
    ) -> None:
        scene_number = (
            self.get_selected_scene_number()
        )

        if scene_number > 0:
            self.duplicate_scene_requested.emit(
                scene_number
            )

    def _emit_delete_request(
        self,
    ) -> None:
        scene_number = (
            self.get_selected_scene_number()
        )

        if scene_number > 0:
            self.delete_scene_requested.emit(
                scene_number
            )

    def _emit_move_up_request(
        self,
    ) -> None:
        scene_number = (
            self.get_selected_scene_number()
        )

        if scene_number > 1:
            self.move_scene_up_requested.emit(
                scene_number
            )

    def _emit_move_down_request(
        self,
    ) -> None:
        scene_number = (
            self.get_selected_scene_number()
        )

        if (
            scene_number > 0
            and scene_number < self._scene_count
        ):
            self.move_scene_down_requested.emit(
                scene_number
            )

    def _update_controls(self) -> None:
        has_scene = (
            self._scene_count > 0
        )

        self.scene_selector.setEnabled(
            has_scene
        )

        self.duplicate_button.setEnabled(
            has_scene
        )

        self.delete_button.setEnabled(
            has_scene
        )

        self._update_move_buttons()

    def _update_move_buttons(self) -> None:
        scene_number = (
            self.get_selected_scene_number()
        )

        self.move_up_button.setEnabled(
            scene_number > 1
        )

        self.move_down_button.setEnabled(
            (
                scene_number > 0
                and scene_number < self._scene_count
            )
        )