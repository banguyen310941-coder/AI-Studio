from __future__ import annotations

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.services.timeline_service import TimelineService
from app.timeline_canvas import TimelineCanvas, TimelineClipItem


class TimelineCanvasSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.service = TimelineService()
        self.clip = self.service.add_clip(
            "video-1",
            "",
            1.0,
            3.0,
            title="Smoke clip",
        )
        self.canvas = TimelineCanvas(self.service)
        self.canvas.resize(900, 320)
        self.canvas.show()
        self.app.processEvents()

    def tearDown(self) -> None:
        self.canvas.close()
        self.canvas.deleteLater()
        self.app.processEvents()

    def _clip_item(self) -> TimelineClipItem:
        for item in self.canvas.scene_object.items():
            if isinstance(item, TimelineClipItem):
                return item
        self.fail("TimelineClipItem was not created")

    def test_hover_and_release_can_queue_scene_refresh(self) -> None:
        item = self._clip_item()
        changed: list[tuple[str, float, float]] = []
        uncaught: list[BaseException] = []
        original_excepthook = sys.excepthook

        def capture_exception(exc_type, exc_value, traceback) -> None:
            del exc_type, traceback
            uncaught.append(exc_value)

        def rebuild_scene(clip_id: str, start: float, duration: float) -> None:
            changed.append((clip_id, start, duration))
            self.service.move_resize_clip(clip_id, start, duration)
            self.canvas.refresh()

        sys.excepthook = capture_exception
        self.canvas.clip_changed.connect(rebuild_scene)
        try:
            center_scene = item.mapToScene(item.boundingRect().center())
            center = self.canvas.mapFromScene(center_scene)

            handle_scene = item.mapToScene(
                item.boundingRect().topRight()
                - self.canvas.transform().inverted()[0].map(QPoint(4, -10))
            )
            # Hover over the clip first: this exercises QGraphicsSceneHoverEvent.pos().
            QTest.mouseMove(self.canvas.viewport(), center)
            self.app.processEvents()

            # Press/release exercises QGraphicsSceneMouseEvent.pos() and then queues
            # the refresh that clears/rebuilds the scene.
            QTest.mousePress(
                self.canvas.viewport(),
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
                center,
            )
            QTest.mouseMove(self.canvas.viewport(), center + QPoint(24, 0))
            QTest.mouseRelease(
                self.canvas.viewport(),
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
                center + QPoint(24, 0),
            )
            self.app.processEvents()
            self.app.processEvents()
        finally:
            sys.excepthook = original_excepthook

        self.assertEqual(uncaught, [])
        self.assertTrue(changed, "clip_changed was not delivered")
        self.assertEqual(changed[-1][0], self.clip["id"])
        self.assertTrue(
            any(isinstance(scene_item, TimelineClipItem) for scene_item in self.canvas.scene_object.items()),
            "scene refresh did not rebuild clip items",
        )


if __name__ == "__main__":
    unittest.main()
