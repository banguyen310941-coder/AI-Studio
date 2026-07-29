from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import threading
from typing import Callable

from app.render.render_job import RenderJob, RenderJobStatus
from app.render.render_settings import RenderSettings
from app.transitions.render_executor import RenderResult, TransitionRenderExecutor

QueueChanged = Callable[[RenderJob], None]
QueueFinished = Callable[[], None]


class RenderQueueManager:
    """Hàng đợi render tuần tự, có lưu trạng thái, bỏ qua lỗi và hỗ trợ hủy."""

    def __init__(self, storage_path: str | Path = "data/render_queue.json", ffmpeg_path: str = "ffmpeg") -> None:
        self.storage_path = Path(storage_path)
        self.ffmpeg_path = ffmpeg_path
        self.jobs: list[RenderJob] = []
        self._thread: threading.Thread | None = None
        self._executor: TransitionRenderExecutor | None = None
        self._stop_requested = threading.Event()
        self._lock = threading.RLock()
        self.on_job_changed: QueueChanged | None = None
        self.on_queue_finished: QueueFinished | None = None
        self.load()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def add(self, job: RenderJob) -> RenderJob:
        with self._lock:
            self.jobs.append(job)
            self.save()
        self._notify(job)
        return job

    def remove(self, job_id: str) -> bool:
        with self._lock:
            for index, job in enumerate(self.jobs):
                if job.id == job_id and job.status != RenderJobStatus.RUNNING:
                    del self.jobs[index]
                    self.save()
                    return True
        return False

    def clear_finished(self) -> int:
        finished = {RenderJobStatus.COMPLETED, RenderJobStatus.FAILED, RenderJobStatus.CANCELLED}
        with self._lock:
            before = len(self.jobs)
            self.jobs = [job for job in self.jobs if job.status not in finished]
            count = before - len(self.jobs)
            self.save()
        return count

    def retry(self, job_id: str) -> bool:
        job = self.get(job_id)
        if job is None or job.status == RenderJobStatus.RUNNING:
            return False
        job.status = RenderJobStatus.QUEUED
        job.progress = 0.0
        job.message = "Đang chờ chạy lại"
        job.started_at = None
        job.finished_at = None
        self.save()
        self._notify(job)
        return True

    def get(self, job_id: str) -> RenderJob | None:
        return next((job for job in self.jobs if job.id == job_id), None)

    def start(self) -> bool:
        if self.is_running:
            return False
        if not any(job.status == RenderJobStatus.QUEUED for job in self.jobs):
            return False
        self._stop_requested.clear()
        self._thread = threading.Thread(target=self._run, name="render-queue", daemon=True)
        self._thread.start()
        return True

    def cancel_current(self) -> bool:
        self._stop_requested.set()
        if self._executor is not None:
            return self._executor.cancel()
        return False

    def _run(self) -> None:
        try:
            for job in list(self.jobs):
                if self._stop_requested.is_set():
                    break
                if job.status != RenderJobStatus.QUEUED:
                    continue
                self._run_job(job)
        finally:
            self._executor = None
            self._thread = None
            if self.on_queue_finished:
                self.on_queue_finished()

    def _run_job(self, job: RenderJob) -> None:
        job.status = RenderJobStatus.RUNNING
        job.progress = 0.0
        job.message = "Đang khởi động FFmpeg…"
        job.started_at = datetime.now(timezone.utc).isoformat()
        self.save()
        self._notify(job)
        executor = TransitionRenderExecutor(self.ffmpeg_path)
        self._executor = executor
        try:
            result = executor.render(
                job.to_plan(),
                job.output_path,
                progress_callback=lambda value, message: self._progress(job, value, message),
                extra_args=RenderSettings.from_dict(job.render_settings).ffmpeg_args(self.ffmpeg_path),
            )
        except Exception as exc:
            result = RenderResult(False, Path(job.output_path), -1, message=str(exc))
        if result.success:
            job.status = RenderJobStatus.COMPLETED
            job.progress = 100.0
            job.message = "Render hoàn tất"
        elif result.cancelled:
            job.status = RenderJobStatus.CANCELLED
            job.message = "Đã hủy render"
        else:
            job.status = RenderJobStatus.FAILED
            job.message = result.message or "Render thất bại"
        job.finished_at = datetime.now(timezone.utc).isoformat()
        self.save()
        self._notify(job)

    def _progress(self, job: RenderJob, value: float, message: str) -> None:
        job.progress = max(0.0, min(100.0, float(value)))
        job.message = message
        self.save()
        self._notify(job)

    def _notify(self, job: RenderJob) -> None:
        if self.on_job_changed:
            self.on_job_changed(job)

    def save(self) -> Path:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.storage_path.with_suffix(self.storage_path.suffix + ".tmp")
        temp.write_text(json.dumps([job.to_dict() for job in self.jobs], ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.storage_path)
        return self.storage_path

    def load(self) -> None:
        if not self.storage_path.exists():
            return
        try:
            data = json.loads(self.storage_path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                return
            self.jobs = [RenderJob.from_dict(item) for item in data if isinstance(item, dict)]
            for job in self.jobs:
                if job.status == RenderJobStatus.RUNNING:
                    job.status = RenderJobStatus.QUEUED
                    job.message = "Đã khôi phục sau khi ứng dụng đóng"
        except (OSError, ValueError, TypeError):
            self.jobs = []
