from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsScene,
    QGraphicsView,
    QMenu,
    QWidget,
)

from app.transitions.transition_service import TransitionService


@dataclass(slots=True)
class TimelineGeometry:
    pixels_per_second: float = 80.0
    ruler_height: float = 28.0
    track_height: float = 64.0
    track_gap: float = 6.0
    label_width: float = 112.0


class TimelineClipItem(QGraphicsObject):
    """Clip có thể kéo, resize cạnh phải và mở context menu."""

    changed = Signal(str, float, float)
    selected_clip = Signal(str)
    duplicate_requested = Signal(str)
    split_requested = Signal(str)
    delete_requested = Signal(str)

    HANDLE_WIDTH = 10.0

    def __init__(
        self,
        clip: dict[str, Any],
        track_type: str,
        geometry: TimelineGeometry,
        parent: QGraphicsItem | None = None,
    ) -> None:
        super().__init__(parent)
        self.clip = clip
        self.clip_id = str(clip.get("id", ""))
        self.track_type = track_type
        self.geometry = geometry
        self.track_color = str(clip.get("_track_color", ""))
        self.track_locked = bool(clip.get("_track_locked", False))
        self._resizing = False
        self._press_scene_x = 0.0
        self._original_start = float(clip.get("start", 0.0))
        self._original_duration = float(clip.get("duration", 1.0))

        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip(self._tooltip())

    def boundingRect(self) -> QRectF:
        width = max(
            18.0,
            float(self.clip.get("duration", 1.0))
            * self.geometry.pixels_per_second,
        )
        return QRectF(0.0, 0.0, width, self.geometry.track_height - 12.0)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        del option, widget
        rect = self.boundingRect()
        color = self._base_color()
        if not self.clip.get("enabled", True):
            color.setAlpha(95)
        if self.isSelected():
            color = color.lighter(125)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(
            QPen(
                QColor("#ffffff") if self.isSelected() else color.darker(145),
                2.0 if self.isSelected() else 1.0,
            )
        )
        painter.setBrush(color)
        painter.drawRoundedRect(rect, 6.0, 6.0)

        handle_rect = QRectF(
            rect.right() - self.HANDLE_WIDTH,
            rect.top(),
            self.HANDLE_WIDTH,
            rect.height(),
        )
        painter.fillRect(handle_rect, color.lighter(135))

        painter.setPen(QColor("#ffffff"))
        title = str(self.clip.get("title", "Clip"))
        duration = float(self.clip.get("duration", 0.0))
        text = f"{title}\n{duration:.2f}s"
        painter.drawText(
            rect.adjusted(8.0, 5.0, -12.0, -4.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            text,
        )

    def hoverMoveEvent(self, event) -> None:
        if event.position().x() >= self.boundingRect().right() - self.HANDLE_WIDTH:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        else:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event) -> None:
        self.selected_clip.emit(self.clip_id)
        self._press_scene_x = event.scenePos().x()
        self._original_start = float(self.clip.get("start", 0.0))
        self._original_duration = float(self.clip.get("duration", 1.0))
        self._resizing = (
            event.position().x()
            >= self.boundingRect().right() - self.HANDLE_WIDTH
        )
        self.setCursor(
            Qt.CursorShape.SizeHorCursor
            if self._resizing
            else Qt.CursorShape.ClosedHandCursor
        )
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self.track_locked:
            event.accept()
            return
        delta_seconds = (
            event.scenePos().x() - self._press_scene_x
        ) / self.geometry.pixels_per_second

        if self._resizing:
            duration = max(0.1, self._original_duration + delta_seconds)
            duration = self._snap_value(duration)
            self.prepareGeometryChange()
            self.clip["duration"] = duration
            self.update()
        else:
            start = max(0.0, self._original_start + delta_seconds)
            start = self._snap_value(start)
            self.clip["start"] = start
            self.setX(
                self.geometry.label_width
                + start * self.geometry.pixels_per_second
            )
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.changed.emit(
            self.clip_id,
            float(self.clip.get("start", 0.0)),
            float(self.clip.get("duration", 1.0)),
        )
        self._resizing = False
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:
        menu = QMenu()
        duplicate_action = menu.addAction("Nhân đôi clip")
        split_action = menu.addAction("Cắt tại playhead")
        menu.addSeparator()
        delete_action = menu.addAction("Xóa clip")
        selected = menu.exec(event.screenPos())
        if selected == duplicate_action:
            self.duplicate_requested.emit(self.clip_id)
        elif selected == split_action:
            self.split_requested.emit(self.clip_id)
        elif selected == delete_action:
            self.delete_requested.emit(self.clip_id)

    def _snap_value(self, value: float) -> float:
        fps = max(1, int(self.clip.get("_fps", 30)))
        frame = 1.0 / fps
        return round(round(value / frame) * frame, 6)

    def _base_color(self) -> QColor:
        if self.track_color:
            color = QColor(self.track_color)
            if color.isValid():
                return color
        colors = {
            "video": QColor("#4355ff"),
            "audio": QColor("#20a36a"),
            "subtitle": QColor("#d88722"),
        }
        return colors.get(self.track_type, QColor("#667085"))

    def _tooltip(self) -> str:
        return (
            f'{self.clip.get("title", "Clip")}\n'
            f'Bắt đầu: {float(self.clip.get("start", 0.0)):.3f}s\n'
            f'Thời lượng: {float(self.clip.get("duration", 0.0)):.3f}s'
        )


class TimelineTransitionItem(QGraphicsObject):
    """Marker transition có thể chọn, kéo hai cạnh để đổi thời lượng và xóa."""

    selected_transition = Signal(str)
    duration_changed = Signal(str, float)
    delete_requested = Signal(str)

    HANDLE_WIDTH = 8.0

    def __init__(
        self,
        transition: dict[str, Any],
        geometry: TimelineGeometry,
        parent: QGraphicsItem | None = None,
    ) -> None:
        super().__init__(parent)
        self.transition = transition
        self.transition_id = str(transition.get("id", ""))
        self.geometry = geometry
        self._resizing_left = False
        self._resizing_right = False
        self._press_scene_x = 0.0
        self._original_duration = float(transition.get("duration", 1.0))
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
        )
        self.setAcceptHoverEvents(True)
        self.setZValue(30.0)
        self.setToolTip(self._tooltip())

    def boundingRect(self) -> QRectF:
        width = max(18.0, float(self.transition.get("duration", 1.0)) * self.geometry.pixels_per_second)
        return QRectF(-width / 2.0, -14.0, width, 28.0)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        del option, widget
        rect = self.boundingRect()
        color = QColor("#ffd166")
        if not self.transition.get("enabled", True):
            color.setAlpha(85)
        elif self.isSelected():
            color = color.lighter(120)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#ffffff") if self.isSelected() else color.darker(145), 2.0))
        painter.setBrush(color)
        polygon = QPolygonF([
            QPointF(rect.left(), 0.0),
            QPointF(0.0, rect.top()),
            QPointF(rect.right(), 0.0),
            QPointF(0.0, rect.bottom()),
        ])
        painter.drawPolygon(polygon)
        painter.fillRect(QRectF(rect.left(), rect.top(), self.HANDLE_WIDTH, rect.height()), color.lighter(130))
        painter.fillRect(QRectF(rect.right() - self.HANDLE_WIDTH, rect.top(), self.HANDLE_WIDTH, rect.height()), color.lighter(130))

    def hoverMoveEvent(self, event) -> None:
        x = event.position().x()
        rect = self.boundingRect()
        if x <= rect.left() + self.HANDLE_WIDTH or x >= rect.right() - self.HANDLE_WIDTH:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        else:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event) -> None:
        self.selected_transition.emit(self.transition_id)
        self._press_scene_x = event.scenePos().x()
        self._original_duration = float(self.transition.get("duration", 1.0))
        rect = self.boundingRect()
        x = event.position().x()
        self._resizing_left = x <= rect.left() + self.HANDLE_WIDTH
        self._resizing_right = x >= rect.right() - self.HANDLE_WIDTH
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if not (self._resizing_left or self._resizing_right):
            event.accept()
            return
        delta = (event.scenePos().x() - self._press_scene_x) / self.geometry.pixels_per_second
        duration = self._original_duration + (2.0 * delta if self._resizing_right else -2.0 * delta)
        duration = round(max(0.1, min(10.0, duration)), 3)
        self.prepareGeometryChange()
        self.transition["duration"] = duration
        self.setToolTip(self._tooltip())
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if self._resizing_left or self._resizing_right:
            self.duration_changed.emit(self.transition_id, float(self.transition.get("duration", 1.0)))
        self._resizing_left = False
        self._resizing_right = False
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:
        menu = QMenu()
        delete_action = menu.addAction("Xóa transition")
        if menu.exec(event.screenPos()) == delete_action:
            self.delete_requested.emit(self.transition_id)

    def _tooltip(self) -> str:
        return (
            f'Transition: {self.transition.get("type", "cross_dissolve")}\n'
            f'Thời lượng: {float(self.transition.get("duration", 1.0)):.2f}s\n'
            f'Easing: {self.transition.get("easing", "ease-in-out")}\n'
            'Kéo hai cạnh để thay đổi thời lượng.'
        )


class TimelineCanvas(QGraphicsView):
    """Canvas đồ họa cho drag, resize, snap, split và playhead."""

    clip_selected = Signal(str)
    clip_changed = Signal(str, float, float)
    duplicate_requested = Signal(str)
    split_requested = Signal(str)
    delete_requested = Signal(str)
    seek_requested = Signal(float)
    transition_selected = Signal(str)
    transition_changed = Signal(str, float)
    transition_delete_requested = Signal(str)

    def __init__(self, service, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.transition_service = TransitionService(service)
        self.geometry_config = TimelineGeometry()
        self.scene_object = QGraphicsScene(self)
        self.setScene(self.scene_object)
        self.setMinimumHeight(250)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.setStyleSheet(
            "QGraphicsView{background:#111318;border:1px solid #303440;"
            "border-radius:8px;}"
        )
        self.refresh()

    def refresh(self) -> None:
        self.scene_object.clear()
        zoom = float(self.service.data.get("zoom", 1.0))
        self.geometry_config.pixels_per_second = 80.0 * zoom
        duration = float(self.service.data.get("duration", 60.0))
        tracks = [track for track in self.service.data.get("tracks", []) if track.get("visible", True)]

        width = (
            self.geometry_config.label_width
            + duration * self.geometry_config.pixels_per_second
            + 80.0
        )
        height = (
            self.geometry_config.ruler_height
            + len(tracks)
            * (
                self.geometry_config.track_height
                + self.geometry_config.track_gap
            )
            + 20.0
        )
        self.scene_object.setSceneRect(0.0, 0.0, width, height)
        self._draw_ruler(duration)

        for index, track in enumerate(tracks):
            self._draw_track(index, track)

        self._draw_transitions(tracks)
        self._draw_playhead()

    def set_zoom(self, zoom: float) -> None:
        center_time = self.time_at_view_center()
        self.service.set_zoom(zoom)
        self.refresh()
        self.center_on_time(center_time)

    def time_at_view_center(self) -> float:
        scene_point = self.mapToScene(self.viewport().rect().center())
        return max(
            0.0,
            (
                scene_point.x() - self.geometry_config.label_width
            )
            / self.geometry_config.pixels_per_second,
        )

    def center_on_time(self, seconds: float) -> None:
        x = (
            self.geometry_config.label_width
            + max(0.0, seconds) * self.geometry_config.pixels_per_second
        )
        self.centerOn(x, self.sceneRect().center().y())

    def mousePressEvent(self, event) -> None:
        item = self.itemAt(event.position().toPoint())
        if item is None and event.button() == Qt.MouseButton.LeftButton:
            scene_point = self.mapToScene(event.position().toPoint())
            if scene_point.x() >= self.geometry_config.label_width:
                seconds = (
                    scene_point.x() - self.geometry_config.label_width
                ) / self.geometry_config.pixels_per_second
                self.seek_requested.emit(max(0.0, seconds))
        super().mousePressEvent(event)

    def _draw_ruler(self, duration: float) -> None:
        pen = QPen(QColor("#6d7485"))
        text_color = QColor("#d4d7df")
        step = self._ruler_step()

        second = 0.0
        while second <= duration + 0.0001:
            x = (
                self.geometry_config.label_width
                + second * self.geometry_config.pixels_per_second
            )
            major = abs(second - round(second)) < 0.001
            line_height = 15.0 if major else 8.0
            self.scene_object.addLine(
                x,
                self.geometry_config.ruler_height - line_height,
                x,
                self.geometry_config.ruler_height,
                pen,
            )
            if major:
                label = self.scene_object.addText(self._format_ruler(second))
                label.setDefaultTextColor(text_color)
                label.setPos(x + 3.0, -2.0)
            second += step

    def _draw_track(self, index: int, track: dict[str, Any]) -> None:
        y = (
            self.geometry_config.ruler_height
            + index
            * (
                self.geometry_config.track_height
                + self.geometry_config.track_gap
            )
        )
        width = self.sceneRect().width()

        background = QColor("#1c2029") if index % 2 == 0 else QColor("#181b23")
        self.scene_object.addRect(
            0.0,
            y,
            width,
            self.geometry_config.track_height,
            QPen(QColor("#2b303c")),
            background,
        )

        label = self.scene_object.addText(
            f'{self._track_icon(track.get("type", ""))} '
            f'{track.get("name", "Track")}'
        )
        label.setDefaultTextColor(QColor("#e2e5ec"))
        label.setPos(8.0, y + 18.0)

        for clip in track.get("clips", []):
            clip["_fps"] = int(self.service.data.get("fps", 30))
            clip["_track_color"] = str(track.get("color", ""))
            clip["_track_locked"] = bool(track.get("locked", False))
            item = TimelineClipItem(
                clip,
                str(track.get("type", "")),
                self.geometry_config,
            )
            item.setPos(
                self.geometry_config.label_width
                + float(clip.get("start", 0.0))
                * self.geometry_config.pixels_per_second,
                y + 6.0,
            )
            item.changed.connect(self.clip_changed.emit)
            item.selected_clip.connect(self.clip_selected.emit)
            item.duplicate_requested.connect(self.duplicate_requested.emit)
            item.split_requested.connect(self.split_requested.emit)
            item.delete_requested.connect(self.delete_requested.emit)
            self.scene_object.addItem(item)


    def _draw_transitions(self, tracks: list[dict[str, Any]]) -> None:
        """Vẽ marker transition tương tác tại điểm nối hai clip."""
        visible_track_ids = {str(track.get("id", "")) for track in tracks}
        self.transition_service.clean_orphans()
        for transition in self.transition_service.data:
            from_result = self.service.find_clip(str(transition.get("from_clip_id", "")))
            to_result = self.service.find_clip(str(transition.get("to_clip_id", "")))
            if from_result is None or to_result is None:
                continue
            from_track, _ = from_result
            if str(from_track.get("id", "")) not in visible_track_ids:
                continue
            try:
                track_index = tracks.index(from_track)
            except ValueError:
                continue
            center = self.transition_service.transition_time(transition)
            x = self.geometry_config.label_width + center * self.geometry_config.pixels_per_second
            y = (
                self.geometry_config.ruler_height
                + track_index * (self.geometry_config.track_height + self.geometry_config.track_gap)
                + self.geometry_config.track_height / 2.0
            )
            item = TimelineTransitionItem(transition, self.geometry_config)
            item.setPos(x, y)
            item.selected_transition.connect(self.transition_selected.emit)
            item.duration_changed.connect(self.transition_changed.emit)
            item.delete_requested.connect(self.transition_delete_requested.emit)
            self.scene_object.addItem(item)

    def _draw_playhead(self) -> None:
        playhead = float(self.service.data.get("playhead", 0.0))
        x = (
            self.geometry_config.label_width
            + playhead * self.geometry_config.pixels_per_second
        )
        pen = QPen(QColor("#ff4d67"), 2.0)
        line = self.scene_object.addLine(
            x,
            0.0,
            x,
            self.sceneRect().height(),
            pen,
        )
        line.setZValue(50.0)

    def _ruler_step(self) -> float:
        pixels = self.geometry_config.pixels_per_second
        if pixels >= 180:
            return 0.25
        if pixels >= 100:
            return 0.5
        if pixels >= 45:
            return 1.0
        if pixels >= 20:
            return 2.0
        return 5.0

    @staticmethod
    def _format_ruler(seconds: float) -> str:
        minutes = int(seconds // 60)
        remaining = int(seconds % 60)
        return f"{minutes:02d}:{remaining:02d}"

    @staticmethod
    def _track_icon(track_type: str) -> str:
        return {
            "video": "🎞",
            "audio": "🎵",
            "subtitle": "💬",
        }.get(track_type, "•")
