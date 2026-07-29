from __future__ import annotations

from copy import deepcopy

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.animation import FFmpegKeyframeCompiler, KeyframeService


class KeyframeAnimationWidget(QFrame):
    """Bộ điều khiển keyframe cho từng video clip.

    Phiên bản 4.9.6.4 bổ sung thao tác tại playhead, sao chép/dán keyframe
    và bố cục gọn để sử dụng tốt trong Timeline Tool Dock.
    """

    animation_changed = Signal()
    PROPERTIES = [
        ("Opacity", "opacity"),
        ("Scale", "scale"),
        ("Vị trí X", "x"),
        ("Vị trí Y", "y"),
        ("Rotation", "rotation"),
    ]

    def __init__(self, timeline_service, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.service = KeyframeService(timeline_service)
        self._clip_id: str | None = None
        self._clipboard: dict | None = None
        self._playhead = 0.0
        self._build()
        self.setEnabled(False)

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        top = QHBoxLayout()
        title = QLabel("◆ Keyframe Animation", self)
        title.setObjectName("sectionTitle")
        self.clip_label = QLabel("Chưa chọn video clip", self)
        self.clip_label.setObjectName("description")
        self.playhead_label = QLabel("Playhead: 0.000 s", self)
        self.playhead_label.setObjectName("description")
        top.addWidget(title)
        top.addWidget(self.clip_label)
        top.addStretch()
        top.addWidget(self.playhead_label)
        root.addLayout(top)

        row = QHBoxLayout()
        self.prop = QComboBox(self)
        for label, value in self.PROPERTIES:
            self.prop.addItem(label, value)

        self.time = QDoubleSpinBox(self)
        self.time.setDecimals(3)
        self.time.setSuffix(" s")
        self.time.setRange(0, 86400)

        self.value = QDoubleSpinBox(self)
        self.value.setDecimals(4)
        self.value.setRange(-10000, 10000)
        self.value.setValue(1)

        self.ease = QComboBox(self)
        for label, value in [
            ("Linear", "linear"),
            ("Ease In", "ease_in"),
            ("Ease Out", "ease_out"),
            ("Ease In/Out", "ease_in_out"),
            ("Hold", "hold"),
        ]:
            self.ease.addItem(label, value)

        at_playhead = QPushButton("↦ Lấy playhead", self)
        at_playhead.clicked.connect(self._use_playhead)
        add = QPushButton("＋ Thêm keyframe", self)
        add.setObjectName("primaryButton")
        add.clicked.connect(self._add)

        for widget in [
            QLabel("Thuộc tính:"), self.prop,
            QLabel("Thời gian:"), self.time,
            at_playhead,
            QLabel("Giá trị:"), self.value,
            QLabel("Easing:"), self.ease,
            add,
        ]:
            row.addWidget(widget)
        row.addStretch()
        root.addLayout(row)

        self.table = QTableWidget(0, 4, self)
        self.table.setMinimumHeight(105)
        self.table.setHorizontalHeaderLabels(
            ["Thuộc tính", "Thời gian", "Giá trị", "Easing"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._load)
        root.addWidget(self.table)

        actions = QHBoxLayout()
        update = QPushButton("Cập nhật", self)
        update.clicked.connect(self._update)
        copy_button = QPushButton("Sao chép", self)
        copy_button.clicked.connect(self._copy)
        self.paste_button = QPushButton("Dán tại playhead", self)
        self.paste_button.clicked.connect(self._paste)
        self.paste_button.setEnabled(False)
        delete = QPushButton("Xóa", self)
        delete.clicked.connect(self._delete)
        clear = QPushButton("Xóa tất cả", self)
        clear.clicked.connect(self._clear)
        for widget in [update, copy_button, self.paste_button, delete, clear]:
            actions.addWidget(widget)
        actions.addStretch()
        root.addLayout(actions)

        self.preview = QLabel("FFmpeg: không có animation filter", self)
        self.preview.setWordWrap(True)
        self.preview.setObjectName("description")
        root.addWidget(self.preview)

    def set_playhead(self, seconds: float) -> None:
        self._playhead = max(0.0, float(seconds))
        self.playhead_label.setText(f"Playhead: {self._playhead:.3f} s")

    def _use_playhead(self) -> None:
        self.time.setValue(min(self.time.maximum(), self._playhead))

    def select_clip(self, clip_id: str | None) -> None:
        self._clip_id = clip_id
        found = self.service.timeline_service.find_clip(clip_id) if clip_id else None
        valid = bool(found and found[0].get("type") == "video")
        self.setEnabled(valid)
        self.clip_label.setText(
            str(found[1].get("title")) if valid else "Keyframe chỉ dùng cho video clip"
        )
        self.time.setMaximum(float(found[1].get("duration", 1)) if valid else 1)
        self.refresh()

    def refresh(self) -> None:
        frames = self.service.keyframes_for_clip(self._clip_id) if self._clip_id else []
        self.table.setRowCount(0)
        labels = {value: label for label, value in self.PROPERTIES}
        easing_labels = {
            "linear": "Linear",
            "ease_in": "Ease In",
            "ease_out": "Ease Out",
            "ease_in_out": "Ease In/Out",
            "hold": "Hold",
        }
        for row, frame in enumerate(frames):
            self.table.insertRow(row)
            values = [
                labels.get(frame.get("property"), frame.get("property")),
                f"{float(frame.get('time', 0)):.3f}",
                f"{float(frame.get('value', 0)):.4f}",
                easing_labels.get(frame.get("easing", "linear"), frame.get("easing")),
            ]
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(str(value)))
        self.preview.setText("FFmpeg: " + FFmpegKeyframeCompiler.preview(frames))

    def _index(self) -> int:
        rows = self.table.selectionModel().selectedRows()
        return rows[0].row() if rows else -1

    def _load(self) -> None:
        index = self._index()
        frames = self.service.keyframes_for_clip(self._clip_id) if self._clip_id else []
        if 0 <= index < len(frames):
            frame = frames[index]
            self.prop.setCurrentIndex(max(0, self.prop.findData(frame.get("property"))))
            self.time.setValue(float(frame.get("time", 0)))
            self.value.setValue(float(frame.get("value", 0)))
            self.ease.setCurrentIndex(max(0, self.ease.findData(frame.get("easing"))))

    def _add(self) -> None:
        if self._clip_id and self.service.add(
            self._clip_id,
            self.prop.currentData(),
            self.time.value(),
            self.value.value(),
            self.ease.currentData(),
        ):
            self.refresh()
            self.animation_changed.emit()

    def _update(self) -> None:
        index = self._index()
        if self._clip_id and index >= 0 and self.service.update(
            self._clip_id,
            index,
            time=self.time.value(),
            value=self.value.value(),
            easing=self.ease.currentData(),
        ):
            self.refresh()
            self.animation_changed.emit()

    def _copy(self) -> None:
        index = self._index()
        frames = self.service.keyframes_for_clip(self._clip_id) if self._clip_id else []
        if 0 <= index < len(frames):
            self._clipboard = deepcopy(frames[index])
            self.paste_button.setEnabled(True)
            self.paste_button.setText(
                f"Dán {self._clipboard.get('property')} tại playhead"
            )

    def _paste(self) -> None:
        if not self._clip_id or not self._clipboard:
            return
        frame = self._clipboard
        if self.service.add(
            self._clip_id,
            frame.get("property", "opacity"),
            min(self.time.maximum(), self._playhead),
            frame.get("value", 0),
            frame.get("easing", "linear"),
        ):
            self.refresh()
            self.animation_changed.emit()

    def _delete(self) -> None:
        index = self._index()
        if self._clip_id and index >= 0 and self.service.remove(self._clip_id, index):
            self.refresh()
            self.animation_changed.emit()

    def _clear(self) -> None:
        if (
            self._clip_id
            and QMessageBox.question(
                self,
                "Xóa keyframe",
                "Xóa toàn bộ keyframe của clip?",
            ) == QMessageBox.StandardButton.Yes
            and self.service.clear(self._clip_id)
        ):
            self.refresh()
            self.animation_changed.emit()
