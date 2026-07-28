from collections import deque
from pathlib import Path

from app.models.scene_task import (
    SceneTask,
    SceneTaskStatus,
)


class SceneTaskQueue:
    """
    Hàng đợi quản lý các SceneTask.

    Phiên bản đầu tiên xử lý tuần tự và hỗ trợ:
    - Lấy tác vụ tiếp theo.
    - Thử lại tác vụ bị lỗi.
    - Hủy các tác vụ còn chờ.
    - Theo dõi tiến độ.
    """

    def __init__(
        self,
        project_path: Path,
        scenes: list[dict],
        max_retries: int = 2,
    ) -> None:
        if not scenes:
            raise ValueError(
                "Không có cảnh để tạo hàng đợi."
            )

        if max_retries < 0:
            raise ValueError(
                "Số lần thử lại không được âm."
            )

        self.project_path = Path(
            project_path
        )
        self.max_retries = max_retries

        self.tasks: list[SceneTask] = [
            SceneTask(
                scene_number=index,
                scene_data=scene,
                project_path=self.project_path,
                max_retries=max_retries,
            )
            for index, scene in enumerate(
                scenes,
                start=1,
            )
        ]

        self._pending: deque[SceneTask] = deque(
            self.tasks
        )

    def __len__(self) -> int:
        return len(self.tasks)

    def has_pending(self) -> bool:
        return bool(self._pending)

    def next_task(self) -> SceneTask | None:
        if not self._pending:
            return None

        return self._pending.popleft()

    def retry_task(
        self,
        task: SceneTask,
    ) -> bool:
        if not task.prepare_retry():
            return False

        self._pending.append(task)
        return True

    def cancel_pending(self) -> None:
        while self._pending:
            task = self._pending.popleft()
            task.mark_cancelled()

    def completed_tasks(self) -> list[SceneTask]:
        return [
            task
            for task in self.tasks
            if task.status
            == SceneTaskStatus.COMPLETED
        ]

    def failed_tasks(self) -> list[SceneTask]:
        return [
            task
            for task in self.tasks
            if task.status
            == SceneTaskStatus.FAILED
        ]

    def cancelled_tasks(self) -> list[SceneTask]:
        return [
            task
            for task in self.tasks
            if task.status
            == SceneTaskStatus.CANCELLED
        ]

    def progress_percent(self) -> int:
        finished_count = sum(
            task.status
            in {
                SceneTaskStatus.COMPLETED,
                SceneTaskStatus.FAILED,
                SceneTaskStatus.CANCELLED,
            }
            for task in self.tasks
        )

        return int(
            finished_count
            / len(self.tasks)
            * 100
        )