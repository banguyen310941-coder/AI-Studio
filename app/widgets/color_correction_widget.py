from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.color import ColorCorrectionService, FFmpegColorCompiler


class ColorCorrectionWidget(QFrame):
    color_changed = Signal()

    def __init__(self, timeline_service, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.service = ColorCorrectionService(timeline_service)
        self._clip_id: str | None = None
        self._loading = False
        self._build_ui()
        self.setEnabled(False)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        row = QHBoxLayout()
        title = QLabel("🎨 Color Correction", self)
        title.setObjectName("sectionTitle")
        self.clip_label = QLabel("Chưa chọn video clip", self)
        self.clip_label.setObjectName("description")
        row.addWidget(title)
        row.addSpacing(12)
        row.addWidget(self.clip_label)
        row.addStretch()
        root.addLayout(row)

        form = QFormLayout()
        self.enabled_check = QCheckBox("Bật hiệu chỉnh màu", self)
        form.addRow("Trạng thái", self.enabled_check)

        self.brightness = self._spin(-1.0, 1.0, 0.01)
        self.contrast = self._spin(0.0, 3.0, 0.05)
        self.saturation = self._spin(0.0, 3.0, 0.05)
        self.gamma = self._spin(0.1, 3.0, 0.05)
        self.temperature = self._spin(-1.0, 1.0, 0.05)
        self.tint = self._spin(-1.0, 1.0, 0.05)

        form.addRow("Brightness", self.brightness)
        form.addRow("Contrast", self.contrast)
        form.addRow("Saturation", self.saturation)
        form.addRow("Gamma", self.gamma)
        form.addRow("Temperature", self.temperature)
        form.addRow("Tint", self.tint)
        root.addLayout(form)

        buttons = QHBoxLayout()
        apply_button = QPushButton("Áp dụng", self)
        apply_button.setObjectName("primaryButton")
        apply_button.clicked.connect(self._apply)
        reset_button = QPushButton("Đặt lại", self)
        reset_button.clicked.connect(self._reset)
        buttons.addWidget(apply_button)
        buttons.addWidget(reset_button)
        buttons.addStretch()
        root.addLayout(buttons)

        self.filter_preview = QLabel("FFmpeg: chưa có filter", self)
        self.filter_preview.setObjectName("description")
        self.filter_preview.setWordWrap(True)
        root.addWidget(self.filter_preview)

    def _spin(self, low: float, high: float, step: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox(self)
        spin.setRange(low, high)
        spin.setDecimals(3)
        spin.setSingleStep(step)
        return spin

    def select_clip(self, clip_id: str | None) -> None:
        self._clip_id = clip_id
        if not clip_id:
            self.setEnabled(False)
            self.clip_label.setText("Chưa chọn video clip")
            return
        result = self.service.timeline_service.find_clip(clip_id)
        if result is None or result[0].get("type") != "video":
            self.setEnabled(False)
            self.clip_label.setText("Color Correction chỉ dùng cho video clip")
            return
        self.setEnabled(True)
        self.clip_label.setText(str(result[1].get("title", "Video clip")))
        self.refresh()

    def refresh(self) -> None:
        if not self._clip_id:
            return
        settings = self.service.settings_for_clip(self._clip_id)
        self._loading = True
        try:
            self.enabled_check.setChecked(settings["enabled"])
            self.brightness.setValue(settings["brightness"])
            self.contrast.setValue(settings["contrast"])
            self.saturation.setValue(settings["saturation"])
            self.gamma.setValue(settings["gamma"])
            self.temperature.setValue(settings["temperature"])
            self.tint.setValue(settings["tint"])
        finally:
            self._loading = False
        self._update_preview(settings)

    def _current_settings(self) -> dict:
        return {
            "enabled": self.enabled_check.isChecked(),
            "brightness": self.brightness.value(),
            "contrast": self.contrast.value(),
            "saturation": self.saturation.value(),
            "gamma": self.gamma.value(),
            "temperature": self.temperature.value(),
            "tint": self.tint.value(),
        }

    def _apply(self) -> None:
        if self._clip_id and self.service.apply(self._clip_id, self._current_settings()):
            self._update_preview(self._current_settings())
            self.color_changed.emit()

    def _reset(self) -> None:
        if self._clip_id and self.service.reset(self._clip_id):
            self.refresh()
            self.color_changed.emit()

    def _update_preview(self, settings: dict) -> None:
        compiled = FFmpegColorCompiler.compile(settings)
        self.filter_preview.setText(f"FFmpeg: {compiled or 'không áp dụng filter'}")
