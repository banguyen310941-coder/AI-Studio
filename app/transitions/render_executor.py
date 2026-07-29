from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import subprocess
import threading
from typing import Callable, Sequence

from app.transitions.render_plan import RenderPlan

ProgressCallback = Callable[[float, str], None]
LogCallback = Callable[[str], None]

_TIME_PATTERN = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")
_DURATION_PATTERN = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")


@dataclass(slots=True)
class RenderResult:
    success: bool
    output_path: Path
    return_code: int
    cancelled: bool = False
    message: str = ""


class TransitionRenderExecutor:
    """Chạy FFmpeg cho RenderPlan, theo dõi tiến độ và hỗ trợ hủy."""

    def __init__(self, ffmpeg_path: str = "ffmpeg") -> None:
        self.ffmpeg_path = ffmpeg_path
        self._process: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()
        self._cancel_requested = threading.Event()

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._process is not None and self._process.poll() is None

    def available(self) -> bool:
        if Path(self.ffmpeg_path).is_file():
            return True
        return shutil.which(self.ffmpeg_path) is not None

    def cancel(self) -> bool:
        self._cancel_requested.set()
        with self._lock:
            process = self._process
        if process is None or process.poll() is not None:
            return False
        try:
            process.terminate()
        except ProcessLookupError:
            return False
        return True

    def render(
        self,
        plan: RenderPlan,
        output_path: str | Path,
        *,
        progress_callback: ProgressCallback | None = None,
        log_callback: LogCallback | None = None,
        extra_args: Sequence[str] = (),
    ) -> RenderResult:
        if self.is_running:
            raise RuntimeError("Một tác vụ render khác đang chạy.")
        if not self.available():
            raise FileNotFoundError(f"Không tìm thấy FFmpeg: {self.ffmpeg_path}")

        target = Path(output_path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        self._validate_sources(plan)
        self._cancel_requested.clear()

        args = plan.ffmpeg_args(target, ffmpeg_path=self.ffmpeg_path)
        if extra_args:
            args[-1:-1] = [str(item) for item in extra_args]

        total_duration = max(0.001, plan.estimated_duration)
        if progress_callback:
            progress_callback(0.0, "Đang khởi động FFmpeg…")

        process = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )
        with self._lock:
            self._process = process

        detected_duration = total_duration
        last_progress = 0.0
        try:
            assert process.stderr is not None
            for raw_line in process.stderr:
                line = raw_line.rstrip()
                if log_callback and line:
                    log_callback(line)
                duration_match = _DURATION_PATTERN.search(line)
                if duration_match:
                    detected_duration = max(0.001, self._seconds(duration_match.groups()))
                time_match = _TIME_PATTERN.search(line)
                if time_match:
                    current = self._seconds(time_match.groups())
                    last_progress = min(99.0, max(last_progress, current / detected_duration * 100.0))
                    if progress_callback:
                        progress_callback(last_progress, f"Đang render… {last_progress:.1f}%")
                if self._cancel_requested.is_set() and process.poll() is None:
                    process.terminate()

            return_code = process.wait()
            cancelled = self._cancel_requested.is_set()
            success = return_code == 0 and target.exists() and not cancelled
            if success:
                if progress_callback:
                    progress_callback(100.0, "Render hoàn tất")
                return RenderResult(True, target, return_code, message="Render hoàn tất.")
            if cancelled:
                target.unlink(missing_ok=True)
                return RenderResult(False, target, return_code, cancelled=True, message="Đã hủy render.")
            return RenderResult(
                False,
                target,
                return_code,
                message=f"FFmpeg kết thúc với mã lỗi {return_code}.",
            )
        finally:
            with self._lock:
                self._process = None

    @staticmethod
    def _seconds(groups: tuple[str, str, str]) -> float:
        hours, minutes, seconds = groups
        return int(hours) * 3600.0 + int(minutes) * 60.0 + float(seconds)

    @staticmethod
    def _validate_sources(plan: RenderPlan) -> None:
        missing = [clip.source for clip in plan.clips if not Path(clip.source).expanduser().exists()]
        if missing:
            sample = ", ".join(missing[:3])
            suffix = "…" if len(missing) > 3 else ""
            raise FileNotFoundError(f"Không tìm thấy file nguồn: {sample}{suffix}")
