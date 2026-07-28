from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.services.config_service import ConfigService


class SettingsPage(QWidget):
    """
    Trang quản lý cài đặt chung của AI Studio.

    Các cài đặt được đọc và lưu thông qua ConfigService.
    """

    settings_saved = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.config_service = ConfigService()

        self.api_key_input: QLineEdit
        self.image_model_combo: QComboBox
        self.voice_model_combo: QComboBox
        self.voice_combo: QComboBox

        self.image_size_combo: QComboBox
        self.image_quality_combo: QComboBox

        self.video_width_input: QSpinBox
        self.video_height_input: QSpinBox
        self.video_fps_input: QSpinBox

        self.subtitle_enabled_checkbox: QCheckBox
        self.subtitle_font_input: QLineEdit
        self.subtitle_font_size_input: QSpinBox
        self.subtitle_margin_input: QSpinBox
        self.subtitle_words_input: QSpinBox

        self.project_directory_input: QLineEdit

        self.save_button: QPushButton
        self.reset_button: QPushButton

        self.build_ui()
        self.load_settings()

    def build_ui(self) -> None:
        """
        Tạo toàn bộ giao diện trang Cài đặt.
        """

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(
            24,
            24,
            24,
            24,
        )
        root_layout.setSpacing(16)

        title_label = QLabel(
            "⚙️ Cài đặt"
        )
        title_label.setObjectName(
            "settingsTitle"
        )
        title_label.setStyleSheet(
            """
            QLabel#settingsTitle {
                font-size: 26px;
                font-weight: 700;
            }
            """
        )

        description_label = QLabel(
            "Quản lý API, model AI, giọng đọc, "
            "video, phụ đề và thư mục dự án."
        )
        description_label.setWordWrap(True)
        description_label.setStyleSheet(
            """
            color: #777777;
            font-size: 14px;
            """
        )

        root_layout.addWidget(title_label)
        root_layout.addWidget(description_label)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(
            QFrame.Shape.NoFrame
        )

        scroll_content = QWidget()

        content_layout = QVBoxLayout(
            scroll_content
        )
        content_layout.setContentsMargins(
            0,
            8,
            12,
            8,
        )
        content_layout.setSpacing(18)

        openai_section = self.create_openai_section()
        image_section = self.create_image_section()
        video_section = self.create_video_section()
        subtitle_section = (
            self.create_subtitle_section()
        )
        project_section = (
            self.create_project_section()
        )

        content_layout.addWidget(openai_section)
        content_layout.addWidget(image_section)
        content_layout.addWidget(video_section)
        content_layout.addWidget(
            subtitle_section
        )
        content_layout.addWidget(
            project_section
        )
        content_layout.addStretch()

        scroll_area.setWidget(scroll_content)

        root_layout.addWidget(
            scroll_area,
            stretch=1,
        )

        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)

        self.reset_button = QPushButton(
            "Khôi phục mặc định"
        )
        self.reset_button.setMinimumHeight(42)
        self.reset_button.clicked.connect(
            self.reset_settings
        )

        self.save_button = QPushButton(
            "💾 Lưu cài đặt"
        )
        self.save_button.setMinimumHeight(42)
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(
            self.save_settings
        )

        button_layout.addStretch()
        button_layout.addWidget(
            self.reset_button
        )
        button_layout.addWidget(
            self.save_button
        )

        root_layout.addLayout(button_layout)

    def create_openai_section(
        self,
    ) -> QFrame:
        section = self.create_section_frame(
            "OpenAI"
        )

        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        form_layout.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText(
            "sk-..."
        )
        self.api_key_input.setEchoMode(
            QLineEdit.EchoMode.Password
        )

        self.api_key_input.setClearButtonEnabled(
            True
        )

        api_key_row = QWidget()
        api_key_layout = QHBoxLayout(
            api_key_row
        )
        api_key_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        api_key_layout.setSpacing(8)

        show_key_button = QPushButton(
            "Hiện"
        )
        show_key_button.setMinimumWidth(70)
        show_key_button.clicked.connect(
            lambda: self.toggle_api_key_visibility(
                show_key_button
            )
        )

        api_key_layout.addWidget(
            self.api_key_input,
            stretch=1,
        )
        api_key_layout.addWidget(
            show_key_button
        )

        self.image_model_combo = QComboBox()
        self.image_model_combo.setEditable(True)
        self.image_model_combo.addItems(
            [
                "gpt-image-1",
            ]
        )

        self.voice_model_combo = QComboBox()
        self.voice_model_combo.setEditable(True)
        self.voice_model_combo.addItems(
            [
                "gpt-4o-mini-tts",
                "tts-1",
                "tts-1-hd",
            ]
        )

        self.voice_combo = QComboBox()
        self.voice_combo.setEditable(True)
        self.voice_combo.addItems(
            [
                "alloy",
                "ash",
                "ballad",
                "coral",
                "echo",
                "fable",
                "nova",
                "onyx",
                "sage",
                "shimmer",
            ]
        )

        form_layout.addRow(
            "OpenAI API Key:",
            api_key_row,
        )
        form_layout.addRow(
            "Model tạo ảnh:",
            self.image_model_combo,
        )
        form_layout.addRow(
            "Model giọng đọc:",
            self.voice_model_combo,
        )
        form_layout.addRow(
            "Giọng đọc:",
            self.voice_combo,
        )

        section.layout().addLayout(
            form_layout
        )

        return section

    def create_image_section(
        self,
    ) -> QFrame:
        section = self.create_section_frame(
            "Hình ảnh"
        )

        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        form_layout.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )

        self.image_size_combo = QComboBox()
        self.image_size_combo.setEditable(True)
        self.image_size_combo.addItems(
            [
                "1024x1024",
                "1536x1024",
                "1024x1536",
            ]
        )

        self.image_quality_combo = QComboBox()
        self.image_quality_combo.setEditable(True)
        self.image_quality_combo.addItems(
            [
                "low",
                "medium",
                "high",
                "auto",
            ]
        )

        form_layout.addRow(
            "Kích thước ảnh:",
            self.image_size_combo,
        )
        form_layout.addRow(
            "Chất lượng ảnh:",
            self.image_quality_combo,
        )

        section.layout().addLayout(
            form_layout
        )

        return section

    def create_video_section(
        self,
    ) -> QFrame:
        section = self.create_section_frame(
            "Video"
        )

        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        form_layout.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )

        self.video_width_input = QSpinBox()
        self.video_width_input.setRange(
            320,
            7680,
        )
        self.video_width_input.setSingleStep(
            16
        )
        self.video_width_input.setSuffix(
            " px"
        )

        self.video_height_input = QSpinBox()
        self.video_height_input.setRange(
            240,
            4320,
        )
        self.video_height_input.setSingleStep(
            16
        )
        self.video_height_input.setSuffix(
            " px"
        )

        self.video_fps_input = QSpinBox()
        self.video_fps_input.setRange(
            1,
            120,
        )
        self.video_fps_input.setSuffix(
            " FPS"
        )

        form_layout.addRow(
            "Chiều rộng:",
            self.video_width_input,
        )
        form_layout.addRow(
            "Chiều cao:",
            self.video_height_input,
        )
        form_layout.addRow(
            "Tốc độ khung hình:",
            self.video_fps_input,
        )

        section.layout().addLayout(
            form_layout
        )

        return section

    def create_subtitle_section(
        self,
    ) -> QFrame:
        section = self.create_section_frame(
            "Phụ đề"
        )

        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        form_layout.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )

        self.subtitle_enabled_checkbox = (
            QCheckBox(
                "Tự động tạo và chèn phụ đề"
            )
        )

        self.subtitle_enabled_checkbox.toggled.connect(
            self.update_subtitle_inputs_state
        )

        self.subtitle_font_input = QLineEdit()
        self.subtitle_font_input.setPlaceholderText(
            "Arial"
        )

        self.subtitle_font_size_input = (
            QSpinBox()
        )
        self.subtitle_font_size_input.setRange(
            8,
            100,
        )
        self.subtitle_font_size_input.setSuffix(
            " pt"
        )

        self.subtitle_margin_input = QSpinBox()
        self.subtitle_margin_input.setRange(
            0,
            500,
        )
        self.subtitle_margin_input.setSuffix(
            " px"
        )

        self.subtitle_words_input = QSpinBox()
        self.subtitle_words_input.setRange(
            1,
            30,
        )
        self.subtitle_words_input.setSuffix(
            " từ"
        )

        form_layout.addRow(
            "Trạng thái:",
            self.subtitle_enabled_checkbox,
        )
        form_layout.addRow(
            "Tên font:",
            self.subtitle_font_input,
        )
        form_layout.addRow(
            "Cỡ chữ:",
            self.subtitle_font_size_input,
        )
        form_layout.addRow(
            "Khoảng cách đáy:",
            self.subtitle_margin_input,
        )
        form_layout.addRow(
            "Số từ mỗi đoạn:",
            self.subtitle_words_input,
        )

        section.layout().addLayout(
            form_layout
        )

        return section

    def create_project_section(
        self,
    ) -> QFrame:
        section = self.create_section_frame(
            "Dự án"
        )

        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        form_layout.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )

        self.project_directory_input = (
            QLineEdit()
        )
        self.project_directory_input.setPlaceholderText(
            "projects"
        )

        directory_row = QWidget()
        directory_layout = QHBoxLayout(
            directory_row
        )
        directory_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        directory_layout.setSpacing(8)

        browse_button = QPushButton(
            "Chọn thư mục"
        )
        browse_button.clicked.connect(
            self.choose_project_directory
        )

        directory_layout.addWidget(
            self.project_directory_input,
            stretch=1,
        )
        directory_layout.addWidget(
            browse_button
        )

        form_layout.addRow(
            "Thư mục dự án:",
            directory_row,
        )

        section.layout().addLayout(
            form_layout
        )

        return section

    def create_section_frame(
        self,
        title: str,
    ) -> QFrame:
        """
        Tạo một khung cài đặt có tiêu đề.
        """

        frame = QFrame()
        frame.setObjectName(
            "settingsSection"
        )

        frame.setStyleSheet(
            """
            QFrame#settingsSection {
                border: 1px solid #D9D9D9;
                border-radius: 10px;
                background-color: transparent;
            }
            """
        )

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(
            18,
            16,
            18,
            18,
        )
        layout.setSpacing(14)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            """
            font-size: 17px;
            font-weight: 700;
            border: none;
            """
        )

        layout.addWidget(title_label)

        return frame

    def load_settings(self) -> None:
        """
        Đọc dữ liệu từ config.json và hiển thị lên giao diện.
        """

        self.config_service.load()

        self.api_key_input.setText(
            str(
                self.config_service.get(
                    "openai.api_key",
                    "",
                )
            )
        )

        self.set_combo_value(
            self.image_model_combo,
            str(
                self.config_service.get(
                    "openai.image_model",
                    "gpt-image-1",
                )
            ),
        )

        self.set_combo_value(
            self.voice_model_combo,
            str(
                self.config_service.get(
                    "openai.voice_model",
                    "gpt-4o-mini-tts",
                )
            ),
        )

        self.set_combo_value(
            self.voice_combo,
            str(
                self.config_service.get(
                    "openai.voice",
                    "alloy",
                )
            ),
        )

        self.set_combo_value(
            self.image_size_combo,
            str(
                self.config_service.get(
                    "image.size",
                    "1536x1024",
                )
            ),
        )

        self.set_combo_value(
            self.image_quality_combo,
            str(
                self.config_service.get(
                    "image.quality",
                    "medium",
                )
            ),
        )

        self.video_width_input.setValue(
            int(
                self.config_service.get(
                    "video.width",
                    1280,
                )
            )
        )

        self.video_height_input.setValue(
            int(
                self.config_service.get(
                    "video.height",
                    720,
                )
            )
        )

        self.video_fps_input.setValue(
            int(
                self.config_service.get(
                    "video.fps",
                    30,
                )
            )
        )

        subtitle_enabled = bool(
            self.config_service.get(
                "subtitle.enabled",
                True,
            )
        )

        self.subtitle_enabled_checkbox.setChecked(
            subtitle_enabled
        )

        self.subtitle_font_input.setText(
            str(
                self.config_service.get(
                    "subtitle.font_name",
                    "Arial",
                )
            )
        )

        self.subtitle_font_size_input.setValue(
            int(
                self.config_service.get(
                    "subtitle.font_size",
                    22,
                )
            )
        )

        self.subtitle_margin_input.setValue(
            int(
                self.config_service.get(
                    "subtitle.margin_bottom",
                    42,
                )
            )
        )

        self.subtitle_words_input.setValue(
            int(
                self.config_service.get(
                    "subtitle.max_words_per_caption",
                    8,
                )
            )
        )

        self.project_directory_input.setText(
            str(
                self.config_service.get(
                    "project.directory",
                    "projects",
                )
            )
        )

        self.update_subtitle_inputs_state(
            subtitle_enabled
        )

    def save_settings(self) -> None:
        """
        Kiểm tra và lưu các cài đặt vào config.json.
        """

        try:
            values = self.collect_settings()

            self.validate_settings(
                values
            )

            self.config_service.update_many(
                values
            )

            self.config_service.ensure_project_directory()

            self.settings_saved.emit()

            QMessageBox.information(
                self,
                "Đã lưu",
                (
                    "Cài đặt đã được lưu thành công.\n\n"
                    "Một số thay đổi sẽ được áp dụng "
                    "khi tạo nội dung hoặc video mới."
                ),
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "Không thể lưu cài đặt",
                str(error),
            )

    def collect_settings(
        self,
    ) -> dict:
        """
        Thu thập dữ liệu hiện tại trên giao diện.
        """

        return {
            "openai.api_key": (
                self.api_key_input.text().strip()
            ),
            "openai.image_model": (
                self.image_model_combo
                .currentText()
                .strip()
            ),
            "openai.voice_model": (
                self.voice_model_combo
                .currentText()
                .strip()
            ),
            "openai.voice": (
                self.voice_combo
                .currentText()
                .strip()
            ),
            "image.size": (
                self.image_size_combo
                .currentText()
                .strip()
            ),
            "image.quality": (
                self.image_quality_combo
                .currentText()
                .strip()
            ),
            "video.width": (
                self.video_width_input.value()
            ),
            "video.height": (
                self.video_height_input.value()
            ),
            "video.fps": (
                self.video_fps_input.value()
            ),
            "subtitle.enabled": (
                self.subtitle_enabled_checkbox
                .isChecked()
            ),
            "subtitle.font_name": (
                self.subtitle_font_input
                .text()
                .strip()
            ),
            "subtitle.font_size": (
                self.subtitle_font_size_input
                .value()
            ),
            "subtitle.margin_bottom": (
                self.subtitle_margin_input
                .value()
            ),
            (
                "subtitle."
                "max_words_per_caption"
            ): (
                self.subtitle_words_input
                .value()
            ),
            "project.directory": (
                self.project_directory_input
                .text()
                .strip()
            ),
        }

    def validate_settings(
        self,
        values: dict,
    ) -> None:
        """
        Kiểm tra dữ liệu trước khi lưu.
        """

        if not values[
            "openai.image_model"
        ]:
            raise ValueError(
                "Model tạo ảnh không được để trống."
            )

        if not values[
            "openai.voice_model"
        ]:
            raise ValueError(
                "Model giọng đọc không được để trống."
            )

        if not values["openai.voice"]:
            raise ValueError(
                "Giọng đọc không được để trống."
            )

        image_size = str(
            values["image.size"]
        )

        if "x" not in image_size.lower():
            raise ValueError(
                "Kích thước ảnh phải có dạng "
                "1536x1024."
            )

        if not values[
            "image.quality"
        ]:
            raise ValueError(
                "Chất lượng ảnh không được để trống."
            )

        if values["video.width"] <= 0:
            raise ValueError(
                "Chiều rộng video không hợp lệ."
            )

        if values["video.height"] <= 0:
            raise ValueError(
                "Chiều cao video không hợp lệ."
            )

        if values["video.fps"] <= 0:
            raise ValueError(
                "FPS video không hợp lệ."
            )

        if (
            values["subtitle.enabled"]
            and not values["subtitle.font_name"]
        ):
            raise ValueError(
                "Tên font phụ đề không được để trống."
            )

        if not values[
            "project.directory"
        ]:
            raise ValueError(
                "Thư mục dự án không được để trống."
            )

    def reset_settings(self) -> None:
        """
        Khôi phục cấu hình mặc định sau khi người dùng xác nhận.
        """

        answer = QMessageBox.question(
            self,
            "Khôi phục cài đặt",
            (
                "Bạn có chắc muốn khôi phục "
                "toàn bộ cài đặt mặc định không?"
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if (
            answer
            != QMessageBox.StandardButton.Yes
        ):
            return

        try:
            self.config_service.reset()
            self.load_settings()

            self.settings_saved.emit()

            QMessageBox.information(
                self,
                "Đã khôi phục",
                "Cài đặt mặc định đã được khôi phục.",
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "Không thể khôi phục",
                str(error),
            )

    def choose_project_directory(
        self,
    ) -> None:
        """
        Mở cửa sổ chọn thư mục dự án.
        """

        current_text = (
            self.project_directory_input
            .text()
            .strip()
        )

        if current_text:
            initial_directory = (
                Path(current_text)
                .expanduser()
            )

            if not initial_directory.is_absolute():
                initial_directory = (
                    Path.cwd()
                    / initial_directory
                )
        else:
            initial_directory = Path.cwd()

        selected_directory = (
            QFileDialog.getExistingDirectory(
                self,
                "Chọn thư mục lưu dự án",
                str(initial_directory),
            )
        )

        if not selected_directory:
            return

        self.project_directory_input.setText(
            selected_directory
        )

    def toggle_api_key_visibility(
        self,
        button: QPushButton,
    ) -> None:
        """
        Hiện hoặc ẩn API Key.
        """

        if (
            self.api_key_input.echoMode()
            == QLineEdit.EchoMode.Password
        ):
            self.api_key_input.setEchoMode(
                QLineEdit.EchoMode.Normal
            )
            button.setText("Ẩn")
        else:
            self.api_key_input.setEchoMode(
                QLineEdit.EchoMode.Password
            )
            button.setText("Hiện")

    def update_subtitle_inputs_state(
        self,
        enabled: bool,
    ) -> None:
        """
        Bật hoặc khóa các ô phụ đề.
        """

        subtitle_widgets = [
            self.subtitle_font_input,
            self.subtitle_font_size_input,
            self.subtitle_margin_input,
            self.subtitle_words_input,
        ]

        for widget in subtitle_widgets:
            widget.setEnabled(enabled)

    def set_combo_value(
        self,
        combo_box: QComboBox,
        value: str,
    ) -> None:
        """
        Chọn giá trị trong ComboBox.

        Nếu giá trị chưa có trong danh sách thì tự thêm.
        """

        index = combo_box.findText(
            value,
            Qt.MatchFlag.MatchFixedString,
        )

        if index < 0:
            combo_box.addItem(value)
            index = combo_box.count() - 1

        combo_box.setCurrentIndex(index)
        import sys

from PySide6.QtWidgets import QApplication

from app.settings_page import SettingsPage


def main() -> None:
    app = QApplication(sys.argv)

    page = SettingsPage()
    page.setWindowTitle(
        "Kiểm tra trang Cài đặt"
    )
    page.resize(
        820,
        760,
    )
    page.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()