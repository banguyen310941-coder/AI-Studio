from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from PySide6.QtCore import QObject, Signal

from app.core.logger import get_logger, log_exception


logger = get_logger(__name__)


@dataclass(frozen=True)
class HistoryEntry:
    """
    Một bản ghi trong lịch sử chỉnh sửa.

    `state` là ảnh chụp dữ liệu tại một thời điểm.
    `description` mô tả thao tác đã tạo ra bản ghi.
    """

    state: dict[str, Any]
    description: str
    created_at: str


class HistoryService(QObject):
    """
    Quản lý lịch sử Undo/Redo của dữ liệu dự án.

    HistoryService chỉ quản lý dữ liệu, không trực tiếp sửa giao diện.

    Quy trình sử dụng:

        history.initialize(initial_state)

        history.push(
            new_state,
            "Sửa nội dung Cảnh 1",
        )

        previous_state = history.undo()

        next_state = history.redo()

    Mỗi trạng thái được deepcopy để tránh dữ liệu bên ngoài
    vô tình làm thay đổi lịch sử đã lưu.
    """

    history_changed = Signal(bool, bool)
    state_restored = Signal(dict)
    error_occurred = Signal(str, str)

    DEFAULT_MAX_HISTORY = 100

    def __init__(
        self,
        parent: QObject | None = None,
        max_history: int = DEFAULT_MAX_HISTORY,
    ) -> None:
        super().__init__(parent)

        if max_history <= 0:
            raise ValueError(
                "Số lượng lịch sử tối đa phải lớn hơn 0."
            )

        self.max_history = max_history

        self._undo_stack: list[HistoryEntry] = []
        self._redo_stack: list[HistoryEntry] = []

        self._current_entry: HistoryEntry | None = None

        self._is_restoring = False
        self._enabled = True

        logger.info(
            "HistoryService đã được khởi tạo. max_history=%s",
            self.max_history,
        )

    def initialize(
        self,
        initial_state: dict[str, Any],
        description: str = "Trạng thái ban đầu",
    ) -> None:
        """
        Khởi tạo lịch sử bằng trạng thái ban đầu.

        Hàm này xóa toàn bộ Undo/Redo cũ.
        """

        self._validate_state(initial_state)

        self._undo_stack.clear()
        self._redo_stack.clear()

        self._current_entry = self._create_entry(
            state=initial_state,
            description=description,
        )

        logger.info(
            "Đã khởi tạo lịch sử. description=%s",
            description,
        )

        self._emit_history_changed()

    def push(
        self,
        state: dict[str, Any],
        description: str = "Thay đổi dữ liệu",
    ) -> bool:
        """
        Lưu một trạng thái mới vào lịch sử.

        Trạng thái hiện tại được chuyển vào Undo stack.
        Redo stack sẽ bị xóa khi người dùng tạo thay đổi mới.

        Trả về True nếu trạng thái được lưu.
        Trả về False nếu HistoryService đang tắt, đang restore
        hoặc trạng thái không thay đổi.
        """

        if not self._enabled:
            logger.debug(
                "Bỏ qua history push vì HistoryService đang tắt."
            )
            return False

        if self._is_restoring:
            logger.debug(
                "Bỏ qua history push trong lúc khôi phục trạng thái."
            )
            return False

        self._validate_state(state)

        if self._current_entry is None:
            self.initialize(
                initial_state=state,
                description=description,
            )
            return True

        if self._states_equal(
            self._current_entry.state,
            state,
        ):
            logger.debug(
                "Bỏ qua history push vì dữ liệu không thay đổi."
            )
            return False

        self._undo_stack.append(
            self._copy_entry(
                self._current_entry
            )
        )

        self._trim_undo_stack()

        self._current_entry = self._create_entry(
            state=state,
            description=description,
        )

        self._redo_stack.clear()

        logger.info(
            (
                "Đã lưu lịch sử. description=%s, "
                "undo_count=%s"
            ),
            description,
            len(self._undo_stack),
        )

        self._emit_history_changed()

        return True

    def undo(self) -> dict[str, Any] | None:
        """
        Quay lại trạng thái trước đó.

        Trả về bản sao trạng thái đã khôi phục.
        Trả về None nếu không thể Undo.
        """

        if not self.can_undo():
            return None

        if self._current_entry is None:
            return None

        try:
            self._is_restoring = True

            self._redo_stack.append(
                self._copy_entry(
                    self._current_entry
                )
            )

            restored_entry = (
                self._undo_stack.pop()
            )

            self._current_entry = (
                self._copy_entry(
                    restored_entry
                )
            )

            restored_state = deepcopy(
                restored_entry.state
            )

            logger.info(
                (
                    "Undo: %s. "
                    "undo_count=%s, redo_count=%s"
                ),
                restored_entry.description,
                len(self._undo_stack),
                len(self._redo_stack),
            )

            self.state_restored.emit(
                deepcopy(restored_state)
            )

            self._emit_history_changed()

            return restored_state

        except Exception as error:
            log_exception(
                logger,
                "Không thể thực hiện Undo.",
                error,
            )

            self.error_occurred.emit(
                "Lỗi Undo",
                str(error),
            )

            return None

        finally:
            self._is_restoring = False

    def redo(self) -> dict[str, Any] | None:
        """
        Tiến tới trạng thái vừa Undo.

        Trả về bản sao trạng thái đã khôi phục.
        Trả về None nếu không thể Redo.
        """

        if not self.can_redo():
            return None

        if self._current_entry is None:
            return None

        try:
            self._is_restoring = True

            self._undo_stack.append(
                self._copy_entry(
                    self._current_entry
                )
            )

            self._trim_undo_stack()

            restored_entry = (
                self._redo_stack.pop()
            )

            self._current_entry = (
                self._copy_entry(
                    restored_entry
                )
            )

            restored_state = deepcopy(
                restored_entry.state
            )

            logger.info(
                (
                    "Redo: %s. "
                    "undo_count=%s, redo_count=%s"
                ),
                restored_entry.description,
                len(self._undo_stack),
                len(self._redo_stack),
            )

            self.state_restored.emit(
                deepcopy(restored_state)
            )

            self._emit_history_changed()

            return restored_state

        except Exception as error:
            log_exception(
                logger,
                "Không thể thực hiện Redo.",
                error,
            )

            self.error_occurred.emit(
                "Lỗi Redo",
                str(error),
            )

            return None

        finally:
            self._is_restoring = False

    def can_undo(self) -> bool:
        """
        Kiểm tra có thể Undo hay không.
        """

        return (
            self._enabled
            and not self._is_restoring
            and bool(self._undo_stack)
        )

    def can_redo(self) -> bool:
        """
        Kiểm tra có thể Redo hay không.
        """

        return (
            self._enabled
            and not self._is_restoring
            and bool(self._redo_stack)
        )

    def get_current_state(
        self,
    ) -> dict[str, Any] | None:
        """
        Trả về bản sao trạng thái hiện tại.
        """

        if self._current_entry is None:
            return None

        return deepcopy(
            self._current_entry.state
        )

    def get_current_description(
        self,
    ) -> str:
        """
        Trả về mô tả trạng thái hiện tại.
        """

        if self._current_entry is None:
            return ""

        return self._current_entry.description

    def get_undo_description(
        self,
    ) -> str:
        """
        Trả về mô tả thao tác Undo tiếp theo.
        """

        if not self._undo_stack:
            return ""

        return self._undo_stack[-1].description

    def get_redo_description(
        self,
    ) -> str:
        """
        Trả về mô tả thao tác Redo tiếp theo.
        """

        if not self._redo_stack:
            return ""

        return self._redo_stack[-1].description

    def get_undo_count(self) -> int:
        return len(
            self._undo_stack
        )

    def get_redo_count(self) -> int:
        return len(
            self._redo_stack
        )

    def get_history_summary(
        self,
    ) -> list[dict[str, str]]:
        """
        Trả về danh sách tóm tắt lịch sử.

        Hàm này không trả về dữ liệu state để tránh sao chép
        lượng dữ liệu lớn không cần thiết.
        """

        result: list[dict[str, str]] = []

        for entry in self._undo_stack:
            result.append(
                {
                    "type": "undo",
                    "description": entry.description,
                    "created_at": entry.created_at,
                }
            )

        if self._current_entry is not None:
            result.append(
                {
                    "type": "current",
                    "description": (
                        self._current_entry.description
                    ),
                    "created_at": (
                        self._current_entry.created_at
                    ),
                }
            )

        for entry in reversed(
            self._redo_stack
        ):
            result.append(
                {
                    "type": "redo",
                    "description": entry.description,
                    "created_at": entry.created_at,
                }
            )

        return result

    def clear(
        self,
        keep_current_state: bool = True,
    ) -> None:
        """
        Xóa lịch sử Undo và Redo.

        Nếu keep_current_state=True, trạng thái hiện tại vẫn được giữ.
        """

        self._undo_stack.clear()
        self._redo_stack.clear()

        if not keep_current_state:
            self._current_entry = None

        logger.info(
            (
                "Đã xóa lịch sử. "
                "keep_current_state=%s"
            ),
            keep_current_state,
        )

        self._emit_history_changed()

    def replace_current_state(
        self,
        state: dict[str, Any],
        description: str = "Cập nhật trạng thái hiện tại",
    ) -> None:
        """
        Thay trạng thái hiện tại mà không tạo thêm bước Undo.

        Dùng khi:
        - Mở một dự án khác.
        - Đồng bộ dữ liệu từ file.
        - Khôi phục dữ liệu bên ngoài lịch sử.
        """

        self._validate_state(state)

        self._current_entry = self._create_entry(
            state=state,
            description=description,
        )

        logger.info(
            "Đã thay trạng thái hiện tại. description=%s",
            description,
        )

        self._emit_history_changed()

    def set_enabled(
        self,
        enabled: bool,
    ) -> None:
        """
        Bật hoặc tắt ghi lịch sử.
        """

        self._enabled = bool(
            enabled
        )

        logger.info(
            "HistoryService enabled=%s",
            self._enabled,
        )

        self._emit_history_changed()

    def is_enabled(self) -> bool:
        return self._enabled

    def is_restoring(self) -> bool:
        """
        Trả về True trong lúc Undo/Redo đang khôi phục dữ liệu.

        ProjectPage có thể dùng giá trị này để tránh tự động
        tạo snapshot mới khi đang áp dụng trạng thái cũ.
        """

        return self._is_restoring

    def _create_entry(
        self,
        state: dict[str, Any],
        description: str,
    ) -> HistoryEntry:
        cleaned_description = (
            description.strip()
            or "Thay đổi dữ liệu"
        )

        return HistoryEntry(
            state=deepcopy(state),
            description=cleaned_description,
            created_at=self._current_time(),
        )

    @staticmethod
    def _copy_entry(
        entry: HistoryEntry,
    ) -> HistoryEntry:
        return HistoryEntry(
            state=deepcopy(entry.state),
            description=entry.description,
            created_at=entry.created_at,
        )

    @staticmethod
    def _states_equal(
        first_state: dict[str, Any],
        second_state: dict[str, Any],
    ) -> bool:
        return first_state == second_state

    @staticmethod
    def _validate_state(
        state: dict[str, Any],
    ) -> None:
        if not isinstance(
            state,
            dict,
        ):
            raise TypeError(
                "Trạng thái lịch sử phải là dict."
            )

    def _trim_undo_stack(self) -> None:
        """
        Giới hạn số lượng bản ghi để tránh dùng quá nhiều RAM.
        """

        overflow = (
            len(self._undo_stack)
            - self.max_history
        )

        if overflow > 0:
            del self._undo_stack[
                :overflow
            ]

            logger.debug(
                "Đã xóa %s bản ghi lịch sử cũ.",
                overflow,
            )

    def _emit_history_changed(self) -> None:
        self.history_changed.emit(
            self.can_undo(),
            self.can_redo(),
        )

    @staticmethod
    def _current_time() -> str:
        return datetime.now().isoformat(
            timespec="seconds"
        )