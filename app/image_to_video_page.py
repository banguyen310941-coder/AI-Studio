from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QThread, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.services.media_render_service import ImageVideoOptions, MediaRenderService
from app.workers.media_render_worker import MediaRenderWorker


class ImageToVideoPage(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.service = MediaRenderService()
        self.thread: QThread | None = None
        self.worker: MediaRenderWorker | None = None

        self.images: list[Path] = []
        self.audio_path: Path | None = None
        self.output_path: Path | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 28, 36, 28)
        root.setSpacing(16)

        title = QLabel("Ảnh thành video tự động", self)
        title.setObjectName("pageTitle")

        desc = QLabel(
            "Chọn nhiều ảnh, AI Studio sẽ tạo chuyển động Ken Burns, "
            "ghép nhạc và xuất MP4.",
            self,
        )
        desc.setObjectName("description")
        desc.setWordWrap(True)

        root.addWidget(title)
        root.addWidget(desc)

        actions = QHBoxLayout()

        add_btn = QPushButton("＋ Thêm ảnh", self)
        add_btn.setObjectName("primaryButton")
        add_btn.clicked.connect(self._choose_images)

        clear_btn = QPushButton("Xóa danh sách", self)
        clear_btn.clicked.connect(self._clear_images)

        actions.addWidget(add_btn)
        actions.addWidget(clear_btn)
        actions.addStretch()
        root.addLayout(actions)

        self.list_widget = QListWidget(self)
        self.list_widget.setMinimumHeight(220)
        root.addWidget(self.list_widget)

        form = QFormLayout()

        self.duration = QDoubleSpinBox(self)
        self.duration.setRange(1.0, 30.0)
        self.duration.setValue(4.0)
        self.duration.setSuffix(" giây / ảnh")

        self.motion = QComboBox(self)
        self.motion.addItem("Điện ảnh tự động", "cinematic")
        self.motion.addItem("Zoom vào", "zoom_in")
        self.motion.addItem("Zoom ra", "zoom_out")
        self.motion.addItem("Pan trái", "pan_left")
        self.motion.addItem("Pan phải", "pan_right")

        self.resolution = QComboBox(self)
        self.resolution.addItem("Ngang Full HD 16:9", "1920x1080")
        self.resolution.addItem("Dọc Full HD 9:16", "1080x1920")
        self.resolution.addItem("Vuông 1:1", "1080x1080")

        form.addRow("Thời lượng:", self.duration)
        form.addRow("Chuyển động:", self.motion)
        form.addRow("Khung hình:", self.resolution)
        root.addLayout(form)

        media_row = QHBoxLayout()

        self.audio_label = QLabel("Chưa chọn nhạc nền", self)

        audio_btn = QPushButton("Chọn nhạc", self)
        audio_btn.clicked.connect(self._choose_audio)

        output_btn = QPushButton("Chọn nơi lưu", self)
        output_btn.clicked.connect(self._choose_output)

        media_row.addWidget(audio_btn)
        media_row.addWidget(self.audio_label, 1)
        media_row.addWidget(output_btn)
        root.addLayout(media_row)

        self.output_label = QLabel(
            "Mặc định: output/image_video.mp4",
            self,
        )
        self.output_label.setObjectName("description")
        root.addWidget(self.output_label)

        self.progress = QProgressBar(self)
        self.progress.setValue(0)
        root.addWidget(self.progress)

        self.status = QLabel("Sẵn sàng", self)
        root.addWidget(self.status)

        bottom = QHBoxLayout()

        self.render_btn = QPushButton("🎬 Tạo video từ ảnh", self)
        self.render_btn.setObjectName("primaryButton")
        self.render_btn.clicked.connect(self._start_render)

        self.open_btn = QPushButton("Mở video", self)
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(self._open_output)

        bottom.addWidget(self.render_btn)
        bottom.addWidget(self.open_btn)
        bottom.addStretch()
        root.addLayout(bottom)

    @Slot()
    def _choose_images(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Chọn ảnh",
            "",
            "Ảnh (*.png *.jpg *.jpeg *.webp *.bmp)",
        )

        for value in files:
            path = Path(value)
            if path not in self.images:
                self.images.append(path)
                self.list_widget.addItem(path.name)

    @Slot()
    def _clear_images(self) -> None:
        self.images.clear()
        self.list_widget.clear()

    @Slot()
    def _choose_audio(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn nhạc",
            "",
            "Âm thanh (*.mp3 *.wav *.m4a *.aac)",
        )

        if file_name:
            self.audio_path = Path(file_name)
            self.audio_label.setText(self.audio_path.name)

    @Slot()
    def _choose_output(self) -> None:
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Lưu video",
            "image_video.mp4",
            "MP4 (*.mp4)",
        )

        if file_name:
            self.output_path = Path(file_name).with_suffix(".mp4")
            self.output_label.setText(str(self.output_path))

    @Slot()
    def _start_render(self) -> None:
        if self.thread is not None and self.thread.isRunning():
            return

        if not self.images:
            QMessageBox.warning(
                self,
                "Thiếu ảnh",
                "Hãy chọn ít nhất một ảnh.",
            )
            return

        output = self.output_path or (
            Path.cwd() / "output" / "image_video.mp4"
        )

        options = ImageVideoOptions(
            images=list(self.images),
            output_path=output,
            seconds_per_image=self.duration.value(),
            resolution=self.resolution.currentData(),
            motion=self.motion.currentData(),
            audio_path=self.audio_path,
        )

        self._start_job(
            lambda progress: self.service.create_video_from_images(
                options,
                progress,
            )
        )

    def _start_job(self, job: Callable) -> None:
        self.render_btn.setEnabled(False)
        self.open_btn.setEnabled(False)
        self.progress.setValue(0)
        self.status.setText("Đang chuẩn bị...")

        thread = QThread(self)
        worker = MediaRenderWorker(job)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress.connect(self._on_progress)
        worker.completed.connect(self._on_completed)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._on_thread_finished)
        thread.finished.connect(thread.deleteLater)

        self.thread = thread
        self.worker = worker
        thread.start()

    @Slot(int, str)
    def _on_progress(self, value: int, text: str) -> None:
        self.progress.setValue(value)
        self.status.setText(text)

    @Slot(str)
    def _on_completed(self, output: str) -> None:
        self.output_path = Path(output)
        self.output_label.setText(output)
        self.progress.setValue(100)
        self.status.setText("Hoàn thành")
        self.open_btn.setEnabled(True)

        QMessageBox.information(
            self,
            "Hoàn thành",
            f"Video đã được lưu tại:\n{output}",
        )

    @Slot(str)
    def _on_failed(self, error: str) -> None:
        self.status.setText("Thất bại")
        QMessageBox.critical(
            self,
            "Không thể tạo video",
            error,
        )

    @Slot()
    def _on_thread_finished(self) -> None:
        self.render_btn.setEnabled(True)
        self.worker = None
        self.thread = None

    @Slot()
    def _open_output(self) -> None:
        if self.output_path and self.output_path.exists():
            subprocess.run(
                ["open", str(self.output_path)],
                check=False,
            )
