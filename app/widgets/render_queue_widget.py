from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QLabel, QMessageBox,
    QProgressBar, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from app.render.render_job import RenderJob, RenderJobStatus
from app.render.render_queue import RenderQueueManager


class RenderQueueDialog(QDialog):
    job_signal = Signal(object)
    queue_finished_signal = Signal()

    STATUS_TEXT = {
        RenderJobStatus.QUEUED: "Đang chờ",
        RenderJobStatus.RUNNING: "Đang render",
        RenderJobStatus.COMPLETED: "Hoàn tất",
        RenderJobStatus.FAILED: "Lỗi",
        RenderJobStatus.CANCELLED: "Đã hủy",
    }

    def __init__(self, manager: RenderQueueManager, parent=None) -> None:
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("Render Queue Manager 4.9.5.7")
        self.resize(920, 460)
        self.job_signal.connect(self._job_changed)
        self.queue_finished_signal.connect(self._queue_finished)
        self.manager.on_job_changed = self.job_signal.emit
        self.manager.on_queue_finished = self.queue_finished_signal.emit
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        title = QLabel("Render Queue Manager · render tuần tự và tự bỏ qua job lỗi", self)
        title.setObjectName("sectionTitle")
        root.addWidget(title)
        self.table = QTableWidget(0, 5, self)
        self.table.setHorizontalHeaderLabels(["Tên", "Đầu ra", "Trạng thái", "Tiến độ", "Thông báo"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        root.addWidget(self.table)
        row = QHBoxLayout()
        self.start_button = QPushButton("▶ Chạy hàng đợi", self)
        self.start_button.setObjectName("primaryButton")
        self.start_button.clicked.connect(self._start)
        self.cancel_button = QPushButton("■ Hủy job hiện tại", self)
        self.cancel_button.clicked.connect(self._cancel)
        retry = QPushButton("↻ Chạy lại job", self)
        retry.clicked.connect(self._retry)
        remove = QPushButton("Xóa job", self)
        remove.clicked.connect(self._remove)
        clear = QPushButton("Dọn job đã xong", self)
        clear.clicked.connect(self._clear)
        for button in (self.start_button, self.cancel_button, retry, remove, clear):
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
        self.summary.setText(f"{len(self.manager.jobs)} job · {queued} đang chờ · {complete} hoàn tất · {failed} lỗi")
        self.start_button.setEnabled(not self.manager.is_running and queued > 0)
        self.cancel_button.setEnabled(self.manager.is_running)

    def _start(self) -> None:
        if not self.manager.start():
            QMessageBox.information(self, "Render Queue", "Không có job đang chờ hoặc hàng đợi đang chạy.")
        self.refresh()

    def _cancel(self) -> None:
        self.manager.cancel_current()
        self.refresh()

    def _retry(self) -> None:
        self.manager.retry(self.selected_job_id())
        self.refresh()

    def _remove(self) -> None:
        if not self.manager.remove(self.selected_job_id()):
            QMessageBox.information(self, "Render Queue", "Không thể xóa job đang chạy.")
        self.refresh()

    def _clear(self) -> None:
        self.manager.clear_finished()
        self.refresh()

    def _job_changed(self, _job: RenderJob) -> None:
        self.refresh()

    def _queue_finished(self) -> None:
        self.refresh()
