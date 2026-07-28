from __future__ import annotations

import uuid
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models.timeline import TimelineClip, TimelineDocument
from app.services.timeline_service import TimelineService


class TimelineEditorPage(QWidget):
    back_requested = Signal()

    HEADERS = ("Bật", "Track", "Tên clip", "Nguồn", "Bắt đầu", "Thời lượng", "Âm lượng")

    def __init__(self) -> None:
        super().__init__()
        self.service = TimelineService()
        self.document = TimelineDocument()
        self.current_path: Path | None = None
        self._loading = False
        self._build_ui()
        self._refresh_table()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        top = QHBoxLayout()
        back = QPushButton("← Tổng quan", self)
        back.setObjectName("secondaryButton")
        back.clicked.connect(self.back_requested.emit)
        title_box = QVBoxLayout()
        title = QLabel("Timeline", self)
        title.setObjectName("pageTitle")
        subtitle = QLabel("Sắp xếp video, âm thanh và phụ đề theo thời gian.", self)
        subtitle.setObjectName("description")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        top.addWidget(back)
        top.addSpacing(10)
        top.addLayout(title_box)
        top.addStretch()
        root.addLayout(top)

        settings = QFrame(self)
        settings.setObjectName("card")
        settings_layout = QHBoxLayout(settings)
        settings_layout.setContentsMargins(16, 12, 16, 12)
        settings_layout.addWidget(QLabel("FPS:"))
        self.fps = QSpinBox(settings)
        self.fps.setRange(1, 120)
        self.fps.setValue(30)
        self.fps.valueChanged.connect(self._settings_changed)
        settings_layout.addWidget(self.fps)
        settings_layout.addWidget(QLabel("Khung hình:"))
        self.width = QSpinBox(settings)
        self.width.setRange(16, 7680)
        self.width.setValue(1920)
        self.width.valueChanged.connect(self._settings_changed)
        self.height = QSpinBox(settings)
        self.height.setRange(16, 4320)
        self.height.setValue(1080)
        self.height.valueChanged.connect(self._settings_changed)
        settings_layout.addWidget(self.width)
        settings_layout.addWidget(QLabel("×"))
        settings_layout.addWidget(self.height)
        settings_layout.addStretch()
        self.duration_label = QLabel("Tổng thời lượng: 00:00.0", settings)
        settings_layout.addWidget(self.duration_label)
        root.addWidget(settings)

        toolbar = QHBoxLayout()
        for text, callback in (
            ("＋ Video", lambda: self._add_media("video")),
            ("＋ Audio", lambda: self._add_media("audio")),
            ("＋ Phụ đề", lambda: self._add_media("subtitle")),
            ("Nhân bản", self._duplicate_selected),
            ("Xóa", self._remove_selected),
            ("↑", lambda: self._move_selected(-1)),
            ("↓", lambda: self._move_selected(1)),
        ):
            button = QPushButton(text, self)
            button.setObjectName("secondaryButton")
            button.clicked.connect(callback)
            toolbar.addWidget(button)
        toolbar.addStretch()
        open_button = QPushButton("Mở timeline", self)
        open_button.clicked.connect(self._open_timeline)
        save_as = QPushButton("Lưu thành…", self)
        save_as.clicked.connect(self._save_as)
        save = QPushButton("Lưu", self)
        save.setObjectName("primaryButton")
        save.clicked.connect(self._save)
        toolbar.addWidget(open_button)
        toolbar.addWidget(save_as)
        toolbar.addWidget(save)
        root.addLayout(toolbar)

        self.table = QTableWidget(0, len(self.HEADERS), self)
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.table, 1)

        self.path_label = QLabel("Chưa chọn file timeline.json", self)
        self.path_label.setObjectName("description")
        root.addWidget(self.path_label)

    def _add_media(self, track: str) -> None:
        filters = {
            "video": "Video (*.mp4 *.mov *.mkv *.webm);;Tất cả (*.*)",
            "audio": "Audio (*.wav *.mp3 *.aiff *.m4a *.aac);;Tất cả (*.*)",
            "subtitle": "Phụ đề (*.srt *.vtt *.txt);;Tất cả (*.*)",
        }
        source, _ = QFileDialog.getOpenFileName(self, "Chọn tệp", "", filters[track])
        if not source:
            return
        start = self.document.duration if track == "video" else 0.0
        clip = TimelineClip(
            id=uuid.uuid4().hex,
            track=track,
            name=Path(source).stem,
            source=source,
            start=start,
            duration=5.0,
            volume=1.0,
        )
        self.document.clips.append(clip)
        self._refresh_table(select_row=len(self.document.clips) - 1)

    def _refresh_table(self, select_row: int | None = None) -> None:
        self._loading = True
        self.table.setRowCount(len(self.document.clips))
        for row, clip in enumerate(self.document.clips):
            enabled = QComboBox(self.table)
            enabled.addItems(["Có", "Không"])
            enabled.setCurrentIndex(0 if clip.enabled else 1)
            enabled.currentIndexChanged.connect(lambda _=0, r=row: self._row_changed(r))
            self.table.setCellWidget(row, 0, enabled)

            track = QComboBox(self.table)
            track.addItems(["video", "audio", "subtitle"])
            track.setCurrentText(clip.track)
            track.currentTextChanged.connect(lambda _="", r=row: self._row_changed(r))
            self.table.setCellWidget(row, 1, track)

            self.table.setItem(row, 2, QTableWidgetItem(clip.name))
            self.table.setItem(row, 3, QTableWidgetItem(clip.source))

            start = self._number_box(clip.start, 0.0, 86400.0)
            duration = self._number_box(clip.duration, 0.1, 86400.0)
            volume = self._number_box(clip.volume, 0.0, 1.0)
            for column, widget in ((4, start), (5, duration), (6, volume)):
                widget.valueChanged.connect(lambda _=0.0, r=row: self._row_changed(r))
                self.table.setCellWidget(row, column, widget)
        self._loading = False
        if select_row is not None and 0 <= select_row < self.table.rowCount():
            self.table.selectRow(select_row)
        self._update_duration()

    def _number_box(self, value: float, minimum: float, maximum: float) -> QDoubleSpinBox:
        box = QDoubleSpinBox(self.table)
        box.setRange(minimum, maximum)
        box.setDecimals(2)
        box.setSingleStep(0.25)
        box.setValue(value)
        return box

    def _row_changed(self, row: int) -> None:
        if self._loading or not (0 <= row < len(self.document.clips)):
            return
        clip = self.document.clips[row]
        clip.enabled = self.table.cellWidget(row, 0).currentIndex() == 0
        clip.track = self.table.cellWidget(row, 1).currentText()
        clip.name = self.table.item(row, 2).text().strip() or "Clip"
        clip.source = self.table.item(row, 3).text().strip()
        clip.start = self.table.cellWidget(row, 4).value()
        clip.duration = self.table.cellWidget(row, 5).value()
        clip.volume = self.table.cellWidget(row, 6).value()
        self._update_duration()

    def _sync_text_cells(self) -> None:
        for row in range(len(self.document.clips)):
            self._row_changed(row)

    def _selected_row(self) -> int:
        rows = self.table.selectionModel().selectedRows()
        return rows[0].row() if rows else -1

    def _remove_selected(self) -> None:
        row = self._selected_row()
        if row >= 0:
            self.document.clips.pop(row)
            self._refresh_table(select_row=min(row, len(self.document.clips) - 1))

    def _duplicate_selected(self) -> None:
        self._sync_text_cells()
        row = self._selected_row()
        if row < 0:
            return
        source = self.document.clips[row]
        clone = TimelineClip.from_dict(source.to_dict())
        clone.id = uuid.uuid4().hex
        clone.name = f"{clone.name} copy"
        clone.start = source.start + source.duration
        self.document.clips.insert(row + 1, clone)
        self._refresh_table(select_row=row + 1)

    def _move_selected(self, offset: int) -> None:
        self._sync_text_cells()
        row = self._selected_row()
        target = row + offset
        if row < 0 or not (0 <= target < len(self.document.clips)):
            return
        self.document.clips[row], self.document.clips[target] = self.document.clips[target], self.document.clips[row]
        self._refresh_table(select_row=target)

    def _settings_changed(self) -> None:
        if self._loading:
            return
        self.document.fps = self.fps.value()
        self.document.width = self.width.value()
        self.document.height = self.height.value()

    def _update_duration(self) -> None:
        seconds = self.document.duration
        minutes = int(seconds // 60)
        self.duration_label.setText(f"Tổng thời lượng: {minutes:02d}:{seconds % 60:04.1f}")

    def _open_timeline(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Mở timeline", "", "Timeline (timeline.json *.json)")
        if not path:
            return
        try:
            self.document = self.service.load(path)
        except ValueError as exc:
            QMessageBox.critical(self, "Không mở được timeline", str(exc))
            return
        self.current_path = Path(path)
        self._loading = True
        self.fps.setValue(self.document.fps)
        self.width.setValue(self.document.width)
        self.height.setValue(self.document.height)
        self._loading = False
        self._refresh_table()
        self.path_label.setText(str(self.current_path))

    def _save_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Lưu timeline", "timeline.json", "JSON (*.json)")
        if path:
            self.current_path = Path(path).with_suffix(".json")
            self._save()

    def _save(self) -> None:
        self._sync_text_cells()
        self._settings_changed()
        if self.current_path is None:
            self._save_as()
            return
        try:
            saved = self.service.save(self.current_path, self.document)
        except OSError as exc:
            QMessageBox.critical(self, "Không lưu được", str(exc))
            return
        self.path_label.setText(str(saved))
        QMessageBox.information(self, "Đã lưu", f"Timeline đã lưu tại:\n{saved}")
