from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class FilmWorkerSignals(QObject):
    progress = Signal(int, str)
    completed = Signal(object)
    failed = Signal(str)


class FilmWorker(QRunnable):
    def __init__(self, task: Callable[[Callable[[int, str], None]], object]) -> None:
        super().__init__()
        self.task = task
        self.signals = FilmWorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.task(lambda value, text: self.signals.progress.emit(value, text))
            self.signals.completed.emit(result)
        except Exception as exc:
            self.signals.failed.emit(str(exc))
