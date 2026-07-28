from __future__ import annotations

from pathlib import Path
import platform
import subprocess

from PySide6.QtCore import QObject, Signal, Slot


class VoiceWorker(QObject):
    progress = Signal(int, int)
    segment_finished = Signal(int, str)
    segment_failed = Signal(int, str)
    finished = Signal()
    stopped = Signal()

    def __init__(self, segments: list[dict]) -> None:
        super().__init__()
        self.segments = segments
        self._stop_requested = False

    @Slot()
    def run(self) -> None:
        for index, segment in enumerate(self.segments):
            if self._stop_requested:
                self.stopped.emit()
                return

            self.progress.emit(index, 10)

            try:
                text = str(segment.get("text", "")).strip()
                if not text:
                    raise ValueError("Nội dung giọng đọc đang trống.")

                output_path = Path(segment["output_path"])
                output_path.parent.mkdir(parents=True, exist_ok=True)

                if platform.system() != "Darwin":
                    raise RuntimeError(
                        "Bản 4.7 hiện dùng công cụ giọng đọc tích hợp của macOS."
                    )

                command = ["say"]
                voice = str(segment.get("voice", "System Default"))
                if voice and voice != "System Default":
                    command.extend(["-v", voice])

                command.extend(
                    [
                        "-r",
                        str(int(segment.get("rate", 180))),
                        "-o",
                        str(output_path),
                        text,
                    ]
                )

                self.progress.emit(index, 35)
                subprocess.run(
                    command,
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                self.progress.emit(index, 100)
                self.segment_finished.emit(index, str(output_path))
            except Exception as error:
                self.segment_failed.emit(index, str(error))

        self.finished.emit()

    @Slot()
    def stop(self) -> None:
        self._stop_requested = True
