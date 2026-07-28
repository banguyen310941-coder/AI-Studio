from PySide6.QtCore import QObject, Signal


class EventBus(QObject):
    """
    Trung tâm truyền sự kiện của AI Studio.

    Giao diện và các controller chỉ kết nối với EventBus,
    nhờ đó các module không cần biết trực tiếp về nhau.
    """

    # Pipeline
    pipeline_progress = Signal(int, str)
    pipeline_scene_completed = Signal(int, str)
    pipeline_completed = Signal(str)
    pipeline_failed = Signal(str)
    pipeline_running_changed = Signal(bool)
    pipeline_finished = Signal()

    # Scene
    scene_warning = Signal(str, str)
    scene_error = Signal(str, str)

    # Project / script
    scenes_generated = Signal(int)
    project_saved = Signal(str, int)


_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """
    Trả về EventBus dùng chung trong toàn bộ ứng dụng.
    """

    global _event_bus

    if _event_bus is None:
        _event_bus = EventBus()

    return _event_bus