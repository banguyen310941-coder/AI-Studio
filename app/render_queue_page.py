from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.render_queue_service import RenderJob, RenderQueueService
from app.workers.render_queue_worker import RenderQueueWorker


class RenderQueuePage(QWidget):
    back_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.projects_root = Path(__file__).resolve().parent.parent / "projects"
        self.service = RenderQueueService(self.projects_root)
        self.jobs: list[RenderJob] = self.service.load_queue()
        self.thread: QThread | None = None
        self.worker: RenderQueueWorker | None = None
        self._build_ui()
        self.refresh_projects()
        self.render_jobs()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        header = QHBoxLayout()
        title_box = QVBoxLayout()

        title = QLabel("⚡ Render Queue", self)
        title.setObjectName("pageTitle")
        description = QLabel(
            "Tạo hàng đợi từ storyboard, chạy tuần tự, tạm dừng và tiếp tục.",
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
        splitter.addWidget(self._create_queue_panel())
        splitter.setSizes([240, 980])
        root.addWidget(splitter, 1)

    def _create_project_panel(self) -> QWidget:
        panel = QFrame(self)
        panel.setObjectName("card")
        layout = QVBoxLayout(panel)

        label = QLabel("Dự án", panel)
        label.setObjectName("sectionTitle")
        layout.addWidget(label)

        self.project_list = QListWidget(panel)
        layout.addWidget(self.project_list, 1)

        refresh_button = QPushButton("↻ Làm mới", panel)
        refresh_button.setObjectName("secondaryButton")
        refresh_button.clicked.connect(self.refresh_projects)
        layout.addWidget(refresh_button)

        add_button = QPushButton("＋ Thêm toàn bộ shot", panel)
        add_button.setObjectName("primaryButton")
        add_button.clicked.connect(self.add_selected_project)
        layout.addWidget(add_button)
        return panel

    def _create_queue_panel(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QHBoxLayout()
        self.queue_label = QLabel("Hàng đợi render", panel)
        self.queue_label.setObjectName("sectionTitle")
        toolbar.addWidget(self.queue_label)
        toolbar.addStretch()

        retry_button = QPushButton("↻ Chạy lại lỗi", panel)
        retry_button.setObjectName("secondaryButton")
        retry_button.clicked.connect(self.retry_failed)
        toolbar.addWidget(retry_button)

        clear_button = QPushButton("Xóa đã xong", panel)
        clear_button.setObjectName("secondaryButton")
        clear_button.clicked.connect(self.clear_finished)
        toolbar.addWidget(clear_button)

        self.stop_button = QPushButton("⏸ Tạm dừng", panel)
        self.stop_button.setObjectName("secondaryButton")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_queue)
        toolbar.addWidget(self.stop_button)

        self.start_button = QPushButton("▶ Chạy hàng đợi", panel)
        self.start_button.setObjectName("primaryButton")
        self.start_button.clicked.connect(self.start_queue)
        toolbar.addWidget(self.start_button)

        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 8, panel)
        self.table.setHorizontalHeaderLabels(
            [
                "Dự án",
                "Cảnh",
                "Shot",
                "Tên",
                "Trạng thái",
                "Tiến độ",
                "Đầu ra",
                "Lỗi",
            ]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 55)
        self.table.setColumnWidth(2, 55)
        self.table.setColumnWidth(3, 190)
        self.table.setColumnWidth(4, 110)
        self.table.setColumnWidth(5, 150)
        self.table.setColumnWidth(6, 300)
        self.table.setColumnWidth(7, 240)
        layout.addWidget(self.table, 1)

        self.status_label = QLabel("Sẵn sàng.", panel)
        self.status_label.setObjectName("description")
        layout.addWidget(self.status_label)
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

    def add_selected_project(self) -> None:
        item = self.project_list.currentItem()
        if item is None:
            QMessageBox.warning(self, "Chưa chọn dự án", "Hãy chọn một dự án.")
            return

        project_dir = Path(item.data(Qt.ItemDataRole.UserRole))
        new_jobs = self.service.create_jobs_from_project(project_dir)
        if not new_jobs:
            QMessageBox.warning(
                self,
                "Không có shot",
                "Dự án chưa có storyboard.json hoặc director_plan.json.",
            )
            return

        existing = {
            (job.project_dir, job.shot_number)
            for job in self.jobs
            if job.status != "Đã xong"
        }
        added = 0
        for job in new_jobs:
            key = (job.project_dir, job.shot_number)
            if key not in existing:
                self.jobs.append(job)
                existing.add(key)
                added += 1

        self.service.save_queue(self.jobs)
        self.render_jobs()
        self.status_label.setText(f"Đã thêm {added} shot vào hàng đợi.")

    def render_jobs(self) -> None:
        self.table.setRowCount(0)

        for job in self.jobs:
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = [
                job.project_name,
                str(job.scene_number),
                str(job.shot_number),
                job.title,
                job.status,
            ]
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))

            progress = QProgressBar(self.table)
            progress.setRange(0, 100)
            progress.setValue(job.progress)
            progress.setFormat("%p%")
            self.table.setCellWidget(row, 5, progress)

            self.table.setItem(row, 6, QTableWidgetItem(job.output_path))
            self.table.setItem(row, 7, QTableWidgetItem(job.error))

        pending = sum(job.status in {"Chờ render", "Đã tạm dừng"} for job in self.jobs)
        running = sum(job.status == "Đang render" for job in self.jobs)
        finished = sum(job.status == "Đã xong" for job in self.jobs)
        self.queue_label.setText(
            f"Hàng đợi render · {pending} chờ · {running} đang chạy · {finished} xong"
        )

    def start_queue(self) -> None:
        if self.thread is not None:
            return

        start_index = self.service.next_pending_index(self.jobs)
        if start_index < 0:
            QMessageBox.information(self, "Hàng đợi trống", "Không còn shot chờ render.")
            return

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText("Đang chạy hàng đợi...")

        payload = [asdict(job) for job in self.jobs]
        self.thread = QThread(self)
        self.worker = RenderQueueWorker(payload, start_index)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.job_progress.connect(self.on_job_progress)
        self.worker.job_finished.connect(self.on_job_finished)
        self.worker.job_failed.connect(self.on_job_failed)
        self.worker.queue_finished.connect(self.on_queue_finished)
        self.worker.stopped.connect(self.on_queue_stopped)

        self.worker.queue_finished.connect(self.thread.quit)
        self.worker.stopped.connect(self.thread.quit)
        self.thread.finished.connect(self._cleanup_thread)
        self.thread.start()

    @Slot(int, int)
    def on_job_progress(self, index: int, progress: int) -> None:
        if not 0 <= index < len(self.jobs):
            return

        job = self.jobs[index]
        job.status = "Đang render"
        job.progress = progress
        self.service.save_queue(self.jobs)

        self.table.item(index, 4).setText(job.status)
        widget = self.table.cellWidget(index, 5)
        if isinstance(widget, QProgressBar):
            widget.setValue(progress)
        self.render_queue_summary()

    @Slot(int, str)
    def on_job_finished(self, index: int, manifest_path: str) -> None:
        if not 0 <= index < len(self.jobs):
            return

        job = self.jobs[index]
        job.status = "Đã xong"
        job.progress = 100
        job.error = ""
        self.service.save_queue(self.jobs)

        self.table.item(index, 4).setText(job.status)
        self.table.item(index, 6).setText(manifest_path)
        widget = self.table.cellWidget(index, 5)
        if isinstance(widget, QProgressBar):
            widget.setValue(100)
        self.render_queue_summary()

    @Slot(int, str)
    def on_job_failed(self, index: int, error: str) -> None:
        if not 0 <= index < len(self.jobs):
            return

        job = self.jobs[index]
        job.status = "Lỗi"
        job.error = error
        self.service.save_queue(self.jobs)
        self.table.item(index, 4).setText(job.status)
        self.table.item(index, 7).setText(error)
        self.render_queue_summary()

    @Slot()
    def on_queue_finished(self) -> None:
        self.status_label.setText("Đã chạy xong hàng đợi.")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    @Slot()
    def on_queue_stopped(self) -> None:
        for job in self.jobs:
            if job.status == "Đang render":
                job.status = "Đã tạm dừng"
        self.service.save_queue(self.jobs)
        self.render_jobs()
        self.status_label.setText("Đã tạm dừng. Có thể tiếp tục từ shot đang chờ.")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def stop_queue(self) -> None:
        if self.worker is not None:
            self.worker.stop()
            self.stop_button.setEnabled(False)
            self.status_label.setText("Đang tạm dừng...")

    @Slot()
    def _cleanup_thread(self) -> None:
        if self.worker is not None:
            self.worker.deleteLater()
        if self.thread is not None:
            self.thread.deleteLater()
        self.worker = None
        self.thread = None
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def retry_failed(self) -> None:
        self.service.reset_failed(self.jobs)
        self.service.save_queue(self.jobs)
        self.render_jobs()

    def clear_finished(self) -> None:
        self.jobs = [job for job in self.jobs if job.status != "Đã xong"]
        self.service.save_queue(self.jobs)
        self.render_jobs()

    def render_queue_summary(self) -> None:
        pending = sum(job.status in {"Chờ render", "Đã tạm dừng"} for job in self.jobs)
        running = sum(job.status == "Đang render" for job in self.jobs)
        finished = sum(job.status == "Đã xong" for job in self.jobs)
        self.queue_label.setText(
            f"Hàng đợi render · {pending} chờ · {running} đang chạy · {finished} xong"
        )

    def closeEvent(self, event) -> None:
        if self.worker is not None:
            self.worker.stop()
        event.accept()
