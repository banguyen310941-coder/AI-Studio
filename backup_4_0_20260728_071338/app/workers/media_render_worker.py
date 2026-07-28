from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot


class MediaRenderWorker(QObject):
    progress = Signal(int, str)
    completed = Signal(str)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, job: Callable[[Callable[[int, str], None]], Path]) -> None:
        super().__init__()
        self.job = job

    @Slot()
    def run(self) -> None:
        try:
            output_path = self.job(lambda value, text: self.progress.emit(value, text))
            self.completed.emit(str(output_path))
        except Exception as exc:  # Giao diện phải nhận được mọi lỗi từ worker.
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()
