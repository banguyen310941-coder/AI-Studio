from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.services.timeline_service import TimelineService
from app.timeline_preview_widget import TimelinePreviewWidget
from app.timeline_canvas import TimelineCanvas
from app.timeline_track_manager import TrackManagerWidget


class TimelineEditorPage(QWidget):
    """Timeline Editor 4.9.4: Track Manager, lock, mute, ẩn/hiện và màu."""

    back_requested = Signal()

    TRACK_LABELS = {
        "video": "🎞 Video",
        "audio": "🎵 Audio",
        "subtitle": "💬 Phụ đề",
    }

    def __init__(self) -> None:
        super().__init__()
        self.service = TimelineService()
        self._selected_clip_id: str | None = None
        self._loading_form = False
        self._build_ui()
        self.preview.playhead_changed.connect(self._playhead_changed)
        self.canvas.clip_selected.connect(self._select_clip_from_canvas)
        self.canvas.clip_changed.connect(self._canvas_clip_changed)
        self.canvas.duplicate_requested.connect(self._duplicate_clip_by_id)
        self.canvas.split_requested.connect(self._split_clip_by_id)
        self.canvas.delete_requested.connect(self._delete_clip_by_id)
        self.canvas.seek_requested.connect(self.preview.set_playhead)
        self._refresh_all()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        header = QHBoxLayout()
        back_button = QPushButton("← Tổng quan", self)
        back_button.setObjectName("secondaryButton")
        back_button.clicked.connect(self.back_requested.emit)

        title_box = QVBoxLayout()
        title = QLabel("Timeline Editor", self)
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "Sắp xếp video, âm thanh và phụ đề theo thời gian.",
            self,
        )
        subtitle.setObjectName("description")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        header.addWidget(back_button)
        header.addSpacing(10)
        header.addLayout(title_box)
        header.addStretch()
        root.addLayout(header)

        toolbar = QFrame(self)
        toolbar.setObjectName("card")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(14, 12, 14, 12)

        new_button = QPushButton("＋ Mới", toolbar)
        new_button.clicked.connect(self._new_timeline)
        open_button = QPushButton("Mở JSON", toolbar)
        open_button.clicked.connect(self._open_timeline)
        save_button = QPushButton("Lưu", toolbar)
        save_button.setObjectName("primaryButton")
        save_button.clicked.connect(self._save_timeline)
        save_as_button = QPushButton("Lưu thành…", toolbar)
        save_as_button.clicked.connect(self._save_timeline_as)
        undo_button = QPushButton("↶ Undo", toolbar)
        undo_button.clicked.connect(self._undo)
        redo_button = QPushButton("↷ Redo", toolbar)
        redo_button.clicked.connect(self._redo)
        split_button = QPushButton("✂ Cắt clip", toolbar)
        split_button.clicked.connect(self._split_selected_clip)

        toolbar_layout.addWidget(new_button)
        toolbar_layout.addWidget(open_button)
        toolbar_layout.addWidget(save_button)
        toolbar_layout.addWidget(save_as_button)
        toolbar_layout.addSpacing(18)

        toolbar_layout.addWidget(QLabel("FPS:", toolbar))
        self.fps_spin = QSpinBox(toolbar)
        self.fps_spin.setRange(1, 120)
        self.fps_spin.valueChanged.connect(self._settings_changed)
        toolbar_layout.addWidget(self.fps_spin)

        toolbar_layout.addWidget(QLabel("Thời lượng:", toolbar))
        self.duration_spin = QDoubleSpinBox(toolbar)
        self.duration_spin.setRange(1.0, 86400.0)
        self.duration_spin.setDecimals(2)
        self.duration_spin.setSuffix(" giây")
        self.duration_spin.valueChanged.connect(self._settings_changed)
        toolbar_layout.addWidget(self.duration_spin)

        toolbar_layout.addWidget(QLabel("Zoom:", toolbar))
        self.zoom_spin = QDoubleSpinBox(toolbar)
        self.zoom_spin.setRange(0.25, 8.0)
        self.zoom_spin.setSingleStep(0.25)
        self.zoom_spin.setDecimals(2)
        self.zoom_spin.setSuffix("×")
        self.zoom_spin.valueChanged.connect(self._zoom_changed)
        toolbar_layout.addWidget(self.zoom_spin)

        toolbar_layout.addStretch()
        self.summary_label = QLabel(toolbar)
        self.summary_label.setObjectName("description")
        toolbar_layout.addWidget(self.summary_label)
        root.addWidget(toolbar)

        self.preview = TimelinePreviewWidget(
            self.service,
            self,
            status_callback=self._show_preview_status,
        )
        root.addWidget(self.preview)

        self.track_manager = TrackManagerWidget(self.service, self)
        self.track_manager.track_changed.connect(self._track_changed)
        root.addWidget(self.track_manager)

        self.canvas = TimelineCanvas(self.service, self)
        root.addWidget(self.canvas)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)

        table_panel = QFrame(splitter)
        table_panel.setObjectName("card")
        table_layout = QVBoxLayout(table_panel)
        table_layout.setContentsMargins(14, 14, 14, 14)
        table_layout.setSpacing(10)

        action_row = QHBoxLayout()
        add_video = QPushButton("＋ Video", table_panel)
        add_video.clicked.connect(lambda: self._add_clip("video"))
        add_audio = QPushButton("＋ Audio", table_panel)
        add_audio.clicked.connect(lambda: self._add_clip("audio"))
        add_subtitle = QPushButton("＋ Phụ đề", table_panel)
        add_subtitle.clicked.connect(lambda: self._add_clip("subtitle"))
        duplicate = QPushButton("Nhân đôi", table_panel)
        duplicate.clicked.connect(self._duplicate_selected_clip)
        remove = QPushButton("Xóa", table_panel)
        remove.clicked.connect(self._remove_selected_clip)
        jump_button = QPushButton("Tới clip", table_panel)
        jump_button.clicked.connect(self._jump_to_selected_clip)

        for button in (
            add_video,
            add_audio,
            add_subtitle,
            duplicate,
            remove,
            jump_button,
        ):
            action_row.addWidget(button)
        action_row.addStretch()
        table_layout.addLayout(action_row)

        self.clip_table = QTableWidget(0, 7, table_panel)
        self.clip_table.setHorizontalHeaderLabels(
            [
                "Track",
                "Tên clip",
                "Bắt đầu",
                "Thời lượng",
                "Kết thúc",
                "Nguồn/Nội dung",
                "Bật",
            ]
        )
        self.clip_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.clip_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.clip_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.clip_table.verticalHeader().setVisible(False)
        header_view = self.clip_table.horizontalHeader()
        header_view.setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        header_view.setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        header_view.setSectionResizeMode(
            4, QHeaderView.ResizeMode.ResizeToContents
        )
        header_view.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(
            6, QHeaderView.ResizeMode.ResizeToContents
        )
        self.clip_table.itemSelectionChanged.connect(
            self._table_selection_changed
        )
        table_layout.addWidget(self.clip_table, 1)

        inspector = QFrame(splitter)
        inspector.setObjectName("card")
        inspector.setMinimumWidth(320)
        inspector_layout = QVBoxLayout(inspector)
        inspector_layout.setContentsMargins(16, 16, 16, 16)
        inspector_layout.setSpacing(12)

        inspector_title = QLabel("Thuộc tính clip", inspector)
        inspector_title.setObjectName("sectionTitle")
        inspector_layout.addWidget(inspector_title)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.track_combo = QComboBox(inspector)
        self.track_combo.setEnabled(False)
        form.addRow("Track", self.track_combo)

        self.title_edit = QLineEdit(inspector)
        form.addRow("Tên", self.title_edit)

        self.start_spin = QDoubleSpinBox(inspector)
        self.start_spin.setRange(0.0, 86400.0)
        self.start_spin.setDecimals(3)
        self.start_spin.setSuffix(" s")
        form.addRow("Bắt đầu", self.start_spin)

        self.clip_duration_spin = QDoubleSpinBox(inspector)
        self.clip_duration_spin.setRange(0.1, 86400.0)
        self.clip_duration_spin.setDecimals(3)
        self.clip_duration_spin.setSuffix(" s")
        form.addRow("Thời lượng", self.clip_duration_spin)

        self.volume_spin = QDoubleSpinBox(inspector)
        self.volume_spin.setRange(0.0, 2.0)
        self.volume_spin.setSingleStep(0.05)
        self.volume_spin.setDecimals(2)
        form.addRow("Âm lượng", self.volume_spin)

        self.enabled_check = QCheckBox("Kích hoạt clip", inspector)
        form.addRow("", self.enabled_check)
        inspector_layout.addLayout(form)

        inspector_layout.addWidget(QLabel("Nguồn hoặc nội dung:", inspector))
        self.content_edit = QTextEdit(inspector)
        self.content_edit.setPlaceholderText(
            "Đường dẫn video/audio hoặc nội dung phụ đề"
        )
        self.content_edit.setMinimumHeight(150)
        inspector_layout.addWidget(self.content_edit)

        apply_button = QPushButton("Áp dụng thay đổi", inspector)
        apply_button.setObjectName("primaryButton")
        apply_button.clicked.connect(self._apply_clip_changes)
        inspector_layout.addWidget(apply_button)
        inspector_layout.addStretch()

        splitter.addWidget(table_panel)
        splitter.addWidget(inspector)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

    def _new_timeline(self) -> None:
        answer = QMessageBox.question(
            self,
            "Tạo timeline mới",
            "Dữ liệu chưa lưu sẽ bị mất. Tiếp tục?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.service.new()
        self._selected_clip_id = None
        self._refresh_all()

    def _open_timeline(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Mở timeline",
            "",
            "Timeline JSON (*.json);;Tất cả tệp (*)",
        )
        if not path:
            return
        try:
            self.service.load(path)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(
                self,
                "Không mở được timeline",
                str(exc),
            )
            return
        self._selected_clip_id = None
        self._refresh_all()
        QMessageBox.information(self, "Đã mở", f"Đã mở:\n{path}")

    def _save_timeline(self) -> None:
        if self.service.current_path is None:
            self._save_timeline_as()
            return
        try:
            path = self.service.save(self.service.current_path)
        except OSError as exc:
            QMessageBox.critical(self, "Không lưu được", str(exc))
            return
        QMessageBox.information(self, "Đã lưu", f"Đã lưu:\n{path}")

    def _save_timeline_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Lưu timeline",
            "timeline.json",
            "Timeline JSON (*.json)",
        )
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            saved = self.service.save(path)
        except OSError as exc:
            QMessageBox.critical(self, "Không lưu được", str(exc))
            return
        QMessageBox.information(self, "Đã lưu", f"Đã lưu:\n{saved}")

    def _settings_changed(self) -> None:
        if self._loading_form:
            return
        self.service.set_fps(self.fps_spin.value())
        self.service.set_duration(self.duration_spin.value())
        self.preview.refresh()
        self._refresh_summary()

    def _add_clip(self, track_type: str) -> None:
        track = next(
            (
                item
                for item in self.service.data["tracks"]
                if item.get("type") == track_type
            ),
            None,
        )
        if track is None:
            track = self.service.add_track(
                self.TRACK_LABELS.get(track_type, track_type),
                track_type,
            )

        source = ""
        text = ""
        title = ""

        if track_type in {"video", "audio"}:
            label = "Video" if track_type == "video" else "Audio"
            path, _ = QFileDialog.getOpenFileName(
                self,
                f"Chọn {label}",
                "",
                "Media (*.mp4 *.mov *.mkv *.avi *.mp3 *.wav *.aiff *.m4a);;"
                "Tất cả tệp (*)",
            )
            if not path:
                return
            source = path
            title = Path(path).stem
        else:
            title = "Phụ đề mới"
            text = "Nhập nội dung phụ đề tại bảng Thuộc tính clip."

        clip = self.service.add_clip(
            track["id"],
            source,
            float(self.service.data.get("playhead", 0.0)),
            5.0,
            title=title,
            text=text,
        )
        self._selected_clip_id = clip["id"]
        self._refresh_all(select_clip_id=clip["id"])

    def _duplicate_selected_clip(self) -> None:
        if not self._selected_clip_id:
            QMessageBox.information(
                self,
                "Chưa chọn clip",
                "Hãy chọn một clip để nhân đôi.",
            )
            return
        clip = self.service.duplicate_clip(self._selected_clip_id)
        if clip is None:
            return
        self._selected_clip_id = clip["id"]
        self._refresh_all(select_clip_id=clip["id"])

    def _remove_selected_clip(self) -> None:
        if not self._selected_clip_id:
            QMessageBox.information(
                self,
                "Chưa chọn clip",
                "Hãy chọn một clip để xóa.",
            )
            return
        answer = QMessageBox.question(
            self,
            "Xóa clip",
            "Bạn có chắc muốn xóa clip đang chọn?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.service.remove_clip(self._selected_clip_id)
        self._selected_clip_id = None
        self._refresh_all()

    def _table_selection_changed(self) -> None:
        selected = self.clip_table.selectedItems()
        if not selected:
            self._selected_clip_id = None
            self._clear_inspector()
            return
        row = selected[0].row()
        item = self.clip_table.item(row, 0)
        clip_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        self._selected_clip_id = clip_id
        self._load_selected_clip_into_inspector()

    def _load_selected_clip_into_inspector(self) -> None:
        if not self._selected_clip_id:
            self._clear_inspector()
            return
        result = self.service.find_clip(self._selected_clip_id)
        if result is None:
            self._clear_inspector()
            return

        track, clip = result
        self._loading_form = True
        try:
            self.track_combo.clear()
            self.track_combo.addItem(
                self.TRACK_LABELS.get(track["type"], track["name"])
            )
            self.title_edit.setText(str(clip.get("title", "")))
            self.start_spin.setValue(float(clip.get("start", 0.0)))
            self.clip_duration_spin.setValue(
                float(clip.get("duration", 1.0))
            )
            self.volume_spin.setValue(float(clip.get("volume", 1.0)))
            self.enabled_check.setChecked(bool(clip.get("enabled", True)))
            content = (
                clip.get("text", "")
                if track.get("type") == "subtitle"
                else clip.get("source", "")
            )
            self.content_edit.setPlainText(str(content))
            self.volume_spin.setEnabled(track.get("type") == "audio")
        finally:
            self._loading_form = False

    def _apply_clip_changes(self) -> None:
        if not self._selected_clip_id:
            QMessageBox.information(
                self,
                "Chưa chọn clip",
                "Hãy chọn một clip trước.",
            )
            return
        result = self.service.find_clip(self._selected_clip_id)
        if result is None:
            return
        track, _ = result
        content = self.content_edit.toPlainText().strip()
        kwargs = {
            "start": self.start_spin.value(),
            "duration": self.clip_duration_spin.value(),
            "title": self.title_edit.text(),
            "volume": self.volume_spin.value(),
            "enabled": self.enabled_check.isChecked(),
        }
        if track.get("type") == "subtitle":
            kwargs["text"] = content
        else:
            found = self.service.find_clip(self._selected_clip_id)
            if found is not None:
                found[1]["source"] = content

        self.service.update_clip(self._selected_clip_id, **kwargs)
        self._refresh_all(select_clip_id=self._selected_clip_id)

    def _refresh_all(self, select_clip_id: str | None = None) -> None:
        self._loading_form = True
        try:
            self.fps_spin.setValue(int(self.service.data.get("fps", 30)))
            self.duration_spin.setValue(
                float(self.service.data.get("duration", 60.0))
            )
            self.zoom_spin.setValue(
                float(self.service.data.get("zoom", 1.0))
            )
        finally:
            self._loading_form = False
        self.preview.refresh()
        self.track_manager.refresh()
        self.canvas.refresh()
        self._refresh_table(select_clip_id)
        self._refresh_summary()
        if select_clip_id:
            self._load_selected_clip_into_inspector()
        elif not self._selected_clip_id:
            self._clear_inspector()

    def _refresh_table(self, select_clip_id: str | None = None) -> None:
        self.clip_table.setRowCount(0)
        row_to_select = -1

        for track in self.service.data.get("tracks", []):
            for clip in track.get("clips", []):
                row = self.clip_table.rowCount()
                self.clip_table.insertRow(row)
                start = float(clip.get("start", 0.0))
                duration = float(clip.get("duration", 0.0))
                end = start + duration
                track_text = self.TRACK_LABELS.get(
                    track.get("type", ""),
                    track.get("name", "Track"),
                )
                source_or_text = (
                    clip.get("text", "")
                    if track.get("type") == "subtitle"
                    else clip.get("source", "")
                )

                values = [
                    track_text,
                    clip.get("title", "Clip"),
                    f"{start:.3f}",
                    f"{duration:.3f}",
                    f"{end:.3f}",
                    str(source_or_text),
                    "Có" if clip.get("enabled", True) else "Không",
                ]
                for column, value in enumerate(values):
                    item = QTableWidgetItem(str(value))
                    item.setToolTip(str(value))
                    if column in {2, 3, 4}:
                        item.setTextAlignment(
                            Qt.AlignmentFlag.AlignRight
                            | Qt.AlignmentFlag.AlignVCenter
                        )
                    self.clip_table.setItem(row, column, item)

                first_item = self.clip_table.item(row, 0)
                first_item.setData(
                    Qt.ItemDataRole.UserRole,
                    clip.get("id"),
                )
                if clip.get("id") == select_clip_id:
                    row_to_select = row

        if row_to_select >= 0:
            self.clip_table.selectRow(row_to_select)

    def _refresh_summary(self) -> None:
        summary = self.service.summary()
        zoom = float(self.service.data.get("zoom", 1.0))
        self.summary_label.setText(
            f"{summary.track_count} track · {summary.clip_count} clip · "
            f"{summary.duration:.2f}s · {summary.fps} FPS · {zoom:.2f}×"
        )

    def _zoom_changed(self) -> None:
        if self._loading_form:
            return
        self.service.set_zoom(self.zoom_spin.value())
        self.canvas.set_zoom(self.zoom_spin.value())
        row_height = max(26, min(72, round(30 * self.zoom_spin.value())))
        self.clip_table.verticalHeader().setDefaultSectionSize(row_height)
        self._refresh_summary()

    def _playhead_changed(self, seconds: float) -> None:
        self.statusBarMessage = f"Playhead: {seconds:.3f}s"

    def _jump_to_selected_clip(self) -> None:
        if not self._selected_clip_id:
            QMessageBox.information(
                self,
                "Chưa chọn clip",
                "Hãy chọn một clip trước.",
            )
            return
        result = self.service.find_clip(self._selected_clip_id)
        if result is not None:
            self.preview.jump_to_clip(result[1])

    def _show_preview_status(self, message: str) -> None:
        window = self.window()
        if hasattr(window, "statusBar"):
            window.statusBar().showMessage(message, 2500)


    def _track_changed(self) -> None:
        self.track_manager.refresh()
        self.canvas.refresh()
        self._refresh_table(self._selected_clip_id)
        self._refresh_summary()
        self._show_preview_status("Đã cập nhật Track")

    def _select_clip_from_canvas(self, clip_id: str) -> None:
        self._selected_clip_id = clip_id
        self._refresh_table(select_clip_id=clip_id)
        self._load_selected_clip_into_inspector()

    def _canvas_clip_changed(
        self,
        clip_id: str,
        start: float,
        duration: float,
    ) -> None:
        if self.service.move_resize_clip(clip_id, start, duration):
            self._selected_clip_id = clip_id
            self._refresh_all(select_clip_id=clip_id)
            self._show_preview_status("Đã cập nhật vị trí/thời lượng clip")

    def _duplicate_clip_by_id(self, clip_id: str) -> None:
        self._selected_clip_id = clip_id
        self._duplicate_selected_clip()

    def _delete_clip_by_id(self, clip_id: str) -> None:
        self._selected_clip_id = clip_id
        self._remove_selected_clip()

    def _split_clip_by_id(self, clip_id: str) -> None:
        self._selected_clip_id = clip_id
        self._split_selected_clip()

    def _split_selected_clip(self) -> None:
        if not self._selected_clip_id:
            QMessageBox.information(
                self,
                "Chưa chọn clip",
                "Hãy chọn clip cần cắt.",
            )
            return

        playhead = float(self.service.data.get("playhead", 0.0))
        result = self.service.split_clip(self._selected_clip_id, playhead)
        if result is None:
            QMessageBox.warning(
                self,
                "Không thể cắt",
                "Playhead phải nằm bên trong clip và cách hai mép ít nhất 0.05 giây.",
            )
            return

        _, right_clip = result
        self._selected_clip_id = str(right_clip.get("id"))
        self._refresh_all(select_clip_id=self._selected_clip_id)
        self._show_preview_status("Đã cắt clip tại playhead")

    def _undo(self) -> None:
        if not self.service.undo():
            self._show_preview_status("Không có thao tác để Undo")
            return
        self._selected_clip_id = None
        self._refresh_all()
        self._show_preview_status("Đã Undo")

    def _redo(self) -> None:
        if not self.service.redo():
            self._show_preview_status("Không có thao tác để Redo")
            return
        self._selected_clip_id = None
        self._refresh_all()
        self._show_preview_status("Đã Redo")

    def _clear_inspector(self) -> None:
        self._loading_form = True
        try:
            self.track_combo.clear()
            self.title_edit.clear()
            self.start_spin.setValue(0.0)
            self.clip_duration_spin.setValue(1.0)
            self.volume_spin.setValue(1.0)
            self.enabled_check.setChecked(True)
            self.content_edit.clear()
            self.volume_spin.setEnabled(False)
        finally:
            self._loading_form = False
