from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from app.agents.image_agent import ImageAgent
from app.agents.voice_agent import VoiceAgent
from app.models.project_model import ProjectModel
from app.services.history_service import HistoryService
from app.video_builder import VideoBuilder
from app.widgets.scene_card import SceneCard


class SceneController(QObject):
    """
    Quản lý thao tác và tài nguyên của từng cảnh.

    Trách nhiệm:
    - Đăng ký SceneCard.
    - Kết nối các nút tạo ảnh, giọng đọc và video.
    - Hiển thị tài nguyên đã tạo.
    - Thêm cảnh.
    - Nhân đôi cảnh.
    - Xóa cảnh.
    - Di chuyển cảnh.
    - Lưu snapshot vào HistoryService.
    - Yêu cầu giao diện chọn hoặc cuộn đến cảnh.

    SceneController không trực tiếp hiển thị QMessageBox.
    """

    warning_requested = Signal(str, str)
    error_occurred = Signal(str, str)

    scene_added = Signal(int)
    scene_duplicated = Signal(int, int)
    scene_deleted = Signal(int)
    scene_moved = Signal(int, int)

    scene_focus_requested = Signal(int)

    DEFAULT_SCENE = {
        "title": "Cảnh mới",
        "visual": "",
        "narration": "",
        "screen_text": "",
        "image_prompt": "",
    }

    def __init__(
        self,
        project_path_provider: Callable[[], Path],
        parent: QObject | None = None,
        event_bus: QObject | None = None,
        project_model: ProjectModel | None = None,
        history_service: HistoryService | None = None,
        image_agent: ImageAgent | None = None,
        voice_agent: VoiceAgent | None = None,
        video_builder: VideoBuilder | None = None,
    ) -> None:
        super().__init__(parent)

        self.project_path_provider = project_path_provider
        self.event_bus = event_bus

        self.project_model = project_model
        self.history_service = history_service

        self.image_agent = (
            image_agent
            if image_agent is not None
            else ImageAgent()
        )

        self.voice_agent = (
            voice_agent
            if voice_agent is not None
            else VoiceAgent()
        )

        self.video_builder = (
            video_builder
            if video_builder is not None
            else VideoBuilder()
        )

        self.scene_cards: dict[int, SceneCard] = {}

        self._editing_enabled = True

    # =========================================================
    # DEPENDENCIES
    # =========================================================

    def set_project_model(
        self,
        project_model: ProjectModel,
    ) -> None:
        """
        Gắn ProjectModel sau khi controller đã được khởi tạo.
        """

        self.project_model = project_model

    def set_history_service(
        self,
        history_service: HistoryService,
    ) -> None:
        """
        Gắn HistoryService sau khi controller đã được khởi tạo.
        """

        self.history_service = history_service

    def set_editing_enabled(
        self,
        enabled: bool,
    ) -> None:
        """
        Cho phép hoặc khóa các thao tác chỉnh sửa danh sách cảnh.

        Dùng khi pipeline đang chạy.
        """

        self._editing_enabled = bool(enabled)

    # =========================================================
    # SCENE CARD REGISTRY
    # =========================================================

    def register_card(
        self,
        card: SceneCard,
    ) -> None:
        """
        Đăng ký SceneCard và kết nối các nút tạo tài nguyên.
        """

        existing_card = self.scene_cards.get(
            card.scene_number
        )

        if existing_card is card:
            return

        self.scene_cards[card.scene_number] = card

        card.image_requested.connect(
            self.generate_image
        )

        card.voice_requested.connect(
            self.generate_voice
        )

        card.video_requested.connect(
            self.generate_video
        )

        self.display_existing_assets(
            card.scene_number
        )

    def unregister_card(
        self,
        scene_number: int,
    ) -> None:
        """
        Gỡ một SceneCard khỏi controller.
        """

        self.scene_cards.pop(
            scene_number,
            None,
        )

    def unregister_all_cards(
        self,
    ) -> None:
        """
        Gỡ toàn bộ SceneCard.
        """

        self.scene_cards.clear()

    def rebuild_card_index(
        self,
    ) -> None:
        """
        Xây dựng lại dictionary SceneCard.

        Dùng sau khi các card được đánh lại số thứ tự.
        """

        cards = list(
            self.scene_cards.values()
        )

        self.scene_cards = {
            card.scene_number: card
            for card in cards
        }

    def find_card(
        self,
        scene_number: int,
    ) -> SceneCard | None:
        """
        Tìm SceneCard theo số thứ tự cảnh.
        """

        return self.scene_cards.get(
            scene_number
        )

    # =========================================================
    # SCENE EDITING
    # =========================================================

    def add_scene(
        self,
        scene_data: dict[str, Any] | None = None,
        position: int | None = None,
    ) -> int:
        """
        Thêm một cảnh mới.

        Trả về số thứ tự của cảnh vừa tạo.
        Trả về 0 nếu thao tác đang bị khóa.
        """

        if not self._editing_enabled:
            return 0

        model = self._require_project_model()

        data = deepcopy(
            scene_data
            if scene_data is not None
            else self.DEFAULT_SCENE
        )

        scene_number = model.add_scene(
            scene_data=data,
            position=position,
        )

        self._push_history(
            f"Thêm Cảnh {scene_number}"
        )

        self.scene_added.emit(
            scene_number
        )

        self.scene_focus_requested.emit(
            scene_number
        )

        return scene_number

    def duplicate_scene(
        self,
        scene_number: int,
    ) -> int:
        """
        Nhân đôi một cảnh.

        Cảnh mới được chèn ngay sau cảnh nguồn.
        """

        if not self._editing_enabled:
            return 0

        model = self._require_project_model()

        scene = model.get_scene(
            scene_number
        )

        if scene is None:
            self._emit_warning(
                "Không tìm thấy cảnh",
                f"Không tồn tại Cảnh {scene_number}.",
            )
            return 0

        duplicated_scene = deepcopy(
            scene
        )

        original_title = str(
            duplicated_scene.get(
                "title",
                "",
            )
        ).strip()

        if original_title:
            duplicated_scene["title"] = (
                f"{original_title} (bản sao)"
            )
        else:
            duplicated_scene["title"] = (
                "Cảnh mới (bản sao)"
            )

        new_scene_number = model.add_scene(
            scene_data=duplicated_scene,
            position=scene_number + 1,
        )

        self._push_history(
            f"Nhân đôi Cảnh {scene_number}"
        )

        self.scene_duplicated.emit(
            scene_number,
            new_scene_number,
        )

        self.scene_focus_requested.emit(
            new_scene_number
        )

        return new_scene_number

    def delete_scene(
        self,
        scene_number: int,
    ) -> bool:
        """
        Xóa một cảnh.

        Việc hỏi xác nhận người dùng sẽ do ProjectPage xử lý.
        """

        if not self._editing_enabled:
            return False

        model = self._require_project_model()

        scene = model.get_scene(
            scene_number
        )

        if scene is None:
            self._emit_warning(
                "Không tìm thấy cảnh",
                f"Không tồn tại Cảnh {scene_number}.",
            )
            return False

        result = model.remove_scene(
            scene_number
        )

        if result is False:
            return False

        self._push_history(
            f"Xóa Cảnh {scene_number}"
        )

        self.scene_deleted.emit(
            scene_number
        )

        remaining_count = (
            model.get_scene_count()
        )

        if remaining_count > 0:
            target_scene = min(
                scene_number,
                remaining_count,
            )

            self.scene_focus_requested.emit(
                target_scene
            )

        return True

    def move_scene_up(
        self,
        scene_number: int,
    ) -> bool:
        """
        Di chuyển cảnh lên một vị trí.
        """

        if scene_number <= 1:
            return False

        return self.move_scene(
            from_scene_number=scene_number,
            to_scene_number=scene_number - 1,
        )

    def move_scene_down(
        self,
        scene_number: int,
    ) -> bool:
        """
        Di chuyển cảnh xuống một vị trí.
        """

        model = self._require_project_model()

        if (
            scene_number <= 0
            or scene_number
            >= model.get_scene_count()
        ):
            return False

        return self.move_scene(
            from_scene_number=scene_number,
            to_scene_number=scene_number + 1,
        )

    def move_scene(
        self,
        from_scene_number: int,
        to_scene_number: int,
    ) -> bool:
        """
        Di chuyển cảnh từ vị trí này sang vị trí khác.
        """

        if not self._editing_enabled:
            return False

        model = self._require_project_model()

        changed = model.move_scene(
            from_scene_number,
            to_scene_number,
        )

        if not changed:
            return False

        direction = (
            "lên"
            if to_scene_number
            < from_scene_number
            else "xuống"
        )

        self._push_history(
            (
                f"Di chuyển Cảnh "
                f"{from_scene_number} {direction}"
            )
        )

        self.scene_moved.emit(
            from_scene_number,
            to_scene_number,
        )

        self.scene_focus_requested.emit(
            to_scene_number
        )

        return True

    def select_scene(
        self,
        scene_number: int,
    ) -> bool:
        """
        Yêu cầu giao diện chọn và cuộn đến một cảnh.
        """

        model = self._require_project_model()

        scene = model.get_scene(
            scene_number
        )

        if scene is None:
            return False

        self.scene_focus_requested.emit(
            scene_number
        )

        return True

    # =========================================================
    # PATHS
    # =========================================================

    def get_project_path(
        self,
    ) -> Path:
        """
        Trả về thư mục dự án hiện tại.
        """

        return Path(
            self.project_path_provider()
        )

    def get_image_path(
        self,
        scene_number: int,
    ) -> Path:
        """
        Trả về đường dẫn ảnh của cảnh.
        """

        return (
            self.get_project_path()
            / "images"
            / f"scene_{scene_number:02d}.png"
        )

    def get_audio_path(
        self,
        scene_number: int,
    ) -> Path:
        """
        Trả về đường dẫn âm thanh của cảnh.
        """

        return (
            self.get_project_path()
            / "audio"
            / f"scene_{scene_number:02d}.mp3"
        )

    def get_video_path(
        self,
        scene_number: int,
    ) -> Path:
        """
        Trả về đường dẫn video của cảnh.
        """

        return (
            self.get_project_path()
            / "video"
            / f"scene_{scene_number:02d}.mp4"
        )

    # =========================================================
    # ASSET DISPLAY
    # =========================================================

    def display_existing_assets(
        self,
        scene_number: int,
    ) -> None:
        """
        Hiển thị các tài nguyên đã tồn tại của một cảnh.
        """

        card = self.find_card(
            scene_number
        )

        if card is None:
            return

        image_path = self.get_image_path(
            scene_number
        )

        audio_path = self.get_audio_path(
            scene_number
        )

        video_path = self.get_video_path(
            scene_number
        )

        if image_path.exists():
            card.display_image(
                image_path
            )

        if audio_path.exists():
            card.display_voice(
                audio_path
            )

        if video_path.exists():
            card.display_video(
                video_path
            )

    def refresh_scene(
        self,
        scene_number: int,
        video_path: Path | str | None = None,
    ) -> None:
        """
        Làm mới ảnh, giọng đọc và video hiển thị trên SceneCard.
        """

        card = self.find_card(
            scene_number
        )

        if card is None:
            return

        image_path = self.get_image_path(
            scene_number
        )

        audio_path = self.get_audio_path(
            scene_number
        )

        resolved_video_path = (
            Path(video_path)
            if video_path is not None
            else self.get_video_path(
                scene_number
            )
        )

        if image_path.exists():
            card.display_image(
                image_path
            )

        if audio_path.exists():
            card.display_voice(
                audio_path
            )

        if resolved_video_path.exists():
            card.display_video(
                resolved_video_path
            )

    # =========================================================
    # IMAGE GENERATION
    # =========================================================

    def generate_image(
        self,
        scene_number: int,
        prompt: str,
    ) -> None:
        """
        Tạo ảnh cho một cảnh.
        """

        card = self.find_card(
            scene_number
        )

        if card is None:
            return

        clean_prompt = prompt.strip()

        if not clean_prompt:
            self._emit_warning(
                "Thiếu prompt",
                (
                    f"Cảnh {scene_number} "
                    "chưa có prompt tạo ảnh."
                ),
            )
            return

        card.set_image_loading(
            True
        )

        QApplication.processEvents()

        try:
            image_path = (
                self.image_agent.generate(
                    prompt=clean_prompt,
                    output_path=self.get_image_path(
                        scene_number
                    ),
                )
            )

            card.display_image(
                Path(image_path)
            )

        except Exception as error:
            self._emit_error(
                "Lỗi tạo ảnh",
                str(error),
            )

        finally:
            card.set_image_loading(
                False
            )

    # =========================================================
    # VOICE GENERATION
    # =========================================================

    def generate_voice(
        self,
        scene_number: int,
        narration: str,
    ) -> None:
        """
        Tạo giọng đọc cho một cảnh.
        """

        card = self.find_card(
            scene_number
        )

        if card is None:
            return

        clean_narration = (
            narration.strip()
        )

        if not clean_narration:
            self._emit_warning(
                "Thiếu lời đọc",
                (
                    f"Cảnh {scene_number} "
                    "chưa có nội dung lời đọc."
                ),
            )
            return

        card.set_voice_loading(
            True
        )

        QApplication.processEvents()

        try:
            audio_path = (
                self.voice_agent.generate(
                    narration=clean_narration,
                    output_path=self.get_audio_path(
                        scene_number
                    ),
                )
            )

            card.display_voice(
                Path(audio_path)
            )

        except Exception as error:
            self._emit_error(
                "Lỗi tạo giọng đọc",
                str(error),
            )

        finally:
            card.set_voice_loading(
                False
            )

    # =========================================================
    # VIDEO GENERATION
    # =========================================================

    def generate_video(
        self,
        scene_number: int,
    ) -> None:
        """
        Tạo video cho một cảnh từ ảnh và giọng đọc.
        """

        card = self.find_card(
            scene_number
        )

        if card is None:
            return

        image_path = self.get_image_path(
            scene_number
        )

        audio_path = self.get_audio_path(
            scene_number
        )

        if not image_path.exists():
            self._emit_warning(
                "Thiếu ảnh",
                (
                    f"Cảnh {scene_number} "
                    "chưa có ảnh."
                ),
            )
            return

        if not audio_path.exists():
            self._emit_warning(
                "Thiếu giọng đọc",
                (
                    f"Cảnh {scene_number} "
                    "chưa có giọng đọc."
                ),
            )
            return

        card.set_video_loading(
            True
        )

        QApplication.processEvents()

        try:
            video_path = (
                self.video_builder
                .create_scene_video(
                    image_path=image_path,
                    audio_path=audio_path,
                    output_path=self.get_video_path(
                        scene_number
                    ),
                )
            )

            card.display_video(
                Path(video_path)
            )

        except Exception as error:
            self._emit_error(
                "Lỗi tạo video cảnh",
                str(error),
            )

        finally:
            card.set_video_loading(
                False
            )

    # =========================================================
    # HISTORY
    # =========================================================

    def _push_history(
        self,
        description: str,
    ) -> bool:
        """
        Lưu trạng thái hiện tại vào HistoryService.
        """

        if self.history_service is None:
            return False

        model = self._require_project_model()

        return self.history_service.push(
            state=model.create_snapshot(),
            description=description,
        )

    # =========================================================
    # VALIDATION
    # =========================================================

    def _require_project_model(
        self,
    ) -> ProjectModel:
        """
        Trả về ProjectModel hoặc báo lỗi nếu chưa được cấu hình.
        """

        if self.project_model is None:
            raise RuntimeError(
                "SceneController chưa được gắn ProjectModel."
            )

        return self.project_model

    # =========================================================
    # EVENT BUS
    # =========================================================

    def _emit_warning(
        self,
        title: str,
        message: str,
    ) -> None:
        """
        Phát cảnh báo qua EventBus hoặc signal nội bộ.
        """

        if (
            self.event_bus is not None
            and hasattr(
                self.event_bus,
                "scene_warning",
            )
        ):
            self.event_bus.scene_warning.emit(
                title,
                message,
            )
            return

        self.warning_requested.emit(
            title,
            message,
        )

    def _emit_error(
        self,
        title: str,
        message: str,
    ) -> None:
        """
        Phát lỗi qua EventBus hoặc signal nội bộ.
        """

        if (
            self.event_bus is not None
            and hasattr(
                self.event_bus,
                "scene_error",
            )
        ):
            self.event_bus.scene_error.emit(
                title,
                message,
            )
            return

        self.error_occurred.emit(
            title,
            message,
        )