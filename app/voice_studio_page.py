from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.services.voice_service import VoiceSegment, VoiceService
from app.workers.voice_worker import VoiceWorker


class VoiceStudioPage(QWidget):
    back_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.projects_root = Path(__file__).resolve().parent.parent / "projects"
        self.service = VoiceService(self.projects_root)
        self.voices = self.service.available_voices()
        self.current_project_dir: Path | None = None
        self.segments: list[VoiceSegment] = []
        self.thread: QThread | None = None
        self.worker: VoiceWorker | None = None
        self._build_ui()
        self.refresh_projects()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        header = QHBoxLayout()
        title_box = QVBoxLayout()

        title = QLabel("🎙 Voice Studio", self)
        title.setObjectName("pageTitle")
        description = QLabel(
            "Tạo lời đọc từng cảnh bằng giọng hệ thống macOS và xuất phụ đề SRT.",
            self,
        )
        description.setObjectName("description")
        title_box.addWidget(title)
        title_box.addWidget(description)
        header.addLayout(title_box)
        header.addStretch()

        back_button = QPushButton("← Tổng quan", self)
        back_button.setObjectName("secondaryButton")
        back_button.clicked.connect(self.back_requested.emit)
        header.addWidget(back_button)
        root.addLayout(header)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self._create_project_panel())
        splitter.addWidget(self._create_voice_panel())
        splitter.setSizes([240, 1000])
        root.addWidget(splitter, 1)

    def _create_project_panel(self) -> QWidget:
        panel = QFrame(self)
        panel.setObjectName("card")
        layout = QVBoxLayout(panel)

        label = QLabel("Dự án", panel)
        label.setObjectName("sectionTitle")
        layout.addWidget(label)

        self.project_list = QListWidget(panel)
        self.project_list.itemDoubleClicked.connect(self.open_project)
        layout.addWidget(self.project_list, 1)

        refresh_button = QPushButton("↻ Làm mới", panel)
        refresh_button.setObjectName("secondaryButton")
        refresh_button.clicked.connect(self.refresh_projects)
        layout.addWidget(refresh_button)

        open_button = QPushButton("Mở dự án", panel)
        open_button.setObjectName("primaryButton")
        open_button.clicked.connect(self.open_project)
        layout.addWidget(open_button)
        return panel

    def _create_voice_panel(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QHBoxLayout()

        self.project_label = QLabel("Chưa mở dự án", panel)
        self.project_label.setObjectName("sectionTitle")
        toolbar.addWidget(self.project_label)
        toolbar.addStretch()

        self.stop_button = QPushButton("⏹ Dừng", panel)
        self.stop_button.setObjectName("secondaryButton")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_generation)
        toolbar.addWidget(self.stop_button)

        self.generate_button = QPushButton("▶ Tạo toàn bộ giọng đọc", panel)
        self.generate_button.setObjectName("primaryButton")
        self.generate_button.clicked.connect(self.generate_all)
        toolbar.addWidget(self.generate_button)

        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 8, panel)
        self.table.setHorizontalHeaderLabels(
            [
                "Cảnh",
                "Tên cảnh",
                "Nội dung",
                "Giọng",
                "Tốc độ",
                "Trạng thái",
                "Tiến độ",
                "Tệp audio",
            ]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setColumnWidth(0, 55)
        self.table.setColumnWidth(1, 190)
        self.table.setColumnWidth(2, 380)
        self.table.setColumnWidth(3, 135)
        self.table.setColumnWidth(4, 80)
        self.table.setColumnWidth(5, 110)
        self.table.setColumnWidth(6, 140)
        self.table.setColumnWidth(7, 300)
        layout.addWidget(self.table, 1)

        controls = QHBoxLayout()

        save_button = QPushButton("💾 Lưu Voice Plan", panel)
        save_button.setObjectName("secondaryButton")
        save_button.clicked.connect(self.save_plan)
        controls.addWidget(save_button)

        subtitle_button = QPushButton("CC Xuất phụ đề SRT", panel)
        subtitle_button.setObjectName("secondaryButton")
        subtitle_button.clicked.connect(self.export_subtitles)
        controls.addWidget(subtitle_button)

        controls.addStretch()

        self.status_label = QLabel("Sẵn sàng.", panel)
        self.status_label.setObjectName("description")
        controls.addWidget(self.status_label)
        layout.addLayout(controls)
        return panel

    def refresh_projects(self) -> None:
        self.project_list.clear()
        self.projects_root.mkdir(parents=True, exist_ok=True)

        projects = sorted(
            [path for path in self.projects_root.iterdir() if path.is_dir()],
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

        for project_dir in projects:
            item = QListWidgetItem(project_dir.name)
            item.setData(Qt.ItemDataRole.UserRole, str(project_dir))
            self.project_list.addItem(item)

    def open_project(self, item=None) -> None:
        if item is None:
            item = self.project_list.currentItem()
        if item is None:
            QMessageBox.warning(self, "Chưa chọn dự án", "Hãy chọn một dự án.")
            return

        self.current_project_dir = Path(item.data(Qt.ItemDataRole.UserRole))
        self.segments = self.service.load_segments(self.current_project_dir)
        self.project_label.setText(f"Dự án: {self.current_project_dir.name}")
        self.render_segments()

        if not self.segments:
            QMessageBox.warning(
                self,
                "Chưa có lời đọc",
                "Dự án chưa có director_plan.json hoặc voice_plan.json.",
            )

    def render_segments(self) -> None:
        self.table.setRowCount(0)

        for segment in self.segments:
            row = self.table.rowCount()
            self.table.insertRow(row)

            self.table.setItem(row, 0, QTableWidgetItem(str(segment.scene_number)))
            self.table.setItem(row, 1, QTableWidgetItem(segment.title))

            editor = QTextEdit(self.table)
            editor.setPlainText(segment.text)
            editor.setMinimumHeight(72)
            self.table.setCellWidget(row, 2, editor)

            voice_combo = QComboBox(self.table)
            voice_combo.addItems(self.voices)
            voice_index = voice_combo.findText(segment.voice)
            voice_combo.setCurrentIndex(max(0, voice_index))
            self.table.setCellWidget(row, 3, voice_combo)

            rate_spin = QSpinBox(self.table)
            rate_spin.setRange(80, 360)
            rate_spin.setValue(segment.rate)
            rate_spin.setSuffix(" wpm")
            self.table.setCellWidget(row, 4, rate_spin)

            self.table.setItem(row, 5, QTableWidgetItem(segment.status))

            progress = QProgressBar(self.table)
            progress.setRange(0, 100)
            progress.setValue(100 if segment.status == "Đã tạo" else 0)
            progress.setFormat("%p%")
            self.table.setCellWidget(row, 6, progress)

            self.table.setItem(row, 7, QTableWidgetItem(segment.output_path))
            self.table.setRowHeight(row, 82)

    def collect_segments(self) -> list[VoiceSegment]:
        segments: list[VoiceSegment] = []

        for row in range(self.table.rowCount()):
            text_widget = self.table.cellWidget(row, 2)
            voice_widget = self.table.cellWidget(row, 3)
            rate_widget = self.table.cellWidget(row, 4)

            segments.append(
                VoiceSegment(
                    scene_number=self._int_cell(row, 0, row + 1),
                    title=self._text_cell(row, 1),
                    text=text_widget.toPlainText().strip()
                    if isinstance(text_widget, QTextEdit)
                    else "",
                    voice=voice_widget.currentText()
                    if isinstance(voice_widget, QComboBox)
                    else "System Default",
                    rate=rate_widget.value()
                    if isinstance(rate_widget, QSpinBox)
                    else 180,
                    output_path=self._text_cell(row, 7),
                    status=self._text_cell(row, 5) or "Chưa tạo",
                )
            )

        return segments

    def _text_cell(self, row: int, column: int) -> str:
        item = self.table.item(row, column)
        return item.text().strip() if item else ""

    def _int_cell(self, row: int, column: int, default: int) -> int:
        try:
            return int(self._text_cell(row, column))
        except ValueError:
            return default

    def save_plan(self) -> None:
        if self.current_project_dir is None:
            QMessageBox.warning(self, "Chưa mở dự án", "Hãy mở một dự án trước.")
            return

        self.segments = self.collect_segments()
        path = self.service.save_plan(self.current_project_dir, self.segments)
        self.status_label.setText(f"Đã lưu {path.name}")

    def export_subtitles(self) -> None:
        if self.current_project_dir is None:
            QMessageBox.warning(self, "Chưa mở dự án", "Hãy mở một dự án trước.")
            return

        self.segments = self.collect_segments()
        path = self.service.create_subtitle_file(
            self.current_project_dir,
            self.segments,
        )
        QMessageBox.information(
            self,
            "Đã xuất phụ đề",
            f"Đã lưu:\n{path}",
        )

    def generate_all(self) -> None:
        if self.thread is not None:
            return
        if self.current_project_dir is None:
            QMessageBox.warning(self, "Chưa mở dự án", "Hãy mở một dự án trước.")
            return

        self.segments = self.collect_segments()
        if not self.segments:
            QMessageBox.warning(self, "Không có dữ liệu", "Không có lời đọc để tạo.")
            return

        self.service.save_plan(self.current_project_dir, self.segments)

        self.thread = QThread(self)
        self.worker = VoiceWorker([asdict(segment) for segment in self.segments])
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.on_progress)
        self.worker.segment_finished.connect(self.on_segment_finished)
        self.worker.segment_failed.connect(self.on_segment_failed)
        self.worker.finished.connect(self.on_finished)
        self.worker.stopped.connect(self.on_stopped)

        self.worker.finished.connect(self.thread.quit)
        self.worker.stopped.connect(self.thread.quit)
        self.thread.finished.connect(self.cleanup_thread)

        self.generate_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText("Đang tạo giọng đọc...")
        self.thread.start()

    @Slot(int, int)
    def on_progress(self, index: int, progress: int) -> None:
        if not 0 <= index < len(self.segments):
            return

        self.segments[index].status = "Đang tạo"
        self.table.item(index, 5).setText("Đang tạo")
        widget = self.table.cellWidget(index, 6)
        if isinstance(widget, QProgressBar):
            widget.setValue(progress)

    @Slot(int, str)
    def on_segment_finished(self, index: int, output_path: str) -> None:
        if not 0 <= index < len(self.segments):
            return

        segment = self.segments[index]
        segment.status = "Đã tạo"
        segment.output_path = output_path
        segment.error = ""

        self.table.item(index, 5).setText("Đã tạo")
        self.table.item(index, 7).setText(output_path)

        widget = self.table.cellWidget(index, 6)
        if isinstance(widget, QProgressBar):
            widget.setValue(100)

        if self.current_project_dir is not None:
            self.service.save_plan(self.current_project_dir, self.segments)

    @Slot(int, str)
    def on_segment_failed(self, index: int, error: str) -> None:
        if not 0 <= index < len(self.segments):
            return

        segment = self.segments[index]
        segment.status = "Lỗi"
        segment.error = error
        self.table.item(index, 5).setText("Lỗi")
        self.status_label.setText(f"Lỗi cảnh {segment.scene_number}: {error}")

        if self.current_project_dir is not None:
            self.service.save_plan(self.current_project_dir, self.segments)

    @Slot()
    def on_finished(self) -> None:
        self.status_label.setText("Đã tạo xong toàn bộ giọng đọc.")
        self.generate_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    @Slot()
    def on_stopped(self) -> None:
        self.status_label.setText("Đã dừng tạo giọng đọc.")
        self.generate_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def stop_generation(self) -> None:
        if self.worker is not None:
            self.worker.stop()
            self.status_label.setText("Đang dừng...")
            self.stop_button.setEnabled(False)

    @Slot()
    def cleanup_thread(self) -> None:
        if self.worker is not None:
            self.worker.deleteLater()
        if self.thread is not None:
            self.thread.deleteLater()
        self.worker = None
        self.thread = None
        self.generate_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def closeEvent(self, event) -> None:
        if self.worker is not None:
            self.worker.stop()
        event.accept()
