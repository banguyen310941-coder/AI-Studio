from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
    from PySide6.QtMultimediaWidgets import QVideoWidget

    MULTIMEDIA_AVAILABLE = True
except ImportError:
    QAudioOutput = object
    QMediaPlayer = object
    QVideoWidget = object
    MULTIMEDIA_AVAILABLE = False


class TimelinePreviewWidget(QFrame):
    """Preview video, playhead và điều khiển playback cho Timeline."""

    playhead_changed = Signal(float)

    def __init__(
        self,
        service,
        parent: QWidget | None = None,
        status_callback: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.status_callback = status_callback
        self.setObjectName("card")

        self._playing = False
        self._loading = False
        self._loaded_source = ""
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        self.media_player = None
        self.audio_output = None
        self.video_widget = None

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(9)

        header = QHBoxLayout()
        title = QLabel("Video Preview", self)
        title.setObjectName("sectionTitle")
        self.info_label = QLabel("Chưa có video tại playhead", self)
        self.info_label.setObjectName("description")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.info_label)
        layout.addLayout(header)

        if MULTIMEDIA_AVAILABLE:
            self.video_widget = QVideoWidget(self)
            self.video_widget.setMinimumHeight(190)
            self.video_widget.setStyleSheet(
                "background:#111318;border-radius:8px;"
            )
            layout.addWidget(self.video_widget, 1)

            self.media_player = QMediaPlayer(self)
            self.audio_output = QAudioOutput(self)
            self.media_player.setAudioOutput(self.audio_output)
            self.media_player.setVideoOutput(self.video_widget)
        else:
            placeholder = QLabel(
                "Preview hình ảnh chưa khả dụng.\n"
                "Các nút playhead và playback vẫn hoạt động.",
                self,
            )
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setMinimumHeight(190)
            placeholder.setStyleSheet(
                "background:#111318;color:#aeb5c4;border-radius:8px;"
            )
            layout.addWidget(placeholder, 1)

        controls = QHBoxLayout()
        self.play_button = QPushButton("▶ Phát", self)
        self.play_button.clicked.connect(self.toggle_playback)

        stop_button = QPushButton("■ Dừng", self)
        stop_button.clicked.connect(self.stop)

        previous_button = QPushButton("◀ Frame", self)
        previous_button.clicked.connect(lambda: self.step_frame(-1))

        next_button = QPushButton("Frame ▶", self)
        next_button.clicked.connect(lambda: self.step_frame(1))

        self.time_label = QLabel("00:00.000 / 01:00.000", self)
        self.time_label.setMinimumWidth(180)

        controls.addWidget(self.play_button)
        controls.addWidget(stop_button)
        controls.addWidget(previous_button)
        controls.addWidget(next_button)
        controls.addSpacing(8)
        controls.addWidget(self.time_label)
        controls.addStretch()
        layout.addLayout(controls)

        self.slider = QSlider(Qt.Orientation.Horizontal, self)
        self.slider.setRange(0, 60000)
        self.slider.valueChanged.connect(self._slider_changed)
        self.slider.sliderPressed.connect(self.pause)
        layout.addWidget(self.slider)

    def refresh(self) -> None:
        duration = float(self.service.data.get("duration", 60.0))
        playhead = float(self.service.data.get("playhead", 0.0))
        self._loading = True
        try:
            self.slider.setMaximum(max(1000, round(duration * 1000)))
            self.slider.setValue(round(playhead * 1000))
        finally:
            self._loading = False
        self._update_labels()
        self._update_source()

    def toggle_playback(self) -> None:
        if self._playing:
            self.pause()
        else:
            self.play()

    def play(self) -> None:
        duration = float(self.service.data.get("duration", 60.0))
        playhead = float(self.service.data.get("playhead", 0.0))
        if playhead >= duration:
            self.set_playhead(0.0)

        fps = max(1, int(self.service.data.get("fps", 30)))
        self._timer.setInterval(max(8, round(1000 / fps)))
        self._playing = True
        self.play_button.setText("⏸ Tạm dừng")
        self._timer.start()
        self._sync_media(play=True)
        self._status("Đang phát timeline")

    def pause(self) -> None:
        self._playing = False
        self._timer.stop()
        self.play_button.setText("▶ Phát")
        if self.media_player is not None:
            self.media_player.pause()
        self._status("Đã tạm dừng timeline")

    def stop(self) -> None:
        self.pause()
        self.set_playhead(0.0)
        if self.media_player is not None:
            self.media_player.stop()
        self._status("Đã dừng timeline")

    def step_frame(self, direction: int) -> None:
        self.pause()
        fps = max(1, int(self.service.data.get("fps", 30)))
        current = float(self.service.data.get("playhead", 0.0))
        self.set_playhead(current + direction / fps)

    def set_playhead(self, seconds: float, *, sync_media: bool = True) -> None:
        self.service.set_playhead(seconds)
        current = float(self.service.data.get("playhead", 0.0))
        self._loading = True
        try:
            self.slider.setValue(round(current * 1000))
        finally:
            self._loading = False
        self._update_labels()
        self._update_source()
        if sync_media:
            self._sync_media(play=self._playing)
        self.playhead_changed.emit(current)

    def jump_to_clip(self, clip: dict) -> None:
        self.set_playhead(float(clip.get("start", 0.0)))

    def _slider_changed(self, value: int) -> None:
        if self._loading:
            return
        self.set_playhead(value / 1000.0)

    def _tick(self) -> None:
        fps = max(1, int(self.service.data.get("fps", 30)))
        current = float(self.service.data.get("playhead", 0.0))
        duration = float(self.service.data.get("duration", 60.0))
        next_time = current + 1 / fps
        if next_time >= duration:
            self.stop()
            return
        self.set_playhead(next_time, sync_media=False)

    def _update_source(self) -> None:
        current = float(self.service.data.get("playhead", 0.0))
        clip = self.service.first_active_video(current)
        if clip is None:
            self.info_label.setText("Chưa có video tại playhead")
            self._loaded_source = ""
            return

        source = str(clip.get("source", ""))
        clip_time = current - float(clip.get("start", 0.0))
        self.info_label.setText(
            f'{clip.get("title", "Video")} · {clip_time:.2f}s'
        )

        if source != self._loaded_source:
            self._loaded_source = source
            if self.media_player is not None and source:
                self.media_player.setSource(
                    QUrl.fromLocalFile(str(Path(source).expanduser()))
                )

    def _sync_media(self, play: bool) -> None:
        if self.media_player is None or not self._loaded_source:
            return

        current = float(self.service.data.get("playhead", 0.0))
        clip = self.service.first_active_video(current)
        if clip is None:
            self.media_player.pause()
            return

        clip_time = max(0.0, current - float(clip.get("start", 0.0)))
        self.media_player.setPosition(round(clip_time * 1000))
        if play:
            self.media_player.play()

    def _update_labels(self) -> None:
        current = float(self.service.data.get("playhead", 0.0))
        duration = float(self.service.data.get("duration", 60.0))
        self.time_label.setText(
            f"{self._format_time(current)} / {self._format_time(duration)}"
        )

    @staticmethod
    def _format_time(seconds: float) -> str:
        value = max(0.0, float(seconds))
        minutes = int(value // 60)
        remaining = value - minutes * 60
        return f"{minutes:02d}:{remaining:06.3f}"

    def _status(self, message: str) -> None:
        if self.status_callback is not None:
            self.status_callback(message)
