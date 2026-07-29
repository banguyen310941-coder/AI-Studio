from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QLabel, QMessageBox,
    QProgressBar, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from app.render.background_manager import BackgroundRenderManager
from app.render.render_job import RenderJob, RenderJobStatus
from app.render.resource_monitor import ResourceSnapshot


class RenderQueueDialog(QDialog):
    job_signal = Signal(object)
    queue_finished_signal = Signal()
    resource_signal = Signal(object)

    STATUS_TEXT = {
        RenderJobStatus.QUEUED: "Đang chờ",
        RenderJobStatus.RUNNING: "Background render",
        RenderJobStatus.COMPLETED: "Hoàn tất",
        RenderJobStatus.FAILED: "Lỗi",
        RenderJobStatus.CANCELLED: "Đã hủy",
    }

    def __init__(self, manager: BackgroundRenderManager, parent=None) -> None:
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("Background Render Engine 4.9.5.8")
        self.resize(980, 520)
        self.job_signal.connect(self._job_changed)
        self.queue_finished_signal.connect(self._queue_finished)
        self.resource_signal.connect(self._resource_changed)
        self.manager.on_job_changed = self.job_signal.emit
        self.manager.on_queue_finished = self.queue_finished_signal.emit
        self.manager.on_resource_changed = self.resource_signal.emit
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        title = QLabel("Background Tasks · nhiều worker · pause/resume · Smart Render Cache", self)
        title.setObjectName("sectionTitle")
        root.addWidget(title)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Số worker:", self))
        self.worker_spin = QSpinBox(self)
        self.worker_spin.setRange(1, 4)
        self.worker_spin.setValue(self.manager.max_workers)
        self.worker_spin.valueChanged.connect(self._set_workers)
        controls.addWidget(self.worker_spin)
        self.resource_label = QLabel("CPU: -- · Disk: --", self)
        self.resource_label.setObjectName("description")
        controls.addWidget(self.resource_label)
        controls.addStretch()
        root.addLayout(controls)

        self.table = QTableWidget(0, 5, self)
        self.table.setHorizontalHeaderLabels(["Tên", "Đầu ra", "Trạng thái", "Tiến độ", "Thông báo"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        root.addWidget(self.table)

        row = QHBoxLayout()
        self.start_button = QPushButton("▶ Chạy nền", self)
        self.start_button.setObjectName("primaryButton")
        self.start_button.clicked.connect(self._start)
        self.pause_button = QPushButton("⏸ Tạm dừng nhận job", self)
        self.pause_button.clicked.connect(self._pause_resume)
        self.cancel_button = QPushButton("■ Hủy các job đang chạy", self)
        self.cancel_button.clicked.connect(self._cancel)
        retry = QPushButton("↻ Chạy lại job", self)
        retry.clicked.connect(self._retry)
        remove = QPushButton("Xóa job", self)
        remove.clicked.connect(self._remove)
        clear = QPushButton("Dọn job đã xong", self)
        clear.clicked.connect(self._clear)
        clear_cache = QPushButton("Dọn cache thiếu file", self)
        clear_cache.clicked.connect(self._clear_cache)
        for button in (self.start_button, self.pause_button, self.cancel_button, retry, remove, clear, clear_cache):
            row.addWidget(button)
        row.addStretch()
        root.addLayout(row)
        self.summary = QLabel(self)
        self.summary.setObjectName("description")
        root.addWidget(self.summary)

    def selected_job_id(self) -> str:
        row = self.table.currentRow()
        if row < 0:
            return ""
        item = self.table.item(row, 0)
        return str(item.data(Qt.ItemDataRole.UserRole) or "") if item else ""

    def refresh(self) -> None:
        selected = self.selected_job_id()
        self.table.setRowCount(0)
        for job in self.manager.jobs:
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = [job.name, job.output_path, self.STATUS_TEXT[job.status], "", job.message]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, job.id)
                self.table.setItem(row, col, item)
            progress = QProgressBar(self.table)
            progress.setRange(0, 1000)
            progress.setValue(int(job.progress * 10))
            progress.setFormat(f"{job.progress:.1f}%")
            self.table.setCellWidget(row, 3, progress)
            if job.id == selected:
                self.table.selectRow(row)
        queued = sum(job.status == RenderJobStatus.QUEUED for job in self.manager.jobs)
        complete = sum(job.status == RenderJobStatus.COMPLETED for job in self.manager.jobs)
        failed = sum(job.status == RenderJobStatus.FAILED for job in self.manager.jobs)
        self.summary.setText(
            f"{len(self.manager.jobs)} job · {queued} đang chờ · {self.manager.running_count} đang chạy · "
            f"{complete} hoàn tất · {failed} lỗi · {len(self.manager.cache.records)} cache"
        )
        self.start_button.setEnabled(not self.manager.is_running and queued > 0)
        self.pause_button.setEnabled(self.manager.is_running)
        self.pause_button.setText("▶ Tiếp tục nhận job" if self.manager.is_paused else "⏸ Tạm dừng nhận job")
        self.cancel_button.setEnabled(self.manager.running_count > 0)
        self.worker_spin.setEnabled(not self.manager.is_running)

    def _start(self) -> None:
        if not self.manager.start():
            QMessageBox.information(self, "Background Render", "Không có job đang chờ hoặc engine đang chạy.")
        self.refresh()

    def _pause_resume(self) -> None:
        if self.manager.is_paused:
            self.manager.resume()
        else:
            self.manager.pause()
        self.refresh()

    def _cancel(self) -> None:
        self.manager.cancel_current()
        self.refresh()

    def _retry(self) -> None:
        self.manager.retry(self.selected_job_id())
        self.refresh()

    def _remove(self) -> None:
        if not self.manager.remove(self.selected_job_id()):
            QMessageBox.information(self, "Background Render", "Không thể xóa job đang chạy.")
        self.refresh()

    def _clear(self) -> None:
        self.manager.clear_finished()
        self.refresh()

    def _clear_cache(self) -> None:
        count = self.manager.cache.clear_missing()
        QMessageBox.information(self, "Smart Render Cache", f"Đã xóa {count} mục cache thiếu file.")
        self.refresh()

    def _set_workers(self, value: int) -> None:
        try:
            self.manager.set_max_workers(value)
        except RuntimeError as exc:
            QMessageBox.information(self, "Background Render", str(exc))
            self.worker_spin.setValue(self.manager.max_workers)

    def _job_changed(self, _job: RenderJob) -> None:
        self.refresh()

    def _queue_finished(self) -> None:
        self.refresh()

    def _resource_changed(self, snapshot: ResourceSnapshot) -> None:
        state = " · Đang chờ tài nguyên" if snapshot.overloaded else ""
        self.resource_label.setText(
            f"CPU load: {snapshot.cpu_load_percent:.0f}% · Disk trống: {snapshot.available_disk_gb:.1f} GB{state}"
        )
