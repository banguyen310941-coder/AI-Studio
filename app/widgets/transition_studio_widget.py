from __future__ import annotations

from pathlib import Path
import threading
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
    QInputDialog,
    QProgressBar,
    QLabel,
    QMessageBox,
    QFileDialog,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.transitions.render_executor import RenderResult, TransitionRenderExecutor
from app.transitions.transition_service import TransitionService
from app.render.render_job import RenderJob
from app.render.render_queue import RenderQueueManager
from app.widgets.render_queue_widget import RenderQueueDialog


class TransitionStudioWidget(QFrame):
    """Thư viện và Inspector transition tích hợp vào Timeline Editor."""

    transition_changed = Signal()
    seek_requested = Signal(float)
    render_progress = Signal(float, str)
    render_finished = Signal(object)
    render_log = Signal(str)

    def __init__(self, timeline_service, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.service = TransitionService(timeline_service)
        self._selected_id: str | None = None
        self._loading = False
        self._render_executor: TransitionRenderExecutor | None = None
        self._render_thread: threading.Thread | None = None
        self._queue_manager = RenderQueueManager()
        self._queue_dialog: RenderQueueDialog | None = None
        self.render_progress.connect(self._on_render_progress)
        self.render_finished.connect(self._on_render_finished)
        self.render_log.connect(self._on_render_log)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        title_row = QHBoxLayout()
        title = QLabel("Transition Studio 4.9.5.7", self)
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

        self.user_preset_combo = QComboBox(self)
        form.addRow("Preset cá nhân", self.user_preset_combo)
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
        render_plan_button = QPushButton("Xuất Render Plan", self)
        render_plan_button.clicked.connect(self._export_render_plan)
        self.render_button = QPushButton("Render Video", self)
        self.render_button.setObjectName("primaryButton")
        self.render_button.clicked.connect(self._render_video)
        self.cancel_render_button = QPushButton("Hủy Render", self)
        self.cancel_render_button.setEnabled(False)
        self.cancel_render_button.clicked.connect(self._cancel_render)
        queue_add_button = QPushButton("＋ Thêm vào Render Queue", self)
        queue_add_button.clicked.connect(self._add_to_render_queue)
        queue_open_button = QPushButton("Mở Render Queue", self)
        queue_open_button.clicked.connect(self._open_render_queue)
        save_preset_button = QPushButton("Lưu preset cá nhân", self)
        save_preset_button.clicked.connect(self._save_user_preset)
        apply_preset_button = QPushButton("Áp dụng preset đã chọn", self)
        apply_preset_button.clicked.connect(self._apply_user_preset)
        favorite_preset_button = QPushButton("Đánh dấu yêu thích", self)
        favorite_preset_button.clicked.connect(self._toggle_user_preset_favorite)
        delete_preset_button = QPushButton("Xóa preset cá nhân", self)
        delete_preset_button.clicked.connect(self._delete_user_preset)
        import_preset_button = QPushButton("Nhập preset JSON", self)
        import_preset_button.clicked.connect(self._import_user_presets)
        export_preset_button = QPushButton("Xuất preset JSON", self)
        export_preset_button.clicked.connect(self._export_user_presets)
        button_box.addWidget(add_button)
        button_box.addWidget(apply_button)
        button_box.addWidget(delete_button)
        button_box.addWidget(preview_button)
        button_box.addWidget(duplicate_button)
        button_box.addWidget(auto_button)
        button_box.addWidget(enable_all_button)
        button_box.addWidget(disable_all_button)
        button_box.addWidget(render_plan_button)
        button_box.addWidget(self.render_button)
        button_box.addWidget(self.cancel_render_button)
        button_box.addWidget(queue_add_button)
        button_box.addWidget(queue_open_button)
        button_box.addWidget(save_preset_button)
        button_box.addWidget(apply_preset_button)
        button_box.addWidget(favorite_preset_button)
        button_box.addWidget(delete_preset_button)
        button_box.addWidget(import_preset_button)
        button_box.addWidget(export_preset_button)
        button_box.addStretch()
        form_row.addLayout(button_box)
        root.addLayout(form_row)

        self.table = QTableWidget(0, 6, self)
        self.table.setHorizontalHeaderLabels(
            ["Kiểu", "Clip trước", "Clip sau", "Thời lượng", "Easing", "Bật"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
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

        self.render_progress_bar = QProgressBar(self)
        self.render_progress_bar.setRange(0, 1000)
        self.render_progress_bar.setValue(0)
        self.render_progress_bar.setFormat("Sẵn sàng render")
        root.addWidget(self.render_progress_bar)

        self.render_status_label = QLabel("FFmpeg Executor: sẵn sàng", self)
        self.render_status_label.setObjectName("description")
        self.render_status_label.setWordWrap(True)
        root.addWidget(self.render_status_label)

    def refresh(self) -> None:
        self.service.ensure_document()
        self.service.clean_orphans()
        selected = self._selected_id
        self._loading = True
        try:
            self._refresh_clip_combos()
            self._refresh_user_presets()
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

    def _refresh_user_presets(self) -> None:
        current = self.user_preset_combo.currentData()
        self.user_preset_combo.clear()
        for preset in self.service.preset_store.all():
            star = "★ " if preset.favorite else ""
            self.user_preset_combo.addItem(f"{star}{preset.name}", preset.id)
        index = self.user_preset_combo.findData(current)
        if index >= 0:
            self.user_preset_combo.setCurrentIndex(index)

    def _selected_transition_ids(self) -> list[str]:
        ids: list[str] = []
        for item in self.table.selectedItems():
            transition_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
            if transition_id and transition_id not in ids:
                ids.append(transition_id)
        if not ids and self._selected_id:
            ids.append(self._selected_id)
        return ids

    def _save_user_preset(self) -> None:
        name, accepted = QInputDialog.getText(self, "Lưu preset", "Tên preset:")
        if not accepted:
            return
        try:
            preset = self.service.save_user_preset(
                name,
                str(self.type_combo.currentData() or "cross_dissolve"),
                self.duration_spin.value(),
                str(self.easing_combo.currentData() or "ease-in-out"),
            )
            self._refresh_user_presets()
            self._set_combo_data(self.user_preset_combo, preset.id)
        except ValueError as exc:
            QMessageBox.warning(self, "Transition Studio", str(exc))

    def _apply_user_preset(self) -> None:
        preset_id = str(self.user_preset_combo.currentData() or "")
        ids = self._selected_transition_ids()
        if not preset_id:
            QMessageBox.information(self, "Transition Studio", "Chưa có preset cá nhân để áp dụng.")
            return
        if not ids:
            QMessageBox.information(self, "Transition Studio", "Hãy chọn một hoặc nhiều transition.")
            return
        try:
            count = self.service.apply_user_preset(preset_id, ids)
            self.refresh()
            self.transition_changed.emit()
            QMessageBox.information(self, "Transition Studio", f"Đã áp dụng preset cho {count} transition.")
        except (ValueError, KeyError) as exc:
            QMessageBox.warning(self, "Transition Studio", str(exc))

    def _toggle_user_preset_favorite(self) -> None:
        preset_id = str(self.user_preset_combo.currentData() or "")
        preset = self.service.preset_store.get(preset_id)
        if preset is None:
            return
        self.service.preset_store.set_favorite(preset_id, not preset.favorite)
        self._refresh_user_presets()
        self._set_combo_data(self.user_preset_combo, preset_id)

    def _delete_user_preset(self) -> None:
        preset_id = str(self.user_preset_combo.currentData() or "")
        if not preset_id:
            return
        self.service.preset_store.remove(preset_id)
        self._refresh_user_presets()

    def _import_user_presets(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Nhập preset transition", str(Path.cwd()), "JSON (*.json)")
        if not filename:
            return
        try:
            count = self.service.preset_store.import_file(filename)
            self._refresh_user_presets()
            QMessageBox.information(self, "Transition Studio", f"Đã nhập {count} preset.")
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Transition Studio", str(exc))

    def _export_user_presets(self) -> None:
        default_path = str(Path.cwd() / "data" / "transition-presets-export.json")
        filename, _ = QFileDialog.getSaveFileName(self, "Xuất preset transition", default_path, "JSON (*.json)")
        if not filename:
            return
        if not filename.lower().endswith(".json"):
            filename += ".json"
        try:
            target = self.service.preset_store.export_file(filename)
            QMessageBox.information(self, "Transition Studio", f"Đã xuất preset:\n{target}")
        except OSError as exc:
            QMessageBox.warning(self, "Transition Studio", str(exc))

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


    def _export_render_plan(self) -> None:
        try:
            plan = self.service.build_render_plan()
        except (ValueError, KeyError) as exc:
            QMessageBox.warning(self, "Transition Studio", str(exc))
            return
        default_path = str(Path.cwd() / "output" / "transition-render-plan.json")
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Xuất Transition Render Plan",
            default_path,
            "JSON (*.json)",
        )
        if not filename:
            return
        target = plan.save(filename)
        self.render_status_label.setText(f"Đã lưu Render Plan: {target}")
        QMessageBox.information(self, "Transition Studio", f"Đã xuất Render Plan:\n{target}")


    def _add_to_render_queue(self) -> None:
        try:
            plan = self.service.build_render_plan()
        except (ValueError, KeyError) as exc:
            QMessageBox.warning(self, "Render Queue", str(exc))
            return
        default_path = str(Path.cwd() / "output" / f"transition-queue-{len(self._queue_manager.jobs) + 1}.mp4")
        filename, _ = QFileDialog.getSaveFileName(self, "Thêm job vào Render Queue", default_path, "MP4 Video (*.mp4)")
        if not filename:
            return
        if not filename.lower().endswith(".mp4"):
            filename += ".mp4"
        job = RenderJob.from_plan(plan, filename)
        self._queue_manager.add(job)
        self.render_status_label.setText(f"Đã thêm vào Render Queue: {job.name}")
        self._open_render_queue()

    def _open_render_queue(self) -> None:
        if self._queue_dialog is None:
            self._queue_dialog = RenderQueueDialog(self._queue_manager, self)
        self._queue_dialog.refresh()
        self._queue_dialog.show()
        self._queue_dialog.raise_()
        self._queue_dialog.activateWindow()

    def _render_video(self) -> None:
        if self._render_thread is not None and self._render_thread.is_alive():
            QMessageBox.information(self, "Transition Studio", "Một tác vụ render đang chạy.")
            return
        try:
            plan = self.service.build_render_plan()
        except (ValueError, KeyError) as exc:
            QMessageBox.warning(self, "Transition Studio", str(exc))
            return

        default_path = str(Path.cwd() / "output" / "transition-render.mp4")
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Render Transition Video",
            default_path,
            "MP4 Video (*.mp4)",
        )
        if not filename:
            return
        if not filename.lower().endswith(".mp4"):
            filename += ".mp4"

        executor = TransitionRenderExecutor()
        if not executor.available():
            QMessageBox.warning(
                self,
                "Transition Studio",
                "Không tìm thấy FFmpeg. Hãy cài FFmpeg và đảm bảo lệnh ffmpeg có trong PATH.",
            )
            return

        self._render_executor = executor
        self.render_button.setEnabled(False)
        self.cancel_render_button.setEnabled(True)
        self.render_progress_bar.setValue(0)
        self.render_progress_bar.setFormat("Đang chuẩn bị render…")
        self.render_status_label.setText(f"Đầu ra: {filename}")

        def task() -> None:
            try:
                result = executor.render(
                    plan,
                    filename,
                    progress_callback=lambda value, message: self.render_progress.emit(value, message),
                    log_callback=self.render_log.emit,
                )
            except Exception as exc:  # lỗi hệ thống/FFmpeg được báo về UI
                result = RenderResult(False, Path(filename), -1, message=str(exc))
            self.render_finished.emit(result)

        self._render_thread = threading.Thread(target=task, name="transition-render", daemon=True)
        self._render_thread.start()

    def _cancel_render(self) -> None:
        if self._render_executor is not None and self._render_executor.cancel():
            self.render_status_label.setText("Đang hủy render…")
            self.cancel_render_button.setEnabled(False)

    def _on_render_progress(self, value: float, message: str) -> None:
        self.render_progress_bar.setValue(int(max(0.0, min(100.0, value)) * 10))
        self.render_progress_bar.setFormat(message)
        self.render_status_label.setText(message)

    def _on_render_log(self, line: str) -> None:
        if "error" in line.lower() or "invalid" in line.lower():
            self.render_status_label.setText(line[-220:])

    def _on_render_finished(self, result: RenderResult) -> None:
        self.render_button.setEnabled(True)
        self.cancel_render_button.setEnabled(False)
        self._render_executor = None
        self._render_thread = None
        if result.success:
            self.render_progress_bar.setValue(1000)
            self.render_progress_bar.setFormat("Render hoàn tất")
            self.render_status_label.setText(f"Đã render: {result.output_path}")
            QMessageBox.information(self, "Transition Studio", f"Render hoàn tất:\n{result.output_path}")
        elif result.cancelled:
            self.render_progress_bar.setFormat("Đã hủy render")
            self.render_status_label.setText(result.message)
        else:
            self.render_progress_bar.setFormat("Render thất bại")
            self.render_status_label.setText(result.message)
            QMessageBox.warning(self, "Transition Studio", result.message or "Render thất bại.")

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
