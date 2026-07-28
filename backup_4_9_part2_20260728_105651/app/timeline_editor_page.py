from __future__ import annotations

import uuid
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QMessageBox, QPushButton, QSpinBox, QDoubleSpinBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.models.timeline import TimelineClip, TimelineDocument
from app.services.timeline_service import TimelineService


class TimelineEditorPage(QWidget):
    back_requested = Signal()

    TRACKS = {"Video": "video", "Âm thanh": "audio", "Phụ đề": "subtitle"}

    def __init__(self) -> None:
        super().__init__()
        self.service = TimelineService()
        self.document = TimelineDocument()
        self.current_path: Path | None = None
        self._build_ui()
        self._refresh_table()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        top = QHBoxLayout()
        back = QPushButton("← Tổng quan")
        back.clicked.connect(self.back_requested.emit)
        title = QLabel("Timeline Engine — 4.9 Part 1")
        title.setObjectName("pageTitle")
        top.addWidget(back)
        top.addWidget(title)
        top.addStretch()
        root.addLayout(top)

        controls = QFrame(self)
        controls.setObjectName("card")
        row = QHBoxLayout(controls)
        self.track_combo = QComboBox()
        self.track_combo.addItems(self.TRACKS.keys())
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 120)
        self.fps_spin.setValue(30)
        self.fps_spin.setPrefix("FPS: ")
        add = QPushButton("＋ Thêm clip")
        add.clicked.connect(self._add_clip)
        remove = QPushButton("Xóa clip")
        remove.clicked.connect(self._remove_selected)
        load = QPushButton("Mở timeline")
        load.clicked.connect(self._load)
        save = QPushButton("Lưu timeline")
        save.setObjectName("primaryButton")
        save.clicked.connect(self._save)
        row.addWidget(self.track_combo)
        row.addWidget(self.fps_spin)
        row.addWidget(add)
        row.addWidget(remove)
        row.addStretch()
        row.addWidget(load)
        row.addWidget(save)
        root.addWidget(controls)

        self.table = QTableWidget(0, 6, self)
        self.table.setHorizontalHeaderLabels(["Track", "Tên", "Nguồn", "Bắt đầu (s)", "Thời lượng (s)", "Bật"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        root.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        self.path_label = QLabel("Chưa chọn timeline.json")
        self.duration_label = QLabel("Tổng thời lượng: 0.00 giây")
        bottom.addWidget(self.path_label)
        bottom.addStretch()
        bottom.addWidget(self.duration_label)
        root.addLayout(bottom)

    def _add_clip(self) -> None:
        display_track = self.track_combo.currentText()
        track = self.TRACKS[display_track]
        filters = {
            "video": "Video (*.mp4 *.mov *.mkv *.webm);;Tất cả (*.*)",
            "audio": "Âm thanh (*.wav *.mp3 *.aiff *.m4a);;Tất cả (*.*)",
            "subtitle": "Phụ đề (*.srt *.vtt *.txt);;Tất cả (*.*)",
        }
        source, _ = QFileDialog.getOpenFileName(self, "Chọn tư liệu", "", filters[track])
        if not source:
            return
        start = self.document.duration
        self.document.clips.append(TimelineClip(id=uuid.uuid4().hex, track=track, source=source, start=start, duration=5.0, label=Path(source).stem))
        self._refresh_table()

    def _remove_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        self.document.clips.pop(row)
        self._refresh_table()

    def _refresh_table(self) -> None:
        self.table.setRowCount(len(self.document.clips))
        names = {value: key for key, value in self.TRACKS.items()}
        for row, clip in enumerate(self.document.clips):
            self.table.setItem(row, 0, QTableWidgetItem(names.get(clip.track, clip.track)))
            label = QTableWidgetItem(clip.label)
            self.table.setItem(row, 1, label)
            source = QTableWidgetItem(clip.source)
            source.setFlags(source.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 2, source)
            start = QDoubleSpinBox()
            start.setRange(0, 86400)
            start.setDecimals(2)
            start.setValue(clip.start)
            start.valueChanged.connect(lambda value, i=row: self._set_start(i, value))
            self.table.setCellWidget(row, 3, start)
            duration = QDoubleSpinBox()
            duration.setRange(0.1, 86400)
            duration.setDecimals(2)
            duration.setValue(clip.duration)
            duration.valueChanged.connect(lambda value, i=row: self._set_duration(i, value))
            self.table.setCellWidget(row, 4, duration)
            enabled = QTableWidgetItem()
            enabled.setFlags(enabled.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            enabled.setCheckState(Qt.CheckState.Checked if clip.enabled else Qt.CheckState.Unchecked)
            self.table.setItem(row, 5, enabled)
        self.duration_label.setText(f"Tổng thời lượng: {self.document.duration:.2f} giây")

    def _sync_table(self) -> None:
        for row, clip in enumerate(self.document.clips):
            label = self.table.item(row, 1)
            enabled = self.table.item(row, 5)
            if label:
                clip.label = label.text().strip()
            if enabled:
                clip.enabled = enabled.checkState() == Qt.CheckState.Checked
        self.document.fps = self.fps_spin.value()

    def _set_start(self, index: int, value: float) -> None:
        if index < len(self.document.clips):
            self.document.clips[index].start = value
            self.duration_label.setText(f"Tổng thời lượng: {self.document.duration:.2f} giây")

    def _set_duration(self, index: int, value: float) -> None:
        if index < len(self.document.clips):
            self.document.clips[index].duration = value
            self.duration_label.setText(f"Tổng thời lượng: {self.document.duration:.2f} giây")

    def _load(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Mở timeline", "", "Timeline (timeline.json *.json)")
        if not path:
            return
        try:
            self.document = self.service.load(path)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Không mở được", str(exc))
            return
        self.current_path = Path(path)
        self.fps_spin.setValue(self.document.fps)
        self.path_label.setText(str(self.current_path))
        self._refresh_table()

    def _save(self) -> None:
        self._sync_table()
        path = self.current_path
        if path is None:
            selected, _ = QFileDialog.getSaveFileName(self, "Lưu timeline", "timeline.json", "JSON (*.json)")
            if not selected:
                return
            path = Path(selected)
        try:
            saved = self.service.save(path, self.document)
        except OSError as exc:
            QMessageBox.critical(self, "Không lưu được", str(exc))
            return
        self.current_path = saved
        self.path_label.setText(str(saved))
        self.duration_label.setText(f"Tổng thời lượng: {self.document.duration:.2f} giây")
        QMessageBox.information(self, "Đã lưu", f"Timeline đã lưu tại:\n{saved}")
