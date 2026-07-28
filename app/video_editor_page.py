from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtCore import QThread, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.services.media_render_service import MediaRenderService, VideoEditOptions
from app.workers.media_render_worker import MediaRenderWorker


class VideoEditorPage(QWidget):
    """
    AI Video Editor 4.1.

    Không cập nhật QWidget từ lambda của worker thread.
    Tất cả cập nhật UI đi qua QObject slot trên GUI thread.
    """

    def __init__(self) -> None:
        super().__init__()

        self.service = MediaRenderService()

        self.input_path: Path | None = None
        self.subtitle_path: Path | None = None
        self.music_path: Path | None = None
        self.output_path: Path | None = None
        self.source_duration: float | None = None

        self.thread: QThread | None = None
        self.worker: MediaRenderWorker | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 28, 36, 28)
        root.setSpacing(14)

        title = QLabel("AI Video Editor", self)
        title.setObjectName("pageTitle")

        desc = QLabel(
            "Tải video lên, nhập yêu cầu bằng tiếng Việt rồi xuất "
            "phiên bản đã chỉnh sửa.",
            self,
        )
        desc.setObjectName("description")
        desc.setWordWrap(True)

        root.addWidget(title)
        root.addWidget(desc)

        import_row = QHBoxLayout()

        import_btn = QPushButton("＋ Tải video lên", self)
        import_btn.setObjectName("primaryButton")
        import_btn.clicked.connect(self._choose_video)

        self.input_label = QLabel("Chưa chọn video", self)

        import_row.addWidget(import_btn)
        import_row.addWidget(self.input_label, 1)
        root.addLayout(import_row)

        self.request = QPlainTextEdit(self)
        self.request.setPlaceholderText(
            "Ví dụ: Cắt 3 giây đầu, tăng tốc 1.25x, "
            "chuyển thành video dọc TikTok và tắt tiếng gốc."
        )
        self.request.setMaximumHeight(100)
        root.addWidget(self.request)

        parse_btn = QPushButton("✨ Phân tích yêu cầu", self)
        parse_btn.clicked.connect(self._parse_request)
        root.addWidget(parse_btn)

        form = QFormLayout()

        self.start = QDoubleSpinBox(self)
        self.start.setRange(0, 99999)
        self.start.setSuffix(" giây")

        self.end = QDoubleSpinBox(self)
        self.end.setRange(0, 99999)
        self.end.setSpecialValueText("Đến hết video")
        self.end.setSuffix(" giây")

        self.speed = QDoubleSpinBox(self)
        self.speed.setRange(0.25, 4.0)
        self.speed.setSingleStep(0.05)
        self.speed.setValue(1.0)
        self.speed.setSuffix("x")

        self.crop = QComboBox(self)
        self.crop.addItem("Giữ nguyên", "keep")
        self.crop.addItem("Dọc 9:16", "vertical")
        self.crop.addItem("Ngang 16:9", "horizontal")
        self.crop.addItem("Vuông 1:1", "square")

        self.mute = QCheckBox("Tắt âm thanh gốc", self)

        form.addRow("Bắt đầu:", self.start)
        form.addRow("Kết thúc:", self.end)
        form.addRow("Tốc độ:", self.speed)
        form.addRow("Khung hình:", self.crop)
        form.addRow("Âm thanh:", self.mute)
        root.addLayout(form)

        extras = QHBoxLayout()

        sub_btn = QPushButton("Chọn phụ đề SRT", self)
        sub_btn.clicked.connect(self._choose_subtitle)

        music_btn = QPushButton("Chọn nhạc nền", self)
        music_btn.clicked.connect(self._choose_music)

        output_btn = QPushButton("Chọn nơi lưu", self)
        output_btn.clicked.connect(self._choose_output)

        extras.addWidget(sub_btn)
        extras.addWidget(music_btn)
        extras.addWidget(output_btn)
        extras.addStretch()
        root.addLayout(extras)

        self.extra_label = QLabel(
            "Phụ đề: chưa chọn | Nhạc: chưa chọn",
            self,
        )
        self.extra_label.setObjectName("description")
        root.addWidget(self.extra_label)

        self.progress = QProgressBar(self)
        self.progress.setValue(0)

        self.status = QLabel("Sẵn sàng", self)

        root.addWidget(self.progress)
        root.addWidget(self.status)

        bottom = QHBoxLayout()

        self.render_btn = QPushButton(
            "🎞 Chỉnh sửa và xuất video",
            self,
        )
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
    def _choose_video(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn video",
            "",
            "Video (*.mp4 *.mov *.mkv *.avi *.m4v)",
        )

        if not file_name:
            return

        self.input_path = Path(file_name)
        self.input_label.setText(self.input_path.name)

        try:
            self.source_duration = self.service.probe_duration(
                self.input_path
            )
            self.end.setMaximum(self.source_duration)
            self.status.setText(
                f"Thời lượng gốc: {self.source_duration:.1f} giây"
            )
        except Exception as error:
            QMessageBox.warning(
                self,
                "Không đọc được video",
                str(error),
            )

    @Slot()
    def _parse_request(self) -> None:
        values = self.service.parse_natural_edit_request(
            self.request.toPlainText()
        )

        if "start_seconds" in values:
            self.start.setValue(float(values["start_seconds"]))

        if "trim_end_seconds" in values and self.source_duration:
            self.end.setValue(
                max(
                    0,
                    self.source_duration
                    - float(values["trim_end_seconds"]),
                )
            )

        if "speed" in values:
            self.speed.setValue(float(values["speed"]))

        if "crop_mode" in values:
            index = self.crop.findData(values["crop_mode"])
            if index >= 0:
                self.crop.setCurrentIndex(index)

        if values.get("mute_original"):
            self.mute.setChecked(True)

        self.status.setText(
            "Đã áp dụng yêu cầu vào các thông số bên dưới."
        )

    @Slot()
    def _choose_subtitle(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn phụ đề",
            "",
            "Phụ đề (*.srt *.ass *.vtt)",
        )

        if file_name:
            self.subtitle_path = Path(file_name)
            self._refresh_extras()

    @Slot()
    def _choose_music(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn nhạc",
            "",
            "Âm thanh (*.mp3 *.wav *.m4a *.aac)",
        )

        if file_name:
            self.music_path = Path(file_name)
            self._refresh_extras()

    @Slot()
    def _choose_output(self) -> None:
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Lưu video",
            "edited_video.mp4",
            "MP4 (*.mp4)",
        )

        if file_name:
            self.output_path = Path(file_name).with_suffix(".mp4")

    def _refresh_extras(self) -> None:
        subtitle_name = (
            self.subtitle_path.name
            if self.subtitle_path
            else "chưa chọn"
        )
        music_name = (
            self.music_path.name
            if self.music_path
            else "chưa chọn"
        )
        self.extra_label.setText(
            f"Phụ đề: {subtitle_name} | Nhạc: {music_name}"
        )

    @Slot()
    def _start_render(self) -> None:
        if self.thread is not None and self.thread.isRunning():
            return

        if not self.input_path:
            QMessageBox.warning(
                self,
                "Thiếu video",
                "Hãy tải video đầu vào lên.",
            )
            return

        output = self.output_path or (
            Path.cwd() / "output" / "edited_video.mp4"
        )

        end_value = self.end.value()

        options = VideoEditOptions(
            input_path=self.input_path,
            output_path=output,
            start_seconds=self.start.value(),
            end_seconds=end_value if end_value > 0 else None,
            speed=self.speed.value(),
            crop_mode=self.crop.currentData(),
            mute_original=self.mute.isChecked(),
            subtitle_path=self.subtitle_path,
            music_path=self.music_path,
        )

        self.render_btn.setEnabled(False)
        self.open_btn.setEnabled(False)
        self.progress.setValue(0)
        self.status.setText("Đang chuẩn bị...")

        thread = QThread(self)
        worker = MediaRenderWorker(
            lambda progress: self.service.edit_video(
                options,
                progress,
            )
        )
        worker.moveToThread(thread)

        thread.started.connect(worker.run)

        # Quan trọng: dùng bound slots, không dùng lambda để cập nhật UI.
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
            "Không thể chỉnh sửa video",
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
