from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)


class SceneCard(QFrame):
    """
    Giao diện hiển thị và chỉnh sửa một cảnh.

    SceneCard không trực tiếp thao tác với ProjectModel.
    Khi người dùng sửa dữ liệu, card phát field_changed để
    ProjectPage cập nhật dữ liệu trung tâm.
    """

    image_requested = Signal(int, str)
    voice_requested = Signal(int, str)
    video_requested = Signal(int)

    field_changed = Signal(
        int,
        str,
        str,
    )

    data_changed = Signal(
        int,
        dict,
    )

    def __init__(
        self,
        scene_number: int,
        title: str,
        visual: str,
        narration: str,
        screen_text: str,
        image_prompt: str,
    ) -> None:
        super().__init__()

        self.scene_number = scene_number
        self.clean_title = self.normalize_title(
            title
        )

        self._updating_programmatically = False

        self.setObjectName(
            "card"
        )

        self.build_ui(
            visual=visual,
            narration=narration,
            screen_text=screen_text,
            image_prompt=image_prompt,
        )

        self.connect_editor_signals()

    def normalize_title(
        self,
        title: str,
    ) -> str:
        clean_title = title.strip()

        prefixes = [
            f"🎬 Cảnh {self.scene_number}:",
            f"Cảnh {self.scene_number}:",
            f"🎬 CẢNH {self.scene_number}:",
            f"CẢNH {self.scene_number}:",
        ]

        for prefix in prefixes:
            if clean_title.startswith(
                prefix
            ):
                clean_title = clean_title[
                    len(prefix):
                ].strip()

        return (
            clean_title
            or f"Cảnh {self.scene_number}"
        )

    def build_ui(
        self,
        visual: str,
        narration: str,
        screen_text: str,
        image_prompt: str,
    ) -> None:
        layout = QVBoxLayout(
            self
        )
        layout.setContentsMargins(
            22,
            22,
            22,
            22,
        )
        layout.setSpacing(12)

        header_layout = QHBoxLayout()

        self.title_label = QLabel(
            (
                f"🎬 Cảnh {self.scene_number}: "
                f"{self.clean_title}"
            )
        )
        self.title_label.setObjectName(
            "cardTitle"
        )

        self.image_button = QPushButton(
            "🎨 Tạo ảnh"
        )
        self.image_button.setObjectName(
            "secondaryButton"
        )
        self.image_button.clicked.connect(
            self.request_image
        )

        self.voice_button = QPushButton(
            "🔊 Tạo giọng đọc"
        )
        self.voice_button.setObjectName(
            "secondaryButton"
        )
        self.voice_button.clicked.connect(
            self.request_voice
        )

        self.video_button = QPushButton(
            "🎬 Tạo video cảnh"
        )
        self.video_button.setObjectName(
            "secondaryButton"
        )
        self.video_button.clicked.connect(
            self.request_video
        )

        header_layout.addWidget(
            self.title_label
        )
        header_layout.addStretch()
        header_layout.addWidget(
            self.image_button
        )
        header_layout.addWidget(
            self.voice_button
        )
        header_layout.addWidget(
            self.video_button
        )

        self.image_preview = QLabel(
            "Chưa có hình ảnh cho cảnh này"
        )
        self.image_preview.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.image_preview.setMinimumHeight(
            260
        )
        self.image_preview.setStyleSheet(
            """
            QLabel {
                background: #f3f4f8;
                border: 1px dashed #c6cad6;
                border-radius: 10px;
                color: #73798a;
                padding: 10px;
            }
            """
        )

        visual_label = QLabel(
            "Hình ảnh / footage"
        )
        visual_label.setObjectName(
            "cardTitle"
        )

        self.visual_editor = QTextEdit()
        self.visual_editor.setPlainText(
            visual
        )
        self.visual_editor.setFixedHeight(
            70
        )

        narration_label = QLabel(
            "Lời đọc"
        )
        narration_label.setObjectName(
            "cardTitle"
        )

        self.narration_editor = QTextEdit()
        self.narration_editor.setPlainText(
            narration
        )
        self.narration_editor.setFixedHeight(
            85
        )

        self.voice_status = QLabel(
            "Giọng đọc: Chưa có"
        )
        self.voice_status.setObjectName(
            "description"
        )

        self.video_status = QLabel(
            "Video cảnh: Chưa có"
        )
        self.video_status.setObjectName(
            "description"
        )

        screen_text_label = QLabel(
            "Chữ trên màn hình"
        )
        screen_text_label.setObjectName(
            "cardTitle"
        )

        self.screen_text_editor = QTextEdit()
        self.screen_text_editor.setPlainText(
            screen_text
        )
        self.screen_text_editor.setFixedHeight(
            60
        )

        prompt_label = QLabel(
            "Prompt tạo ảnh"
        )
        prompt_label.setObjectName(
            "cardTitle"
        )

        self.prompt_editor = QTextEdit()
        self.prompt_editor.setPlainText(
            image_prompt
        )
        self.prompt_editor.setFixedHeight(
            100
        )

        layout.addLayout(
            header_layout
        )
        layout.addWidget(
            self.image_preview
        )
        layout.addWidget(
            visual_label
        )
        layout.addWidget(
            self.visual_editor
        )
        layout.addWidget(
            narration_label
        )
        layout.addWidget(
            self.narration_editor
        )
        layout.addWidget(
            self.voice_status
        )
        layout.addWidget(
            self.video_status
        )
        layout.addWidget(
            screen_text_label
        )
        layout.addWidget(
            self.screen_text_editor
        )
        layout.addWidget(
            prompt_label
        )
        layout.addWidget(
            self.prompt_editor
        )

    def connect_editor_signals(
        self,
    ) -> None:
        """
        Kết nối các ô nhập liệu với tín hiệu thay đổi dữ liệu.
        """

        self.visual_editor.textChanged.connect(
            lambda: self.emit_field_changed(
                "visual",
                self.visual_editor,
            )
        )

        self.narration_editor.textChanged.connect(
            lambda: self.emit_field_changed(
                "narration",
                self.narration_editor,
            )
        )

        self.screen_text_editor.textChanged.connect(
            lambda: self.emit_field_changed(
                "screen_text",
                self.screen_text_editor,
            )
        )

        self.prompt_editor.textChanged.connect(
            lambda: self.emit_field_changed(
                "image_prompt",
                self.prompt_editor,
            )
        )

    def emit_field_changed(
        self,
        field_name: str,
        editor: QTextEdit,
    ) -> None:
        """
        Phát tín hiệu khi người dùng sửa một trường.

        Khi dữ liệu đang được cập nhật từ Undo/Redo hoặc từ model,
        tín hiệu sẽ bị bỏ qua để tránh vòng lặp cập nhật.
        """

        if self._updating_programmatically:
            return

        value = (
            editor
            .toPlainText()
        )

        self.field_changed.emit(
            self.scene_number,
            field_name,
            value,
        )

        self.data_changed.emit(
            self.scene_number,
            self.get_data(),
        )

    def set_scene_number(
        self,
        scene_number: int,
    ) -> None:
        """
        Cập nhật số thứ tự của cảnh.

        Dùng khi thêm, xóa hoặc sắp xếp lại cảnh.
        """

        if scene_number <= 0:
            raise ValueError(
                "Số thứ tự cảnh phải lớn hơn 0."
            )

        self.scene_number = scene_number

        self.title_label.setText(
            (
                f"🎬 Cảnh {self.scene_number}: "
                f"{self.clean_title}"
            )
        )

    def set_title(
        self,
        title: str,
    ) -> None:
        """
        Cập nhật tiêu đề cảnh từ dữ liệu bên ngoài.
        """

        self.clean_title = self.normalize_title(
            title
        )

        self.title_label.setText(
            (
                f"🎬 Cảnh {self.scene_number}: "
                f"{self.clean_title}"
            )
        )

    def set_data(
        self,
        scene_data: dict,
    ) -> None:
        """
        Cập nhật dữ liệu hiển thị mà không phát field_changed.

        Hàm này dùng cho:
        - Undo.
        - Redo.
        - Khôi phục snapshot.
        - Đồng bộ model vào giao diện.
        """

        if not isinstance(
            scene_data,
            dict,
        ):
            raise TypeError(
                "Dữ liệu cảnh phải là dict."
            )

        self._updating_programmatically = True

        try:
            title = str(
                scene_data.get(
                    "title",
                    self.clean_title,
                )
            )

            self.set_title(
                title
            )

            self.visual_editor.setPlainText(
                str(
                    scene_data.get(
                        "visual",
                        "",
                    )
                )
            )

            self.narration_editor.setPlainText(
                str(
                    scene_data.get(
                        "narration",
                        "",
                    )
                )
            )

            self.screen_text_editor.setPlainText(
                str(
                    scene_data.get(
                        "screen_text",
                        "",
                    )
                )
            )

            self.prompt_editor.setPlainText(
                str(
                    scene_data.get(
                        "image_prompt",
                        "",
                    )
                )
            )

        finally:
            self._updating_programmatically = False

    def request_image(
        self,
    ) -> None:
        prompt = (
            self.prompt_editor
            .toPlainText()
            .strip()
        )

        self.image_requested.emit(
            self.scene_number,
            prompt,
        )

    def request_voice(
        self,
    ) -> None:
        narration = (
            self.narration_editor
            .toPlainText()
            .strip()
        )

        self.voice_requested.emit(
            self.scene_number,
            narration,
        )

    def request_video(
        self,
    ) -> None:
        self.video_requested.emit(
            self.scene_number
        )

    def set_image_loading(
        self,
        loading: bool,
    ) -> None:
        self.image_button.setEnabled(
            not loading
        )

        if loading:
            self.image_button.setText(
                "⏳ Đang tạo ảnh..."
            )
            self.image_preview.setText(
                "AI đang tạo hình ảnh..."
            )
        else:
            self.image_button.setText(
                "🎨 Tạo lại ảnh"
            )

    def set_voice_loading(
        self,
        loading: bool,
    ) -> None:
        self.voice_button.setEnabled(
            not loading
        )

        if loading:
            self.voice_button.setText(
                "⏳ Đang tạo giọng..."
            )
            self.voice_status.setText(
                "Giọng đọc: Đang tạo..."
            )
        else:
            self.voice_button.setText(
                "🔊 Tạo lại giọng đọc"
            )

    def set_video_loading(
        self,
        loading: bool,
    ) -> None:
        self.video_button.setEnabled(
            not loading
        )

        if loading:
            self.video_button.setText(
                "⏳ Đang tạo video..."
            )
            self.video_status.setText(
                "Video cảnh: Đang tạo..."
            )
        else:
            self.video_button.setText(
                "🎬 Tạo lại video cảnh"
            )

    def display_image(
        self,
        image_path: Path,
    ) -> None:
        pixmap = QPixmap(
            str(image_path)
        )

        if pixmap.isNull():
            self.image_preview.setText(
                "Không thể hiển thị hình ảnh."
            )
            return

        scaled_pixmap = pixmap.scaled(
            720,
            400,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        self.image_preview.setPixmap(
            scaled_pixmap
        )
        self.image_preview.setText("")
        self.image_preview.setToolTip(
            str(image_path)
        )

    def display_voice(
        self,
        audio_path: Path,
    ) -> None:
        self.voice_status.setText(
            (
                "Giọng đọc: Đã tạo — "
                f"{audio_path.name}"
            )
        )
        self.voice_status.setToolTip(
            str(audio_path)
        )

    def display_video(
        self,
        video_path: Path,
    ) -> None:
        self.video_status.setText(
            (
                "Video cảnh: Đã tạo — "
                f"{video_path.name}"
            )
        )
        self.video_status.setToolTip(
            str(video_path)
        )

    def get_data(
        self,
    ) -> dict:
        """
        Trả về dữ liệu hiện tại của SceneCard.

        scene_number vẫn được giữ để tương thích với các thành phần
        đang sử dụng dữ liệu SceneCard hiện tại.
        """

        return {
            "scene_number": self.scene_number,
            "title": self.clean_title,
            "visual": (
                self.visual_editor
                .toPlainText()
                .strip()
            ),
            "narration": (
                self.narration_editor
                .toPlainText()
                .strip()
            ),
            "screen_text": (
                self.screen_text_editor
                .toPlainText()
                .strip()
            ),
            "image_prompt": (
                self.prompt_editor
                .toPlainText()
                .strip()
            ),
        }