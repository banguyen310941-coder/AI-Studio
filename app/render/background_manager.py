from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import threading
import time
from typing import Callable

from app.render.render_cache import RenderCache
from app.render.render_job import RenderJob, RenderJobStatus
from app.render.render_settings import RenderSettings
from app.render.render_queue import RenderQueueManager
from app.render.resource_monitor import ResourceMonitor, ResourceSnapshot
from app.transitions.render_executor import RenderResult, TransitionRenderExecutor

ResourceChanged = Callable[[ResourceSnapshot], None]


class BackgroundRenderManager(RenderQueueManager):
    """Concurrent render queue with pause/resume, resource guard and persistent cache."""

    def __init__(
        self,
        storage_path: str | Path = "data/render_queue.json",
        ffmpeg_path: str = "ffmpeg",
        max_workers: int = 2,
        cache_path: str | Path = "data/render_cache.json",
    ) -> None:
        super().__init__(storage_path, ffmpeg_path)
        self.max_workers = max(1, min(4, int(max_workers)))
        self.cache = RenderCache(cache_path)
        self.resource_monitor = ResourceMonitor()
        self.on_resource_changed: ResourceChanged | None = None
        self._pool: ThreadPoolExecutor | None = None
        self._dispatcher: threading.Thread | None = None
        self._futures: dict[Future[None], str] = {}
        self._executors: dict[str, TransitionRenderExecutor] = {}
        self._pause_event = threading.Event()
        self._pause_event.set()
        self._stop_all = threading.Event()

    @property
    def is_running(self) -> bool:
        return self._dispatcher is not None and self._dispatcher.is_alive()

    @property
    def running_count(self) -> int:
        return sum(job.status == RenderJobStatus.RUNNING for job in self.jobs)

    @property
    def is_paused(self) -> bool:
        return not self._pause_event.is_set()

    def set_max_workers(self, value: int) -> None:
        if self.is_running:
            raise RuntimeError("Không thể đổi số worker khi hàng đợi đang chạy")
        self.max_workers = max(1, min(4, int(value)))

    def start(self) -> bool:
        if self.is_running:
            return False
        if not any(job.status == RenderJobStatus.QUEUED for job in self.jobs):
            return False
        self._stop_all.clear()
        self._pause_event.set()
        self._dispatcher = threading.Thread(target=self._dispatch, name="background-render-dispatcher", daemon=True)
        self._dispatcher.start()
        return True

    def pause(self) -> bool:
        if not self.is_running:
            return False
        self._pause_event.clear()
        return True

    def resume(self) -> bool:
        if not self.is_running:
            return False
        self._pause_event.set()
        return True

    def cancel_current(self) -> bool:
        cancelled = False
        for executor in list(self._executors.values()):
            cancelled = executor.cancel() or cancelled
        return cancelled

    def stop_all(self) -> None:
        self._stop_all.set()
        self._pause_event.set()
        self.cancel_current()

    def _dispatch(self) -> None:
        self._pool = ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="render-worker")
        try:
            while not self._stop_all.is_set():
                self._pause_event.wait()
                snapshot = self.resource_monitor.snapshot(Path(self.storage_path).parent)
                if self.on_resource_changed:
                    self.on_resource_changed(snapshot)
                if snapshot.overloaded:
                    time.sleep(1.0)
                    continue
                self._collect_finished()
                free_slots = self.max_workers - len(self._futures)
                queued = [job for job in self.jobs if job.status == RenderJobStatus.QUEUED]
                for job in queued[:max(0, free_slots)]:
                    future = self._pool.submit(self._run_background_job, job)
                    self._futures[future] = job.id
                if not self._futures and not any(job.status == RenderJobStatus.QUEUED for job in self.jobs):
                    break
                time.sleep(0.15)
            while self._futures:
                self._collect_finished()
                time.sleep(0.1)
        finally:
            if self._pool:
                self._pool.shutdown(wait=False, cancel_futures=True)
            self._pool = None
            self._futures.clear()
            self._dispatcher = None
            if self.on_queue_finished:
                self.on_queue_finished()

    def _collect_finished(self) -> None:
        for future in list(self._futures):
            if future.done():
                try:
                    future.result()
                except Exception:
                    pass
                self._futures.pop(future, None)

    def _run_background_job(self, job: RenderJob) -> None:
        cached = self.cache.lookup(job.plan_data, job.output_path)
        if cached:
            job.status = RenderJobStatus.COMPLETED
            job.progress = 100.0
            job.message = "Dùng kết quả Smart Render Cache"
            job.finished_at = datetime.now(timezone.utc).isoformat()
            self.save()
            self._notify(job)
            return
        job.status = RenderJobStatus.RUNNING
        job.progress = 0.0
        job.message = "Background Worker đang khởi động…"
        job.started_at = datetime.now(timezone.utc).isoformat()
        self.save()
        self._notify(job)
        executor = TransitionRenderExecutor(self.ffmpeg_path)
        self._executors[job.id] = executor
        try:
            result = executor.render(
                job.to_plan(),
                job.output_path,
                progress_callback=lambda value, message: self._progress(job, value, message),
                extra_args=RenderSettings.from_dict(job.render_settings).ffmpeg_args(self.ffmpeg_path),
            )
        except Exception as exc:
            result = RenderResult(False, Path(job.output_path), -1, message=str(exc))
        finally:
            self._executors.pop(job.id, None)
        if result.success:
            job.status = RenderJobStatus.COMPLETED
            job.progress = 100.0
            job.message = "Background render hoàn tất"
            self.cache.remember(job.plan_data, job.output_path)
        elif result.cancelled:
            job.status = RenderJobStatus.CANCELLED
            job.message = "Đã hủy background render"
        else:
            job.status = RenderJobStatus.FAILED
            job.message = result.message or "Background render thất bại"
        job.finished_at = datetime.now(timezone.utc).isoformat()
        self.save()
        self._notify(job)
