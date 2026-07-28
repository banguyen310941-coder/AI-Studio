import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.logger import get_logger, log_exception


logger = get_logger(__name__)


class PipelineStateService:
    """
    Lưu và đọc trạng thái xử lý video của một dự án.

    Dữ liệu được lưu tại:

        project/output/pipeline_state.json
    """

    STATE_FILE_NAME = "pipeline_state.json"

    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"

    VALID_STATUSES = {
        STATUS_PENDING,
        STATUS_RUNNING,
        STATUS_COMPLETED,
        STATUS_FAILED,
        STATUS_CANCELLED,
    }

    def __init__(
        self,
        project_path: Path,
    ) -> None:
        self.project_path = Path(
            project_path
        )

        self.output_directory = (
            self.project_path
            / "output"
        )

        self.state_file_path = (
            self.output_directory
            / self.STATE_FILE_NAME
        )

        self.output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    def create_initial_state(
        self,
        scene_count: int,
    ) -> dict[str, Any]:
        """
        Tạo trạng thái ban đầu cho toàn bộ cảnh.
        """

        if scene_count <= 0:
            raise ValueError(
                "Số lượng cảnh phải lớn hơn 0."
            )

        scenes: dict[str, dict[str, Any]] = {}

        for scene_number in range(
            1,
            scene_count + 1,
        ):
            scenes[str(scene_number)] = {
                "status": self.STATUS_PENDING,
                "retry_count": 0,
                "error_message": "",
                "video_path": "",
                "updated_at": self.current_time(),
            }

        state = {
            "version": 1,
            "pipeline_status": self.STATUS_PENDING,
            "scene_count": scene_count,
            "final_video_path": "",
            "created_at": self.current_time(),
            "updated_at": self.current_time(),
            "scenes": scenes,
        }

        self.save_state(state)

        logger.info(
            "Đã tạo trạng thái pipeline cho %s cảnh. path=%s",
            scene_count,
            self.state_file_path,
        )

        return state

    def load_state(
        self,
    ) -> dict[str, Any] | None:
        """
        Đọc trạng thái pipeline đã lưu.

        Trả về None nếu chưa có file trạng thái.
        """

        if not self.state_file_path.exists():
            return None

        try:
            with self.state_file_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                state = json.load(file)

            if not isinstance(state, dict):
                raise ValueError(
                    "Dữ liệu trạng thái pipeline không hợp lệ."
                )

            return state

        except Exception as error:
            log_exception(
                logger,
                "Không thể đọc trạng thái pipeline.",
                error,
            )
            raise

    def save_state(
        self,
        state: dict[str, Any],
    ) -> None:
        """
        Lưu trạng thái pipeline bằng cách ghi file an toàn.
        """

        state["updated_at"] = (
            self.current_time()
        )

        temporary_path = (
            self.state_file_path
            .with_suffix(".tmp")
        )

        try:
            with temporary_path.open(
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    state,
                    file,
                    ensure_ascii=False,
                    indent=2,
                )

            temporary_path.replace(
                self.state_file_path
            )

        except Exception as error:
            log_exception(
                logger,
                "Không thể lưu trạng thái pipeline.",
                error,
            )
            raise

    def ensure_state(
        self,
        scene_count: int,
    ) -> dict[str, Any]:
        """
        Đọc trạng thái hiện tại hoặc tạo mới nếu chưa có.

        Nếu số lượng cảnh đã thay đổi, trạng thái cũ sẽ được
        thay thế bằng trạng thái mới.
        """

        state = self.load_state()

        if state is None:
            return self.create_initial_state(
                scene_count
            )

        saved_scene_count = int(
            state.get(
                "scene_count",
                0,
            )
        )

        if saved_scene_count != scene_count:
            logger.info(
                (
                    "Số lượng cảnh thay đổi từ %s thành %s. "
                    "Tạo lại trạng thái pipeline."
                ),
                saved_scene_count,
                scene_count,
            )

            return self.create_initial_state(
                scene_count
            )

        return state

    def update_pipeline_status(
        self,
        status: str,
        final_video_path: Path | str | None = None,
    ) -> dict[str, Any]:
        """
        Cập nhật trạng thái chung của pipeline.
        """

        self.validate_status(status)

        state = self.load_required_state()

        state["pipeline_status"] = status

        if final_video_path is not None:
            state["final_video_path"] = str(
                final_video_path
            )

        self.save_state(state)

        logger.info(
            "Đã cập nhật pipeline_status=%s.",
            status,
        )

        return state

    def update_scene_status(
        self,
        scene_number: int,
        status: str,
        retry_count: int | None = None,
        error_message: str = "",
        video_path: Path | str | None = None,
    ) -> dict[str, Any]:
        """
        Cập nhật trạng thái của một cảnh.
        """

        self.validate_status(status)

        if scene_number <= 0:
            raise ValueError(
                "Số thứ tự cảnh phải lớn hơn 0."
            )

        state = self.load_required_state()

        scene_key = str(
            scene_number
        )

        scenes = state.get(
            "scenes",
            {},
        )

        if scene_key not in scenes:
            raise KeyError(
                (
                    f"Không tìm thấy Cảnh "
                    f"{scene_number} trong trạng thái pipeline."
                )
            )

        scene_state = scenes[scene_key]

        scene_state["status"] = status
        scene_state["error_message"] = (
            error_message
        )
        scene_state["updated_at"] = (
            self.current_time()
        )

        if retry_count is not None:
            scene_state["retry_count"] = max(
                0,
                retry_count,
            )

        if video_path is not None:
            scene_state["video_path"] = str(
                video_path
            )

        self.save_state(state)

        logger.info(
            (
                "Đã cập nhật Cảnh %s: "
                "status=%s, retry_count=%s."
            ),
            scene_number,
            status,
            scene_state.get(
                "retry_count",
                0,
            ),
        )

        return state

    def get_scene_status(
        self,
        scene_number: int,
    ) -> str | None:
        """
        Trả về trạng thái của một cảnh.
        """

        state = self.load_state()

        if state is None:
            return None

        scene_state = (
            state
            .get("scenes", {})
            .get(str(scene_number))
        )

        if scene_state is None:
            return None

        return str(
            scene_state.get(
                "status",
                self.STATUS_PENDING,
            )
        )

    def is_scene_completed(
        self,
        scene_number: int,
    ) -> bool:
        """
        Kiểm tra cảnh đã hoàn thành hay chưa.
        """

        return (
            self.get_scene_status(
                scene_number
            )
            == self.STATUS_COMPLETED
        )

    def get_incomplete_scene_numbers(
        self,
    ) -> list[int]:
        """
        Trả về các cảnh chưa hoàn thành.
        """

        state = self.load_state()

        if state is None:
            return []

        incomplete_scenes: list[int] = []

        scenes = state.get(
            "scenes",
            {},
        )

        for scene_key, scene_state in scenes.items():
            status = scene_state.get(
                "status",
                self.STATUS_PENDING,
            )

            if status != self.STATUS_COMPLETED:
                incomplete_scenes.append(
                    int(scene_key)
                )

        return sorted(
            incomplete_scenes
        )

    def reset_running_scenes(
        self,
    ) -> dict[str, Any] | None:
        """
        Chuyển các cảnh đang ở trạng thái running về pending.

        Hàm này dùng khi ứng dụng bị đóng đột ngột.
        """

        state = self.load_state()

        if state is None:
            return None

        changed = False

        for scene_state in (
            state
            .get("scenes", {})
            .values()
        ):
            if (
                scene_state.get("status")
                == self.STATUS_RUNNING
            ):
                scene_state["status"] = (
                    self.STATUS_PENDING
                )
                scene_state["updated_at"] = (
                    self.current_time()
                )
                changed = True

        if (
            state.get("pipeline_status")
            == self.STATUS_RUNNING
        ):
            state["pipeline_status"] = (
                self.STATUS_PENDING
            )
            changed = True

        if changed:
            self.save_state(state)

            logger.info(
                (
                    "Đã chuyển các tác vụ running "
                    "về pending để tiếp tục pipeline."
                )
            )

        return state

    def clear_state(self) -> bool:
        """
        Xóa file trạng thái pipeline.
        """

        if not self.state_file_path.exists():
            return False

        self.state_file_path.unlink()

        logger.info(
            "Đã xóa trạng thái pipeline. path=%s",
            self.state_file_path,
        )

        return True

    def load_required_state(
        self,
    ) -> dict[str, Any]:
        state = self.load_state()

        if state is None:
            raise RuntimeError(
                (
                    "Pipeline chưa có file trạng thái. "
                    "Hãy gọi create_initial_state() "
                    "hoặc ensure_state() trước."
                )
            )

        return state

    def validate_status(
        self,
        status: str,
    ) -> None:
        if status not in self.VALID_STATUSES:
            raise ValueError(
                (
                    f"Trạng thái không hợp lệ: {status}. "
                    f"Các trạng thái hợp lệ: "
                    f"{sorted(self.VALID_STATUSES)}"
                )
            )

    @staticmethod
    def current_time() -> str:
        return datetime.now().isoformat(
            timespec="seconds"
        )