from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.lut import FFmpegLUTCompiler, LUTService


class LUTManagerWidget(QFrame):
    lut_changed = Signal()

    def __init__(self, timeline_service, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.service = LUTService(timeline_service)
        self._clip_id: str | None = None
        self._entries: list[dict] = []
        self._build_ui()
        self.setEnabled(False)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("🎞 LUT Manager", self)
        title.setObjectName("sectionTitle")
        self.clip_label = QLabel("Chưa chọn video clip", self)
        self.clip_label.setObjectName("description")
        header.addWidget(title)
        header.addSpacing(12)
        header.addWidget(self.clip_label)
        header.addStretch()
        root.addLayout(header)

        selection = QHBoxLayout()
        self.lut_combo = QComboBox(self)
        self.lut_combo.setMinimumWidth(260)
        self.interpolation_combo = QComboBox(self)
        self.interpolation_combo.addItem("Tetrahedral", "tetrahedral")
        self.interpolation_combo.addItem("Trilinear", "trilinear")
        self.interpolation_combo.addItem("Nearest", "nearest")
        selection.addWidget(QLabel("LUT:", self))
        selection.addWidget(self.lut_combo, 1)
        selection.addWidget(QLabel("Nội suy:", self))
        selection.addWidget(self.interpolation_combo)
        root.addLayout(selection)

        actions = QHBoxLayout()
        import_button = QPushButton("Nhập LUT…", self)
        import_button.clicked.connect(self._import_lut)
        apply_button = QPushButton("Áp dụng", self)
        apply_button.setObjectName("primaryButton")
        apply_button.clicked.connect(self._apply)
        clear_button = QPushButton("Gỡ LUT", self)
        clear_button.clicked.connect(self._clear)
        favorite_button = QPushButton("★ Yêu thích", self)
        favorite_button.clicked.connect(self._toggle_favorite)
        remove_button = QPushButton("Xóa khỏi thư viện", self)
        remove_button.clicked.connect(self._remove)
        export_button = QPushButton("Xuất thư viện…", self)
        export_button.clicked.connect(self._export_library)
        for button in (import_button, apply_button, clear_button, favorite_button, remove_button, export_button):
            actions.addWidget(button)
        actions.addStretch()
        root.addLayout(actions)

        self.status_label = QLabel("Thư viện LUT trống", self)
        self.status_label.setObjectName("description")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self.filter_preview = QLabel("FFmpeg: chưa có LUT", self)
        self.filter_preview.setObjectName("description")
        self.filter_preview.setWordWrap(True)
        root.addWidget(self.filter_preview)

    def select_clip(self, clip_id: str | None) -> None:
        self._clip_id = clip_id
        if not clip_id:
            self.setEnabled(False)
            self.clip_label.setText("Chưa chọn video clip")
            return
        result = self.service.timeline_service.find_clip(clip_id)
        if result is None or result[0].get("type") != "video":
            self.setEnabled(False)
            self.clip_label.setText("LUT chỉ dùng cho video clip")
            return
        self.setEnabled(True)
        self.clip_label.setText(str(result[1].get("title", "Video clip")))
        self.refresh()

    def refresh(self) -> None:
        current_id = ""
        settings = None
        if self._clip_id:
            settings = self.service.settings_for_clip(self._clip_id)
            current_id = settings.get("lut_id", "")
        self._entries = self.service.list_presets()
        self.lut_combo.blockSignals(True)
        self.lut_combo.clear()
        for entry in self._entries:
            prefix = "★ " if entry.get("favorite") else ""
            self.lut_combo.addItem(prefix + str(entry.get("name", "LUT")), entry.get("id"))
        self.lut_combo.blockSignals(False)
        index = self.lut_combo.findData(current_id)
        if index >= 0:
            self.lut_combo.setCurrentIndex(index)
        if settings:
            interp_index = self.interpolation_combo.findData(settings.get("interpolation"))
            if interp_index >= 0:
                self.interpolation_combo.setCurrentIndex(interp_index)
            self.filter_preview.setText(
                f"FFmpeg: {FFmpegLUTCompiler.compile(settings) or 'không áp dụng LUT'}"
            )
        self.status_label.setText(f"{len(self._entries)} LUT trong thư viện")

    def _selected_id(self) -> str:
        return str(self.lut_combo.currentData() or "")

    def _import_lut(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Nhập LUT",
            str(Path.home()),
            "LUT (*.cube *.3dl *.dat *.m3d);;Tất cả tệp (*)",
        )
        if not path:
            return
        try:
            entry = self.service.import_lut(path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Không thể nhập LUT", str(exc))
            return
        self.refresh()
        index = self.lut_combo.findData(entry["id"])
        if index >= 0:
            self.lut_combo.setCurrentIndex(index)
        self.status_label.setText(f"Đã nhập LUT: {entry['name']}")

    def _apply(self) -> None:
        if not self._clip_id or not self._selected_id():
            QMessageBox.information(self, "Chưa chọn LUT", "Hãy nhập và chọn một LUT trước.")
            return
        if self.service.apply_to_clip(
            self._clip_id,
            self._selected_id(),
            str(self.interpolation_combo.currentData()),
        ):
            self.refresh()
            self.lut_changed.emit()

    def _clear(self) -> None:
        if self._clip_id and self.service.clear_clip(self._clip_id):
            self.refresh()
            self.lut_changed.emit()

    def _toggle_favorite(self) -> None:
        lut_id = self._selected_id()
        entry = next((item for item in self._entries if item.get("id") == lut_id), None)
        if entry and self.service.set_favorite(lut_id, not bool(entry.get("favorite"))):
            self.refresh()

    def _remove(self) -> None:
        lut_id = self._selected_id()
        if not lut_id:
            return
        answer = QMessageBox.question(self, "Xóa LUT", "Xóa LUT này khỏi thư viện?")
        if answer == QMessageBox.StandardButton.Yes and self.service.remove_lut(lut_id):
            self.refresh()

    def _export_library(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Xuất thư viện LUT",
            str(Path.home() / "lut_library.json"),
            "JSON (*.json)",
        )
        if path:
            exported = self.service.export_library(path)
            self.status_label.setText(f"Đã xuất: {exported}")
