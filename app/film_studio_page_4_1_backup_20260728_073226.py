from __future__ import annotations

import csv
import os
from pathlib import Path

from PySide6.QtCore import QThreadPool, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
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
    """Tạo phim dài: ý tưởng → kịch bản/shot → Veo → ghép và xuất."""

    def __init__(self) -> None:
        super().__init__()
        self.project: FilmProject | None = None
        self.project_dir: Path | None = None
        self.thread_pool = QThreadPool.globalInstance()
        self.stop_flag = False
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        title = QLabel("🎥 AI Film Studio")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "Tự động phát triển ý tưởng thành phim từ 15 phút, tạo shot 8 giây cho Veo, "
            "theo dõi quá trình render và ghép thành một video hoàn chỉnh."
        )
        subtitle.setObjectName("description")
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)

        tabs = QTabWidget()
        tabs.addTab(self._create_plan_tab(), "1. Ý tưởng & kịch bản")
        tabs.addTab(self._create_queue_tab(), "2. Veo render queue")
        tabs.addTab(self._create_export_tab(), "3. Ghép & xuất phim")
        root.addWidget(tabs, 1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.status_label = QLabel("Sẵn sàng")
        bottom = QHBoxLayout()
        bottom.addWidget(self.status_label, 1)
        bottom.addWidget(self.progress)
        root.addLayout(bottom)

    def _create_plan_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        form_card = QFrame()
        form_card.setObjectName("card")
        form = QFormLayout(form_card)

        self.title_input = QLineEdit("Bộ phim điện ảnh mới")
        self.idea_input = QTextEdit()
        self.idea_input.setPlaceholderText(
            "Ví dụ: Một nhà khảo cổ phát hiện thành phố cổ dưới sa mạc và phải ngăn một lời nguyền thức tỉnh..."
        )
        self.idea_input.setMinimumHeight(120)
        self.genre_combo = QComboBox()
        self.genre_combo.addItems([
            "Điện ảnh hiện thực", "Khoa học viễn tưởng", "Lịch sử sử thi",
            "Kinh dị", "Tình cảm", "Phiêu lưu", "Hoạt hình",
        ])
        self.minutes_spin = QSpinBox()
        self.minutes_spin.setRange(15, 180)
        self.minutes_spin.setValue(15)
        self.minutes_spin.setSuffix(" phút")
        self.aspect_combo = QComboBox()
        self.aspect_combo.addItems(["16:9", "9:16"])
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["720p", "1080p", "4k"])
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "veo-3.1-fast-generate-preview",
            "veo-3.1-generate-preview",
            "veo-3.0-fast-generate-001",
            "veo-3.0-generate-001",
        ])

        form.addRow("Tên phim", self.title_input)
        form.addRow("Ý tưởng", self.idea_input)
        form.addRow("Thể loại", self.genre_combo)
        form.addRow("Thời lượng tối thiểu", self.minutes_spin)
        form.addRow("Khung hình", self.aspect_combo)
        form.addRow("Độ phân giải", self.resolution_combo)
        form.addRow("Mô hình Veo", self.model_combo)
        layout.addWidget(form_card)

        actions = QHBoxLayout()
        create_button = QPushButton("✨ Tạo kịch bản và prompt")
        create_button.setObjectName("primaryButton")
        create_button.clicked.connect(self.create_plan)
        load_button = QPushButton("📂 Mở dự án phim")
        load_button.clicked.connect(self.load_project)
        export_prompts = QPushButton("📄 Xuất danh sách prompt")
        export_prompts.clicked.connect(self.export_prompts)
        actions.addWidget(create_button)
        actions.addWidget(load_button)
        actions.addWidget(export_prompts)
        actions.addStretch()
        layout.addLayout(actions)

        self.summary_label = QLabel("Chưa có kế hoạch phim.")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)
        layout.addStretch()
        return page

    def _create_queue_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        info = QLabel(
            "Veo tạo từng clip ngắn. Phim 15 phút cần khoảng 113 shot 8 giây. "
            "Quá trình có thể mất nhiều giờ và phát sinh chi phí API. Dự án được lưu sau từng shot để có thể tiếp tục."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.shot_table = QTableWidget(0, 6)
        self.shot_table.setHorizontalHeaderLabels([
            "Shot", "Hồi/Cảnh", "Thời lượng", "Trạng thái", "Prompt", "File video"
        ])
        self.shot_table.setColumnWidth(0, 60)
        self.shot_table.setColumnWidth(1, 95)
        self.shot_table.setColumnWidth(2, 80)
        self.shot_table.setColumnWidth(3, 100)
        self.shot_table.setColumnWidth(4, 520)
        self.shot_table.setColumnWidth(5, 220)
        layout.addWidget(self.shot_table, 1)

        actions = QHBoxLayout()
        render_button = QPushButton("▶ Render toàn bộ với Veo")
        render_button.setObjectName("primaryButton")
        render_button.clicked.connect(self.render_all)
        stop_button = QPushButton("⏹ Dừng sau shot hiện tại")
        stop_button.clicked.connect(self.stop_render)
        attach_button = QPushButton("📎 Gắn clip thủ công cho shot")
        attach_button.clicked.connect(self.attach_clip)
        open_folder_button = QPushButton("📁 Mở thư mục clip")
        open_folder_button.clicked.connect(self.open_clips_folder)
        actions.addWidget(render_button)
        actions.addWidget(stop_button)
        actions.addWidget(attach_button)
        actions.addWidget(open_folder_button)
        actions.addStretch()
        layout.addLayout(actions)
        return page

    def _create_export_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        self.export_summary = QLabel("Hãy tạo hoặc mở một dự án phim trước.")
        self.export_summary.setWordWrap(True)
        card_layout.addWidget(self.export_summary)
        layout.addWidget(card)

        actions = QHBoxLayout()
        assemble_button = QPushButton("🎬 Ghép và xuất phim MP4")
        assemble_button.setObjectName("primaryButton")
        assemble_button.clicked.connect(self.assemble_movie)
        open_output_button = QPushButton("▶ Mở phim đã xuất")
        open_output_button.clicked.connect(self.open_output)
        actions.addWidget(assemble_button)
        actions.addWidget(open_output_button)
        actions.addStretch()
        layout.addLayout(actions)
        layout.addStretch()
        return page

    def create_plan(self) -> None:
        idea = self.idea_input.toPlainText().strip()
        if not idea:
            QMessageBox.warning(self, "Thiếu ý tưởng", "Hãy nhập ý tưởng phim trước.")
            return
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu dự án phim")
        if not folder:
            return
        safe_title = "".join(ch for ch in self.title_input.text().strip() if ch.isalnum() or ch in " -_").strip() or "film_project"
        self.project_dir = Path(folder) / safe_title
        self.project_dir.mkdir(parents=True, exist_ok=True)
        options = FilmPlanOptions(
            title=self.title_input.text(),
            idea=idea,
            genre=self.genre_combo.currentText(),
            target_minutes=self.minutes_spin.value(),
            aspect_ratio=self.aspect_combo.currentText(),
            resolution=self.resolution_combo.currentText(),
            veo_model=self.model_combo.currentText(),
        )
        try:
            self.project = FilmPlanningService().create_plan(options)
            self.project.save(self.project_dir / "film_project.json")
            self.refresh_project_ui()
            QMessageBox.information(
                self, "Đã tạo kế hoạch",
                f"Đã tạo {len(self.project.shots)} shot cho phim {self.project.target_minutes} phút."
            )
        except Exception as exc:
            QMessageBox.critical(self, "Không thể tạo kế hoạch", str(exc))

    def load_project(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(self, "Mở dự án phim", "", "AI Film Project (film_project.json);;JSON (*.json)")
        if not file_name:
            return
        try:
            self.project = FilmProject.load(Path(file_name))
            self.project_dir = Path(file_name).parent
            self.title_input.setText(self.project.title)
            self.idea_input.setPlainText(self.project.idea)
            self.refresh_project_ui()
        except Exception as exc:
            QMessageBox.critical(self, "Không thể mở dự án", str(exc))

    def refresh_project_ui(self) -> None:
        if not self.project:
            return
        completed = self.project.completed_shots
        total = len(self.project.shots)
        estimated = sum(shot.duration_seconds for shot in self.project.shots) / 60
        self.summary_label.setText(
            f"Phim: {self.project.title} · {total} shot · thời lượng thiết kế khoảng {estimated:.1f} phút · "
            f"khung hình {self.project.aspect_ratio} · {self.project.resolution}."
        )
        self.export_summary.setText(
            f"Đã có {completed}/{total} clip. Chỉ các shot có trạng thái hoàn thành mới được ghép. "
            "Bạn có thể render bằng Veo hoặc gắn clip thủ công."
        )
        self.shot_table.setRowCount(total)
        for row, shot in enumerate(self.project.shots):
            values = [
                str(shot.index), f"{shot.act}/{shot.scene}", f"{shot.duration_seconds}s",
                shot.status, shot.veo_prompt, shot.video_path,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in (0, 1, 2, 3):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.shot_table.setItem(row, column, item)

    def export_prompts(self) -> None:
        if not self.project:
            QMessageBox.warning(self, "Chưa có dự án", "Hãy tạo hoặc mở dự án phim trước.")
            return
        default = str((self.project_dir or Path.cwd()) / "veo_prompts.csv")
        file_name, _ = QFileDialog.getSaveFileName(self, "Xuất prompt", default, "CSV (*.csv)")
        if not file_name:
            return
        with Path(file_name).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["shot", "act", "scene", "duration", "narration", "veo_prompt", "status", "video_path"])
            for shot in self.project.shots:
                writer.writerow([shot.index, shot.act, shot.scene, shot.duration_seconds, shot.narration, shot.veo_prompt, shot.status, shot.video_path])
        QMessageBox.information(self, "Đã xuất", file_name)

    def render_all(self) -> None:
        if not self.project or not self.project_dir:
            QMessageBox.warning(self, "Chưa có dự án", "Hãy tạo hoặc mở dự án phim trước.")
            return
        remaining = len(self.project.shots) - self.project.completed_shots
        if remaining <= 0:
            QMessageBox.information(self, "Đã hoàn thành", "Tất cả shot đã có video.")
            return
        answer = QMessageBox.question(
            self, "Xác nhận render Veo",
            f"Sẽ gửi tối đa {remaining} yêu cầu Veo. Quá trình có thể lâu và phát sinh chi phí API. Tiếp tục?"
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.stop_flag = False

        def task(progress):
            return VeoService().render_project(
                self.project, self.project_dir, progress, lambda: self.stop_flag
            )

        worker = FilmWorker(task)
        worker.signals.progress.connect(self._on_progress)
        worker.signals.completed.connect(self._on_render_completed)
        worker.signals.failed.connect(self._on_failed)
        self.thread_pool.start(worker)

    def stop_render(self) -> None:
        self.stop_flag = True
        self.status_label.setText("Đã yêu cầu dừng sau shot hiện tại")

    def attach_clip(self) -> None:
        if not self.project or not self.project_dir:
            QMessageBox.warning(self, "Chưa có dự án", "Hãy tạo hoặc mở dự án phim trước.")
            return
        row = self.shot_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Chưa chọn shot", "Hãy chọn một dòng trong bảng.")
            return
        file_name, _ = QFileDialog.getOpenFileName(self, "Chọn clip cho shot", "", "Video (*.mp4 *.mov *.m4v *.webm)")
        if not file_name:
            return
        shot = self.project.shots[row]
        shot.video_path = file_name
        shot.status = "done"
        shot.error = ""
        self.project.save(self.project_dir / "film_project.json")
        self.refresh_project_ui()

    def open_clips_folder(self) -> None:
        if not self.project_dir:
            return
        clips = self.project_dir / "clips"
        clips.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(clips)))

    def assemble_movie(self) -> None:
        if not self.project or not self.project_dir:
            QMessageBox.warning(self, "Chưa có dự án", "Hãy tạo hoặc mở dự án phim trước.")
            return
        default = self.project_dir / "output" / "final_film.mp4"
        file_name, _ = QFileDialog.getSaveFileName(self, "Xuất phim", str(default), "MP4 Video (*.mp4)")
        if not file_name:
            return

        def task(progress):
            return FilmAssemblyService().assemble(self.project, Path(file_name), progress)

        worker = FilmWorker(task)
        worker.signals.progress.connect(self._on_progress)
        worker.signals.completed.connect(self._on_assembly_completed)
        worker.signals.failed.connect(self._on_failed)
        self.thread_pool.start(worker)

    def open_output(self) -> None:
        if not self.project_dir:
            return
        output = self.project_dir / "output" / "final_film.mp4"
        if not output.is_file():
            QMessageBox.warning(self, "Chưa có phim", "Chưa tìm thấy output/final_film.mp4.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(output)))

    def _on_progress(self, value: int, text: str) -> None:
        self.progress.setValue(value)
        self.status_label.setText(text)
        if self.project and self.project_dir and (self.project_dir / "film_project.json").is_file():
            try:
                self.project = FilmProject.load(self.project_dir / "film_project.json")
                self.refresh_project_ui()
            except Exception:
                pass

    def _on_render_completed(self, result: object) -> None:
        if isinstance(result, FilmProject):
            self.project = result
        self.progress.setValue(100)
        self.status_label.setText("Đã hoàn thành hàng đợi Veo")
        self.refresh_project_ui()
        QMessageBox.information(self, "Hoàn thành", "Hàng đợi Veo đã kết thúc. Kiểm tra các shot thất bại trong bảng.")

    def _on_assembly_completed(self, result: object) -> None:
        self.progress.setValue(100)
        self.status_label.setText("Đã xuất phim hoàn chỉnh")
        QMessageBox.information(self, "Xuất phim thành công", str(result))

    def _on_failed(self, message: str) -> None:
        self.status_label.setText("Tác vụ thất bại")
        QMessageBox.critical(self, "Lỗi", message)
