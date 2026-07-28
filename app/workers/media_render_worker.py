from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot


ProgressCallback = Callable[[int, str], None]
RenderJob = Callable[[ProgressCallback], Any]


class MediaRenderWorker(QObject):
    """
    Worker chạy tác vụ render ngoài GUI thread.

    Worker chỉ phát signal. Worker tuyệt đối không truy cập QWidget.
    """

    progress = Signal(int, str)
    completed = Signal(str)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, job: RenderJob) -> None:
        super().__init__()
        self._job = job

    def _report_progress(self, value: int, text: str) -> None:
        safe_value = max(0, min(100, int(value)))
        self.progress.emit(safe_value, str(text))

    @Slot()
    def run(self) -> None:
        try:
            result = self._job(self._report_progress)
            self.completed.emit(str(result))
        except Exception as error:
            self.failed.emit(str(error))
        finally:
            self.finished.emit()
