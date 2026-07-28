from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.services.ai_director_service import AIDirectorService, DirectorOptions


class AIDirectorPage(QWidget):
    back_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.service = AIDirectorService()
        self.current_plan = None
        self.current_project_dir: Path | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 26, 30, 26)
        root.setSpacing(16)

        header = QHBoxLayout()
        title_box = QVBoxLayout()

        title = QLabel("🎬 AI Director", self)
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "Nhập ý tưởng để tự tạo logline, nhân vật, cảnh, shot và prompt Veo.",
            self,
        )
        subtitle.setObjectName("description")

        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch()

        back_button = QPushButton("← Tổng quan", self)
        back_button.setObjectName("secondaryButton")
        back_button.clicked.connect(self.back_requested.emit)
        header.addWidget(back_button)
        root.addLayout(header)

        tabs = QTabWidget(self)
        tabs.addTab(self._create_input_tab(), "1. Ý tưởng")
        tabs.addTab(self._create_plan_tab(), "2. Kế hoạch phim")
        tabs.addTab(self._create_prompt_tab(), "3. Prompt Veo")
        root.addWidget(tabs, 1)
        self.tabs = tabs

    def _create_input_tab(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)

        card = QFrame(page)
        card.setObjectName("card")
        form = QFormLayout(card)

        self.title_input = QLineEdit("Bộ phim mới", card)
        self.idea_input = QTextEdit(card)
        self.idea_input.setMinimumHeight(190)
        self.idea_input.setPlaceholderText(
            "Ví dụ: Một bác sĩ trẻ phát hiện ngôi làng miền núi đang bị "
            "một hiện tượng kỳ lạ khiến ký ức của mọi người biến mất..."
        )

        self.genre_combo = QComboBox(card)
        self.genre_combo.addItems(
            [
                "Điện ảnh hiện thực",
                "Khoa học viễn tưởng",
                "Phiêu lưu",
                "Tâm lý",
                "Kinh dị",
                "Lịch sử",
                "Tình cảm",
                "Hoạt hình",
            ]
        )

        self.tone_combo = QComboBox(card)
        self.tone_combo.addItems(
            [
                "Cảm xúc và điện ảnh",
                "Kịch tính",
                "Bí ẩn",
                "Ấm áp",
                "Hùng tráng",
                "Tối và căng thẳng",
            ]
        )

        self.minutes_spin = QSpinBox(card)
        self.minutes_spin.setRange(3, 60)
        self.minutes_spin.setValue(12)
        self.minutes_spin.setSuffix(" phút")

        form.addRow("Tên phim", self.title_input)
        form.addRow("Ý tưởng", self.idea_input)
        form.addRow("Thể loại", self.genre_combo)
        form.addRow("Sắc thái", self.tone_combo)
        form.addRow("Thời lượng", self.minutes_spin)

        layout.addWidget(card)

        actions = QHBoxLayout()
        create_button = QPushButton("✨ Tạo kế hoạch phim", page)
        create_button.setObjectName("primaryButton")
        create_button.clicked.connect(self.create_plan)

        self.save_button = QPushButton("💾 Lưu thành dự án", page)
        self.save_button.setObjectName("secondaryButton")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self.save_project)

        actions.addWidget(create_button)
        actions.addWidget(self.save_button)
        actions.addStretch()
        layout.addLayout(actions)

        self.status_label = QLabel("Chưa tạo kế hoạch.", page)
        self.status_label.setObjectName("description")
        layout.addWidget(self.status_label)
        layout.addStretch()
        return page

    def _create_plan_tab(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)

        self.summary_text = QTextEdit(page)
        self.summary_text.setReadOnly(True)
        self.summary_text.setPlaceholderText("Kế hoạch phim sẽ xuất hiện tại đây.")
        layout.addWidget(self.summary_text, 1)

        self.scene_table = QTableWidget(0, 6, page)
        self.scene_table.setHorizontalHeaderLabels(
            ["Cảnh", "Hồi", "Tên cảnh", "Bối cảnh", "Thời gian", "Mục đích"]
        )
        self.scene_table.setColumnWidth(0, 60)
        self.scene_table.setColumnWidth(1, 55)
        self.scene_table.setColumnWidth(2, 210)
        self.scene_table.setColumnWidth(3, 280)
        self.scene_table.setColumnWidth(4, 110)
        self.scene_table.setColumnWidth(5, 430)
        layout.addWidget(self.scene_table, 2)
        return page

    def _create_prompt_tab(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)

        self.prompt_table = QTableWidget(0, 4, page)
        self.prompt_table.setHorizontalHeaderLabels(
            ["Shot", "Cảnh", "Camera", "Prompt Veo"]
        )
        self.prompt_table.setColumnWidth(0, 70)
        self.prompt_table.setColumnWidth(1, 75)
        self.prompt_table.setColumnWidth(2, 260)
        self.prompt_table.setColumnWidth(3, 700)
        layout.addWidget(self.prompt_table, 1)

        export_button = QPushButton("📄 Xuất prompt TXT", page)
        export_button.setObjectName("secondaryButton")
        export_button.clicked.connect(self.export_prompts)
        layout.addWidget(export_button)
        return page

    def create_plan(self) -> None:
        try:
            options = DirectorOptions(
                title=self.title_input.text(),
                idea=self.idea_input.toPlainText(),
                genre=self.genre_combo.currentText(),
                tone=self.tone_combo.currentText(),
                target_minutes=self.minutes_spin.value(),
            )
            self.current_plan = self.service.create_plan(options)
        except ValueError as error:
            QMessageBox.warning(self, "Thiếu nội dung", str(error))
            return

        self._render_plan()
        self.save_button.setEnabled(True)
        self.tabs.setCurrentIndex(1)
        self.status_label.setText(
            f"Đã tạo {len(self.current_plan.scenes)} cảnh và "
            f"{sum(len(scene.shots) for scene in self.current_plan.scenes)} shot."
        )

    def _render_plan(self) -> None:
        if self.current_plan is None:
            return

        characters = "\n".join(
            f"• {character['name']} — {character['role']}: "
            f"{character['description']}"
            for character in self.current_plan.characters
        )
        self.summary_text.setPlainText(
            f"TÊN PHIM\n{self.current_plan.title}\n\n"
            f"LOGLINE\n{self.current_plan.logline}\n\n"
            f"THỂ LOẠI\n{self.current_plan.genre}\n\n"
            f"SẮC THÁI\n{self.current_plan.tone}\n\n"
            f"NHÂN VẬT\n{characters}"
        )

        self.scene_table.setRowCount(0)
        self.prompt_table.setRowCount(0)

        for scene in self.current_plan.scenes:
            row = self.scene_table.rowCount()
            self.scene_table.insertRow(row)
            values = [
                str(scene.number),
                str(scene.act),
                scene.title,
                scene.location,
                scene.time_of_day,
                scene.purpose,
            ]
            for column, value in enumerate(values):
                self.scene_table.setItem(row, column, QTableWidgetItem(value))

            for shot in scene.shots:
                prompt_row = self.prompt_table.rowCount()
                self.prompt_table.insertRow(prompt_row)
                prompt_values = [
                    str(shot.number),
                    str(scene.number),
                    shot.camera,
                    shot.veo_prompt,
                ]
                for column, value in enumerate(prompt_values):
                    self.prompt_table.setItem(
                        prompt_row,
                        column,
                        QTableWidgetItem(value),
                    )

    def save_project(self) -> None:
        if self.current_plan is None:
            return

        project_root = Path(__file__).resolve().parent.parent / "projects"
        self.current_project_dir = self.service.save_plan(
            project_root,
            self.current_plan,
        )
        QMessageBox.information(
            self,
            "Đã lưu dự án",
            f"Dự án đã lưu tại:\n{self.current_project_dir}",
        )
        self.status_label.setText(f"Đã lưu: {self.current_project_dir.name}")

    def export_prompts(self) -> None:
        if self.current_plan is None:
            QMessageBox.warning(
                self,
                "Chưa có dữ liệu",
                "Hãy tạo kế hoạch phim trước.",
            )
            return

        default_name = (
            AIDirectorService.safe_project_name(self.current_plan.title)
            + "_veo_prompts.txt"
        )
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Xuất prompt Veo",
            default_name,
            "Text files (*.txt)",
        )
        if not path:
            return

        lines: list[str] = []
        for scene in self.current_plan.scenes:
            lines.append(f"=== {scene.title} ===")
            for shot in scene.shots:
                lines.extend(
                    [
                        f"{shot.title}",
                        shot.veo_prompt,
                        "",
                    ]
                )

        Path(path).write_text("\n".join(lines), encoding="utf-8")
        QMessageBox.information(self, "Đã xuất", f"Đã lưu prompt tại:\n{path}")
