from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QVBoxLayout

from app.render.encoder_profiles import PROFILES
from app.render.gpu_detector import GPUDetector
from app.render.render_settings import RenderSettings


class GPUSettingsDialog(QDialog):
    def __init__(self, settings: RenderSettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("GPU Render Acceleration 4.9.5.9")
        self.resize(520, 230)
        root = QVBoxLayout(self)
        intro = QLabel("Tự phát hiện encoder phần cứng và tự quay về CPU khi encoder không khả dụng.", self)
        intro.setWordWrap(True)
        root.addWidget(intro)
        form = QFormLayout()
        self.encoder_combo = QComboBox(self)
        detector = GPUDetector()
        recommended = detector.recommended()
        self.encoder_combo.addItem(f"Tự động · đề xuất {recommended.label}", "auto")
        for item in detector.detect():
            suffix = "khả dụng" if item.available else "không khả dụng"
            self.encoder_combo.addItem(f"{item.label} · {suffix}", item.id)
            if not item.available:
                model_item = self.encoder_combo.model().item(self.encoder_combo.count() - 1)
                if model_item is not None:
                    model_item.setEnabled(False)
        index = self.encoder_combo.findData(settings.encoder_id)
        self.encoder_combo.setCurrentIndex(max(0, index))
        self.profile_combo = QComboBox(self)
        for profile in PROFILES.values():
            self.profile_combo.addItem(profile.name, profile.id)
        index = self.profile_combo.findData(settings.profile_id)
        self.profile_combo.setCurrentIndex(max(0, index))
        form.addRow("Encoder", self.encoder_combo)
        form.addRow("Chất lượng", self.profile_combo)
        root.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def settings(self) -> RenderSettings:
        return RenderSettings(str(self.encoder_combo.currentData()), str(self.profile_combo.currentData()))
