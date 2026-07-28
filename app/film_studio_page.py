from __future__ import annotations

import csv
from pathlib import Path

from PySide6.QtCore import QThreadPool, Qt, QUrl, Slot
from PySide6.QtGui import QDesktopServices
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
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.models.film_project import FilmProject
from app.services.film_assembly_service import FilmAssemblyService
from app.services.film_planning_service import FilmPlanOptions, FilmPlanningService
from app.services.veo_service import VeoService
from app.workers.film_worker import FilmWorker


class FilmStudioPage(QWidget):
    """
    AI Film Studio 4.2.

    Quy trình mới:
    - Người dùng chỉ nhập ý tưởng và bấm "Tạo phim tự động".
    - Không yêu cầu chọn thư mục ngay từ đầu.
    - Dự án tự lưu vào projects/films/<tên-phim>.
    - Có thể tự tạo kế hoạch, render Veo và ghép phim liên tiếp.
    """

    def __init__(self) -> None:
        super().__init__()

        self.project: FilmProject | None = None
        self.project_dir: Path | None = None
        self.thread_pool = QThreadPool.globalInstance()
        self.stop_flag = False
        self._auto_pipeline = False

        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        title = QLabel("🎥 AI Film Studio 4.2", self)
        title.setObjectName("pageTitle")

        subtitle = QLabel(
            "Chỉ cần nhập ý tưởng. AI Studio sẽ tự viết kế hoạch phim, "
            "chia shot, tạo prompt Veo, render clip và ghép thành phim.",
            self,
        )
        subtitle.setObjectName("description")
        subtitle.setWordWrap(True)

        root.addWidget(title)
        root.addWidget(subtitle)

        tabs = QTabWidget(self)
        tabs.addTab(self._create_plan_tab(), "1. Tạo phim")
        tabs.addTab(self._create_queue_tab(), "2. Tiến trình Veo")
        tabs.addTab(self._create_export_tab(), "3. Xuất phim")
        root.addWidget(tabs, 1)

        self.progress = QProgressBar(self)
        self.progress.setRange(0, 100)

        self.status_label = QLabel("Sẵn sàng", self)

        bottom = QHBoxLayout()
        bottom.addWidget(self.status_label, 1)
        bottom.addWidget(self.progress)
        root.addLayout(bottom)

    def _create_plan_tab(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)

        form_card = QFrame(page)
        form_card.setObjectName("card")
        form = QFormLayout(form_card)

        self.title_input = QLineEdit("Bộ phim điện ảnh mới", form_card)

        self.idea_input = QTextEdit(form_card)
        self.idea_input.setPlaceholderText(
            "Ví dụ: Một nhà khảo cổ phát hiện thành phố cổ dưới sa mạc "
            "và phải ngăn lời nguyền thức tỉnh..."
        )
        self.idea_input.setMinimumHeight(150)

        self.genre_combo = QComboBox(form_card)
        self.genre_combo.addItems(
            [
                "Điện ảnh hiện thực",
                "Khoa học viễn tưởng",
                "Lịch sử sử thi",
                "Kinh dị",
                "Tình cảm",
                "Phiêu lưu",
                "Hoạt hình",
            ]
        )

        self.minutes_spin = QSpinBox(form_card)
        self.minutes_spin.setRange(1, 180)
        self.minutes_spin.setValue(15)
        self.minutes_spin.setSuffix(" phút")

        self.aspect_combo = QComboBox(form_card)
        self.aspect_combo.addItems(["16:9", "9:16"])

        self.resolution_combo = QComboBox(form_card)
        self.resolution_combo.addItems(["720p", "1080p", "4k"])

        self.model_combo = QComboBox(form_card)
        self.model_combo.addItems(
            [
                "veo-3.1-fast-generate-preview",
                "veo-3.1-generate-preview",
                "veo-3.0-fast-generate-001",
                "veo-3.0-generate-001",
            ]
        )

        self.auto_render_checkbox = QCheckBox(
            "Tự động render toàn bộ shot bằng Veo sau khi tạo kế hoạch",
            form_card,
        )
        self.auto_render_checkbox.setChecked(False)

        self.auto_assemble_checkbox = QCheckBox(
            "Tự động ghép phim sau khi render xong",
            form_card,
        )
        self.auto_assemble_checkbox.setChecked(False)

        form.addRow("Tên phim", self.title_input)
        form.addRow("Ý tưởng", self.idea_input)
        form.addRow("Thể loại", self.genre_combo)
        form.addRow("Thời lượng", self.minutes_spin)
        form.addRow("Khung hình", self.aspect_combo)
        form.addRow("Độ phân giải", self.resolution_combo)
        form.addRow("Mô hình Veo", self.model_combo)
        form.addRow("", self.auto_render_checkbox)
        form.addRow("", self.auto_assemble_checkbox)

        layout.addWidget(form_card)

        actions = QHBoxLayout()

        self.create_movie_button = QPushButton(
            "✨ TẠO PHIM TỰ ĐỘNG",
            page,
        )
        self.create_movie_button.setObjectName("primaryButton")
        self.create_movie_button.clicked.connect(self.create_movie_automatically)

        load_button = QPushButton("📂 Mở dự án phim cũ", page)
        load_button.clicked.connect(self.load_project)

        export_prompts = QPushButton("📄 Xuất prompt", page)
        export_prompts.clicked.connect(self.export_prompts)

        actions.addWidget(self.create_movie_button)
        actions.addWidget(load_button)
        actions.addWidget(export_prompts)
        actions.addStretch()

        layout.addLayout(actions)

        self.project_path_label = QLabel(
            "Dự án mới sẽ tự lưu trong: projects/films/",
            page,
        )
        self.project_path_label.setObjectName("description")
        self.project_path_label.setWordWrap(True)

        self.summary_label = QLabel("Chưa có kế hoạch phim.", page)
        self.summary_label.setWordWrap(True)

        layout.addWidget(self.project_path_label)
        layout.addWidget(self.summary_label)
        layout.addStretch()

        return page

    def _create_queue_tab(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)

        info = QLabel(
            "Mỗi shot được lưu riêng. Bạn có thể dừng và tiếp tục sau. "
            "Render Veo có thể mất nhiều thời gian và phát sinh chi phí API.",
            page,
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.shot_table = QTableWidget(0, 6, page)
        self.shot_table.setHorizontalHeaderLabels(
            [
                "Shot",
                "Hồi/Cảnh",
                "Thời lượng",
                "Trạng thái",
                "Prompt",
                "File video",
            ]
        )
        self.shot_table.setColumnWidth(0, 60)
        self.shot_table.setColumnWidth(1, 95)
        self.shot_table.setColumnWidth(2, 80)
        self.shot_table.setColumnWidth(3, 110)
        self.shot_table.setColumnWidth(4, 520)
        self.shot_table.setColumnWidth(5, 220)
        layout.addWidget(self.shot_table, 1)

        actions = QHBoxLayout()

        self.render_button = QPushButton(
            "▶ Render các shot còn thiếu",
            page,
        )
        self.render_button.setObjectName("primaryButton")
        self.render_button.clicked.connect(self.render_all)

        stop_button = QPushButton(
            "⏹ Dừng sau shot hiện tại",
            page,
        )
        stop_button.clicked.connect(self.stop_render)

        attach_button = QPushButton(
            "📎 Gắn clip thủ công",
            page,
        )
        attach_button.clicked.connect(self.attach_clip)

        open_folder_button = QPushButton(
            "📁 Mở thư mục clip",
            page,
        )
        open_folder_button.clicked.connect(self.open_clips_folder)

        actions.addWidget(self.render_button)
        actions.addWidget(stop_button)
        actions.addWidget(attach_button)
        actions.addWidget(open_folder_button)
        actions.addStretch()

        layout.addLayout(actions)
        return page

    def _create_export_tab(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)

        card = QFrame(page)
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)

        self.export_summary = QLabel(
            "Hãy tạo hoặc mở một dự án phim trước.",
            card,
        )
        self.export_summary.setWordWrap(True)
        card_layout.addWidget(self.export_summary)

        layout.addWidget(card)

        actions = QHBoxLayout()

        self.assemble_button = QPushButton(
            "🎬 Ghép và xuất phim MP4",
            page,
        )
        self.assemble_button.setObjectName("primaryButton")
        self.assemble_button.clicked.connect(self.assemble_movie)

        open_output_button = QPushButton(
            "▶ Mở phim đã xuất",
            page,
        )
        open_output_button.clicked.connect(self.open_output)

        open_project_button = QPushButton(
            "📁 Mở thư mục dự án",
            page,
        )
        open_project_button.clicked.connect(self.open_project_folder)

        actions.addWidget(self.assemble_button)
        actions.addWidget(open_output_button)
        actions.addWidget(open_project_button)
        actions.addStretch()

        layout.addLayout(actions)
        layout.addStretch()

        return page

    def _safe_title(self) -> str:
        raw_title = self.title_input.text().strip()
        safe_title = "".join(
            character
            for character in raw_title
            if character.isalnum() or character in " -_"
        ).strip()
        return safe_title or "film_project"

    def _default_project_dir(self) -> Path:
        return Path.cwd() / "projects" / "films" / self._safe_title()

    @Slot()
    def create_movie_automatically(self) -> None:
        idea = self.idea_input.toPlainText().strip()

        if not idea:
            QMessageBox.warning(
                self,
                "Thiếu ý tưởng",
                "Hãy nhập ý tưởng phim trước.",
            )
            return

        self.project_dir = self._default_project_dir()
        self.project_dir.mkdir(parents=True, exist_ok=True)

        self.project_path_label.setText(
            f"Thư mục dự án: {self.project_dir}"
        )

        options = FilmPlanOptions(
            title=self.title_input.text().strip() or "Bộ phim mới",
            idea=idea,
            genre=self.genre_combo.currentText(),
            target_minutes=self.minutes_spin.value(),
            aspect_ratio=self.aspect_combo.currentText(),
            resolution=self.resolution_combo.currentText(),
            veo_model=self.model_combo.currentText(),
        )

        self.create_movie_button.setEnabled(False)
        self.progress.setValue(5)
        self.status_label.setText("Đang tạo kịch bản và danh sách shot...")

        try:
            self.project = FilmPlanningService().create_plan(options)
            self.project.save(self.project_dir / "film_project.json")
            self.refresh_project_ui()

            if self.auto_render_checkbox.isChecked():
                self._auto_pipeline = self.auto_assemble_checkbox.isChecked()
                self.render_all(skip_confirmation=True)
            else:
                self.progress.setValue(100)
                self.status_label.setText("Đã tạo kế hoạch phim")
                QMessageBox.information(
                    self,
                    "Đã tạo kế hoạch",
                    f"Đã tạo {len(self.project.shots)} shot.\n\n"
                    f"Dự án được lưu tại:\n{self.project_dir}",
                )
        except Exception as error:
            self.progress.setValue(0)
            self.status_label.setText("Không thể tạo kế hoạch")
            QMessageBox.critical(
                self,
                "Không thể tạo kế hoạch",
                str(error),
            )
        finally:
            self.create_movie_button.setEnabled(True)

    @Slot()
    def load_project(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Mở dự án phim",
            str(Path.cwd() / "projects" / "films"),
            "AI Film Project (film_project.json);;JSON (*.json)",
        )

        if not file_name:
            return

        try:
            self.project = FilmProject.load(Path(file_name))
            self.project_dir = Path(file_name).parent
            self.title_input.setText(self.project.title)
            self.idea_input.setPlainText(self.project.idea)
            self.project_path_label.setText(
                f"Thư mục dự án: {self.project_dir}"
            )
            self.refresh_project_ui()
        except Exception as error:
            QMessageBox.critical(
                self,
                "Không thể mở dự án",
                str(error),
            )

    def refresh_project_ui(self) -> None:
        if not self.project:
            return

        completed = self.project.completed_shots
        total = len(self.project.shots)
        estimated = (
            sum(shot.duration_seconds for shot in self.project.shots) / 60
        )

        self.summary_label.setText(
            f"Phim: {self.project.title} · {total} shot · "
            f"thời lượng khoảng {estimated:.1f} phút · "
            f"{self.project.aspect_ratio} · {self.project.resolution}."
        )

        self.export_summary.setText(
            f"Đã có {completed}/{total} clip hoàn thành. "
            "Các shot hoàn thành sẽ được ghép theo đúng thứ tự."
        )

        self.shot_table.setRowCount(total)

        for row, shot in enumerate(self.project.shots):
            values = [
                str(shot.index),
                f"{shot.act}/{shot.scene}",
                f"{shot.duration_seconds}s",
                shot.status,
                shot.veo_prompt,
                shot.video_path,
            ]

            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))

                if column in (0, 1, 2, 3):
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignCenter
                    )

                self.shot_table.setItem(row, column, item)

    @Slot()
    def export_prompts(self) -> None:
        if not self.project:
            QMessageBox.warning(
                self,
                "Chưa có dự án",
                "Hãy tạo hoặc mở dự án phim trước.",
            )
            return

        default = str(
            (self.project_dir or Path.cwd()) / "veo_prompts.csv"
        )

        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Xuất prompt",
            default,
            "CSV (*.csv)",
        )

        if not file_name:
            return

        with Path(file_name).open(
            "w",
            encoding="utf-8-sig",
            newline="",
        ) as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "shot",
                    "act",
                    "scene",
                    "duration",
                    "narration",
                    "veo_prompt",
                    "status",
                    "video_path",
                ]
            )

            for shot in self.project.shots:
                writer.writerow(
                    [
                        shot.index,
                        shot.act,
                        shot.scene,
                        shot.duration_seconds,
                        shot.narration,
                        shot.veo_prompt,
                        shot.status,
                        shot.video_path,
                    ]
                )

        QMessageBox.information(
            self,
            "Đã xuất",
            file_name,
        )

    def render_all(self, skip_confirmation: bool = False) -> None:
        if not self.project or not self.project_dir:
            QMessageBox.warning(
                self,
                "Chưa có dự án",
                "Hãy tạo hoặc mở dự án phim trước.",
            )
            return

        remaining = (
            len(self.project.shots) - self.project.completed_shots
        )

        if remaining <= 0:
            self.status_label.setText("Tất cả shot đã có video")

            if self._auto_pipeline:
                self.assemble_movie(use_default_output=True)

            return

        if not skip_confirmation:
            answer = QMessageBox.question(
                self,
                "Xác nhận render Veo",
                f"Sẽ gửi tối đa {remaining} yêu cầu Veo. "
                "Quá trình có thể lâu và phát sinh chi phí API. Tiếp tục?",
            )

            if answer != QMessageBox.StandardButton.Yes:
                return

        self.stop_flag = False
        self.render_button.setEnabled(False)
        self.progress.setValue(0)
        self.status_label.setText("Đang render các shot bằng Veo...")

        def task(progress):
            return VeoService().render_project(
                self.project,
                self.project_dir,
                progress,
                lambda: self.stop_flag,
            )

        worker = FilmWorker(task)
        worker.signals.progress.connect(self._on_progress)
        worker.signals.completed.connect(self._on_render_completed)
        worker.signals.failed.connect(self._on_failed)
        self.thread_pool.start(worker)

    @Slot()
    def stop_render(self) -> None:
        self.stop_flag = True
        self.status_label.setText(
            "Đã yêu cầu dừng sau shot hiện tại"
        )

    @Slot()
    def attach_clip(self) -> None:
        if not self.project or not self.project_dir:
            QMessageBox.warning(
                self,
                "Chưa có dự án",
                "Hãy tạo hoặc mở dự án phim trước.",
            )
            return

        row = self.shot_table.currentRow()

        if row < 0:
            QMessageBox.warning(
                self,
                "Chưa chọn shot",
                "Hãy chọn một dòng trong bảng.",
            )
            return

        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn clip cho shot",
            "",
            "Video (*.mp4 *.mov *.m4v *.webm)",
        )

        if not file_name:
            return

        shot = self.project.shots[row]
        shot.video_path = file_name
        shot.status = "done"
        shot.error = ""

        self.project.save(
            self.project_dir / "film_project.json"
        )
        self.refresh_project_ui()

    @Slot()
    def open_clips_folder(self) -> None:
        if not self.project_dir:
            return

        clips = self.project_dir / "clips"
        clips.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(clips))
        )

    @Slot()
    def open_project_folder(self) -> None:
        if not self.project_dir:
            return

        self.project_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(self.project_dir))
        )

    def assemble_movie(
        self,
        checked: bool = False,
        use_default_output: bool = False,
    ) -> None:
        del checked

        if not self.project or not self.project_dir:
            QMessageBox.warning(
                self,
                "Chưa có dự án",
                "Hãy tạo hoặc mở dự án phim trước.",
            )
            return

        default = (
            self.project_dir
            / "output"
            / "final_film.mp4"
        )

        if use_default_output:
            file_name = str(default)
        else:
            file_name, _ = QFileDialog.getSaveFileName(
                self,
                "Xuất phim",
                str(default),
                "MP4 Video (*.mp4)",
            )

            if not file_name:
                return

        self.assemble_button.setEnabled(False)
        self.status_label.setText("Đang ghép phim...")

        def task(progress):
            return FilmAssemblyService().assemble(
                self.project,
                Path(file_name),
                progress,
            )

        worker = FilmWorker(task)
        worker.signals.progress.connect(self._on_progress)
        worker.signals.completed.connect(
            self._on_assembly_completed
        )
        worker.signals.failed.connect(self._on_failed)
        self.thread_pool.start(worker)

    @Slot()
    def open_output(self) -> None:
        if not self.project_dir:
            return

        output = (
            self.project_dir
            / "output"
            / "final_film.mp4"
        )

        if not output.is_file():
            QMessageBox.warning(
                self,
                "Chưa có phim",
                "Chưa tìm thấy output/final_film.mp4.",
            )
            return

        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(output))
        )

    @Slot(int, str)
    def _on_progress(self, value: int, text: str) -> None:
        self.progress.setValue(value)
        self.status_label.setText(text)

        if (
            self.project
            and self.project_dir
            and (
                self.project_dir
                / "film_project.json"
            ).is_file()
        ):
            try:
                self.project = FilmProject.load(
                    self.project_dir
                    / "film_project.json"
                )
                self.refresh_project_ui()
            except Exception:
                pass

    @Slot(object)
    def _on_render_completed(self, result: object) -> None:
        self.render_button.setEnabled(True)

        if isinstance(result, FilmProject):
            self.project = result

        self.progress.setValue(100)
        self.status_label.setText(
            "Đã hoàn thành hàng đợi Veo"
        )
        self.refresh_project_ui()

        if self._auto_pipeline:
            self._auto_pipeline = False
            self.assemble_movie(use_default_output=True)
            return

        QMessageBox.information(
            self,
            "Hoàn thành",
            "Hàng đợi Veo đã kết thúc. "
            "Kiểm tra các shot thất bại trong bảng.",
        )

    @Slot(object)
    def _on_assembly_completed(self, result: object) -> None:
        self.assemble_button.setEnabled(True)
        self.progress.setValue(100)
        self.status_label.setText(
            "Đã xuất phim hoàn chỉnh"
        )

        QMessageBox.information(
            self,
            "Xuất phim thành công",
            str(result),
        )

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self.render_button.setEnabled(True)
        self.assemble_button.setEnabled(True)
        self.create_movie_button.setEnabled(True)

        self.status_label.setText("Tác vụ thất bại")

        QMessageBox.critical(
            self,
            "Lỗi",
            message,
        )
