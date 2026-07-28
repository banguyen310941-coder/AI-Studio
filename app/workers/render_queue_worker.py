from __future__ import annotations

from pathlib import Path
import json
import time

from PySide6.QtCore import QObject, Signal, Slot


class RenderQueueWorker(QObject):
    job_progress = Signal(int, int)
    job_finished = Signal(int, str)
    job_failed = Signal(int, str)
    queue_finished = Signal()
    stopped = Signal()

    def __init__(self, jobs: list[dict], start_index: int = 0) -> None:
        super().__init__()
        self.jobs = jobs
        self.start_index = start_index
        self._stop_requested = False

    @Slot()
    def run(self) -> None:
        for index in range(self.start_index, len(self.jobs)):
            if self._stop_requested:
                self.stopped.emit()
                return

            job = self.jobs[index]
            if job.get("status") not in {"Chờ render", "Đã tạm dừng"}:
                continue

            try:
                output_path = Path(job["output_path"])
                output_path.parent.mkdir(parents=True, exist_ok=True)

                for progress in range(0, 101, 10):
                    if self._stop_requested:
                        self.stopped.emit()
                        return
                    self.job_progress.emit(index, progress)
                    time.sleep(0.12)

                # Bản 4.6 tạo manifest render ổn định.
                # Dịch vụ Veo thật sẽ được nối vào worker này ở bản tiếp theo.
                manifest_path = output_path.with_suffix(".render.json")
                manifest_path.write_text(
                    json.dumps(
                        {
                            "project": job.get("project_name", ""),
                            "scene_number": job.get("scene_number", 0),
                            "shot_number": job.get("shot_number", 0),
                            "title": job.get("title", ""),
                            "prompt": job.get("prompt", ""),
                            "output_path": str(output_path),
                            "status": "prepared",
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                self.job_finished.emit(index, str(manifest_path))
            except Exception as error:
                self.job_failed.emit(index, str(error))

        self.queue_finished.emit()

    @Slot()
    def stop(self) -> None:
        self._stop_requested = True
