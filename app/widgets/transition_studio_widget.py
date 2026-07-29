from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.transitions.transition_service import TransitionService


class TransitionStudioWidget(QFrame):
    """Thư viện và Inspector transition tích hợp vào Timeline Editor."""

    transition_changed = Signal()
    seek_requested = Signal(float)

    def __init__(self, timeline_service, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.service = TransitionService(timeline_service)
        self._selected_id: str | None = None
        self._loading = False
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        title_row = QHBoxLayout()
        title = QLabel("Transition Studio 4.9.5.3", self)
        title.setObjectName("sectionTitle")
        self.summary_label = QLabel(self)
        self.summary_label.setObjectName("description")
        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(self.summary_label)
        root.addLayout(title_row)

        form_row = QHBoxLayout()
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.from_combo = QComboBox(self)
        self.to_combo = QComboBox(self)
        self.type_combo = QComboBox(self)
        for preset in self.service.presets:
            self.type_combo.addItem(f'{preset["category"]} · {preset["name"]}', preset["id"])
        self.duration_spin = QDoubleSpinBox(self)
        self.duration_spin.setRange(0.1, 10.0)
        self.duration_spin.setDecimals(2)
        self.duration_spin.setSingleStep(0.1)
        self.duration_spin.setValue(1.0)
        self.duration_spin.setSuffix(" s")
        self.easing_combo = QComboBox(self)
        for easing in self.service.EASINGS:
            self.easing_combo.addItem(easing, easing)
        self.enabled_check = QCheckBox("Kích hoạt", self)
        self.enabled_check.setChecked(True)

        form.addRow("Clip trước", self.from_combo)
        form.addRow("Clip sau", self.to_combo)
        form.addRow("Kiểu", self.type_combo)
        form.addRow("Thời lượng", self.duration_spin)
        form.addRow("Easing", self.easing_combo)
        form.addRow("", self.enabled_check)
        form_row.addLayout(form, 1)

        button_box = QVBoxLayout()
        add_button = QPushButton("＋ Thêm transition", self)
        add_button.setObjectName("primaryButton")
        add_button.clicked.connect(self._add_transition)
        apply_button = QPushButton("Áp dụng", self)
        apply_button.clicked.connect(self._apply_transition)
        delete_button = QPushButton("Xóa", self)
        delete_button.clicked.connect(self._delete_transition)
        preview_button = QPushButton("Tới transition", self)
        preview_button.clicked.connect(self._seek_transition)
        duplicate_button = QPushButton("Nhân sang cặp sau", self)
        duplicate_button.clicked.connect(self._duplicate_transition)
        auto_button = QPushButton("Tự nối toàn bộ", self)
        auto_button.clicked.connect(self._auto_add_all)
        enable_all_button = QPushButton("Bật tất cả", self)
        enable_all_button.clicked.connect(lambda: self._set_all_enabled(True))
        disable_all_button = QPushButton("Tắt tất cả", self)
        disable_all_button.clicked.connect(lambda: self._set_all_enabled(False))
        button_box.addWidget(add_button)
        button_box.addWidget(apply_button)
        button_box.addWidget(delete_button)
        button_box.addWidget(preview_button)
        button_box.addWidget(duplicate_button)
        button_box.addWidget(auto_button)
        button_box.addWidget(enable_all_button)
        button_box.addWidget(disable_all_button)
        button_box.addStretch()
        form_row.addLayout(button_box)
        root.addLayout(form_row)

        self.table = QTableWidget(0, 6, self)
        self.table.setHorizontalHeaderLabels(
            ["Kiểu", "Clip trước", "Clip sau", "Thời lượng", "Easing", "Bật"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.setMaximumHeight(170)
        root.addWidget(self.table)

        self.filter_label = QLabel("FFmpeg: chưa chọn transition", self)
        self.filter_label.setObjectName("description")
        self.filter_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self.filter_label)

        self.validation_label = QLabel("Dữ liệu transition hợp lệ", self)
        self.validation_label.setObjectName("description")
        self.validation_label.setWordWrap(True)
        root.addWidget(self.validation_label)

    def refresh(self) -> None:
        self.service.ensure_document()
        self.service.clean_orphans()
        selected = self._selected_id
        self._loading = True
        try:
            self._refresh_clip_combos()
            self.table.setRowCount(0)
            for transition in self.service.data:
                row = self.table.rowCount()
                self.table.insertRow(row)
                from_clip = self._clip_name(str(transition.get("from_clip_id", "")))
                to_clip = self._clip_name(str(transition.get("to_clip_id", "")))
                values = (
                    self.service.preset_name(str(transition.get("type", ""))),
                    from_clip,
                    to_clip,
                    f'{float(transition.get("duration", 1.0)):.2f} s',
                    str(transition.get("easing", "ease-in-out")),
                    "Có" if transition.get("enabled", True) else "Không",
                )
                for column, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    item.setData(Qt.ItemDataRole.UserRole, transition.get("id"))
                    self.table.setItem(row, column, item)
                if transition.get("id") == selected:
                    self.table.selectRow(row)
            summary = self.service.summary()
            self.summary_label.setText(
                f"{summary.count} transition · {summary.total_duration:.2f} giây"
            )
            issues = self.service.validate()
            if issues:
                self.validation_label.setText("⚠ " + " · ".join(issues[:3]))
            else:
                self.validation_label.setText("✓ Dữ liệu transition hợp lệ")
        finally:
            self._loading = False


    def select_transition(self, transition_id: str) -> None:
        """Chọn transition từ Timeline Canvas và đồng bộ Inspector."""
        self._selected_id = transition_id
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and str(item.data(Qt.ItemDataRole.UserRole) or "") == transition_id:
                self.table.selectRow(row)
                self._selection_changed()
                return

    def _refresh_clip_combos(self) -> None:
        current_from = self.from_combo.currentData()
        current_to = self.to_combo.currentData()
        self.from_combo.clear()
        self.to_combo.clear()
        for track in self.service.timeline_service.data.get("tracks", []):
            if track.get("type") != "video":
                continue
            for clip in track.get("clips", []):
                label = f'{track.get("name", "Video")} · {clip.get("title", "Clip")}'
                clip_id = str(clip.get("id", ""))
                self.from_combo.addItem(label, clip_id)
                self.to_combo.addItem(label, clip_id)
        for combo, value in ((self.from_combo, current_from), (self.to_combo, current_to)):
            index = combo.findData(value)
            if index >= 0:
                combo.setCurrentIndex(index)
        if self.to_combo.count() > 1 and self.to_combo.currentIndex() == self.from_combo.currentIndex():
            self.to_combo.setCurrentIndex(1)

    def _add_transition(self) -> None:
        try:
            transition = self.service.add(
                str(self.from_combo.currentData() or ""),
                str(self.to_combo.currentData() or ""),
                str(self.type_combo.currentData() or "cross_dissolve"),
                self.duration_spin.value(),
                str(self.easing_combo.currentData() or "ease-in-out"),
            )
            self._selected_id = str(transition["id"])
            self.refresh()
            self.transition_changed.emit()
        except (ValueError, KeyError) as exc:
            QMessageBox.warning(self, "Transition Studio", str(exc))

    def _auto_add_all(self) -> None:
        try:
            count = self.service.add_all_adjacent(
                transition_type=str(self.type_combo.currentData() or "cross_dissolve"),
                duration=self.duration_spin.value(),
                easing=str(self.easing_combo.currentData() or "ease-in-out"),
            )
            self.refresh()
            self.transition_changed.emit()
            QMessageBox.information(
                self,
                "Transition Studio",
                f"Đã tạo hoặc cập nhật {count} transition giữa các clip liền nhau.",
            )
        except (ValueError, KeyError) as exc:
            QMessageBox.warning(self, "Transition Studio", str(exc))

    def _duplicate_transition(self) -> None:
        if not self._selected_id:
            QMessageBox.information(self, "Transition Studio", "Hãy chọn một transition trước.")
            return
        try:
            transition = self.service.duplicate(self._selected_id)
            self._selected_id = str(transition.get("id", ""))
            self.refresh()
            self.transition_changed.emit()
        except (ValueError, KeyError) as exc:
            QMessageBox.warning(self, "Transition Studio", str(exc))

    def _set_all_enabled(self, enabled: bool) -> None:
        self.service.set_all_enabled(enabled)
        self.refresh()
        self.transition_changed.emit()

    def _apply_transition(self) -> None:
        if not self._selected_id:
            QMessageBox.information(self, "Transition Studio", "Hãy chọn một transition trong bảng.")
            return
        try:
            self.service.update(
                self._selected_id,
                transition_type=str(self.type_combo.currentData()),
                duration=self.duration_spin.value(),
                easing=str(self.easing_combo.currentData()),
                enabled=self.enabled_check.isChecked(),
            )
            self.refresh()
            self.transition_changed.emit()
        except ValueError as exc:
            QMessageBox.warning(self, "Transition Studio", str(exc))

    def _delete_transition(self) -> None:
        if not self._selected_id:
            return
        self.service.remove(self._selected_id)
        self._selected_id = None
        self.refresh()
        self.transition_changed.emit()

    def _selection_changed(self) -> None:
        if self._loading:
            return
        items = self.table.selectedItems()
        if not items:
            self._selected_id = None
            return
        transition_id = str(items[0].data(Qt.ItemDataRole.UserRole) or "")
        transition = self.service.get(transition_id)
        if transition is None:
            return
        self._selected_id = transition_id
        self._loading = True
        try:
            self._set_combo_data(self.from_combo, transition.get("from_clip_id"))
            self._set_combo_data(self.to_combo, transition.get("to_clip_id"))
            self._set_combo_data(self.type_combo, transition.get("type"))
            self.duration_spin.setValue(float(transition.get("duration", 1.0)))
            self._set_combo_data(self.easing_combo, transition.get("easing"))
            self.enabled_check.setChecked(bool(transition.get("enabled", True)))
            try:
                self.filter_label.setText(f"FFmpeg: {self.service.xfade_filter(transition_id)}")
            except (KeyError, ValueError):
                self.filter_label.setText("FFmpeg: không thể biên dịch transition")
        finally:
            self._loading = False

    def _seek_transition(self) -> None:
        transition = self.service.get(self._selected_id or "")
        if transition is not None:
            self.seek_requested.emit(self.service.transition_time(transition))

    def _clip_name(self, clip_id: str) -> str:
        result = self.service.timeline_service.find_clip(clip_id)
        if result is None:
            return "Clip đã xóa"
        track, clip = result
        return f'{track.get("name", "Video")} · {clip.get("title", "Clip")}'

    @staticmethod
    def _set_combo_data(combo: QComboBox, value: Any) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)
