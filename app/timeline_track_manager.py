from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class TrackManagerWidget(QFrame):
    """Quản lý thêm, xóa, đổi tên, khóa, mute, ẩn và màu Track."""

    track_changed = Signal()

    def __init__(self, service, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.setObjectName("card")
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("Quản lý Track", self)
        title.setObjectName("sectionTitle")
        self.kind_combo = QComboBox(self)
        self.kind_combo.addItem("Video", "video")
        self.kind_combo.addItem("Audio", "audio")
        self.kind_combo.addItem("Phụ đề", "subtitle")
        add_button = QPushButton("＋ Track", self)
        add_button.clicked.connect(self._add_track)
        delete_button = QPushButton("Xóa Track", self)
        delete_button.clicked.connect(self._delete_track)

        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.kind_combo)
        header.addWidget(add_button)
        header.addWidget(delete_button)
        root.addLayout(header)

        self.track_list = QListWidget(self)
        self.track_list.setAlternatingRowColors(True)
        root.addWidget(self.track_list)

        actions = QHBoxLayout()
        for text, callback in (
            ("Đổi tên", self._rename_track),
            ("🔒 Khóa/Mở", lambda: self._toggle_flag("locked", False)),
            ("🔇 Mute/Bật", lambda: self._toggle_flag("muted", False)),
            ("👁 Ẩn/Hiện", lambda: self._toggle_flag("visible", True)),
            ("🎨 Màu", self._choose_color),
        ):
            button = QPushButton(text, self)
            button.clicked.connect(callback)
            actions.addWidget(button)
        actions.addStretch()
        root.addLayout(actions)

    def current_track_id(self) -> str | None:
        item = self.track_list.currentItem()
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return str(value) if value else None

    def refresh(self, selected_track_id: str | None = None) -> None:
        selected_track_id = selected_track_id or self.current_track_id()
        self.track_list.clear()
        for track in self.service.data.get("tracks", []):
            track_type = str(track.get("type", "video"))
            icon = {"video": "🎞", "audio": "🎵", "subtitle": "💬"}.get(
                track_type, "•"
            )
            flags = []
            if track.get("locked", False):
                flags.append("🔒")
            if track.get("muted", False):
                flags.append("🔇")
            if not track.get("visible", True):
                flags.append("🙈")

            text = (
                f"{icon} {track.get('name', 'Track')} · "
                f"{len(track.get('clips', []))} clip"
            )
            if flags:
                text += " · " + " ".join(flags)

            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, track.get("id"))
            color = QColor(str(track.get("color", "#667085")))
            if color.isValid():
                item.setForeground(color.lighter(145))
            self.track_list.addItem(item)
            if track.get("id") == selected_track_id:
                self.track_list.setCurrentItem(item)

        if self.track_list.count() and self.track_list.currentItem() is None:
            self.track_list.setCurrentRow(0)

    def _checkpoint(self) -> None:
        if hasattr(self.service, "checkpoint"):
            self.service.checkpoint()

    def _find_track(self, track_id: str | None):
        if not track_id:
            return None
        return self.service.get_track(track_id)

    def _add_track(self) -> None:
        track_type = str(self.kind_combo.currentData())
        base = {"video": "Video", "audio": "Audio", "subtitle": "Phụ đề"}[
            track_type
        ]
        name, accepted = QInputDialog.getText(
            self,
            "Thêm Track",
            "Tên Track:",
            text=f"{base} {len(self.service.data['tracks']) + 1}",
        )
        if not accepted:
            return
        track = self.service.add_track(name, track_type)
        self._ensure_metadata(track)
        self.refresh(str(track.get("id")))
        self.track_changed.emit()

    def _delete_track(self) -> None:
        track_id = self.current_track_id()
        track = self._find_track(track_id)
        if track is None:
            return
        answer = QMessageBox.question(
            self,
            "Xóa Track",
            f"Xóa Track “{track.get('name', 'Track')}”?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.service.remove_track(track_id)
        self.refresh()
        self.track_changed.emit()

    def _rename_track(self) -> None:
        track_id = self.current_track_id()
        track = self._find_track(track_id)
        if track is None:
            return
        name, accepted = QInputDialog.getText(
            self,
            "Đổi tên Track",
            "Tên mới:",
            text=str(track.get("name", "Track")),
        )
        if not accepted or not name.strip():
            return
        self._checkpoint()
        track["name"] = name.strip()
        self.refresh(track_id)
        self.track_changed.emit()

    def _toggle_flag(self, flag: str, default: bool) -> None:
        track_id = self.current_track_id()
        track = self._find_track(track_id)
        if track is None:
            return
        self._checkpoint()
        track[flag] = not bool(track.get(flag, default))
        self.refresh(track_id)
        self.track_changed.emit()

    def _choose_color(self) -> None:
        track_id = self.current_track_id()
        track = self._find_track(track_id)
        if track is None:
            return
        current = QColor(str(track.get("color", "#667085")))
        color = QColorDialog.getColor(current, self, "Chọn màu Track")
        if not color.isValid():
            return
        self._checkpoint()
        track["color"] = color.name()
        self.refresh(track_id)
        self.track_changed.emit()

    @staticmethod
    def _ensure_metadata(track: dict) -> None:
        colors = {
            "video": "#4355ff",
            "audio": "#20a36a",
            "subtitle": "#d88722",
        }
        track_type = str(track.get("type", "video"))
        track.setdefault("color", colors.get(track_type, "#667085"))
        track.setdefault("locked", False)
        track.setdefault("muted", False)
        track.setdefault("visible", True)
