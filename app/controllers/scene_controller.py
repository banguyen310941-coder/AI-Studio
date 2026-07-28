from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal

from app.agents.image_agent import ImageAgent
from app.agents.voice_agent import VoiceAgent
from app.models.project_model import ProjectModel
from app.services.history_service import HistoryService
from app.video_builder import VideoBuilder
from app.widgets.scene_card import SceneCard


class SceneController(QObject):
    """
    Quản lý thao tác và tài nguyên của từng cảnh.

    Lưu ý quan trọng:
    - Không gọi QApplication.processEvents() trong các slot xử lý.
    - Việc gọi processEvents() lồng nhau có thể làm Qt/macOS phát sinh
      repaint re-entrant, dẫn đến QPainter::begin bị gọi khi paint device
      vẫn đang được một painter khác sử dụng.
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

        self.image_agent = image_agent if image_agent is not None else ImageAgent()
        self.voice_agent = voice_agent if voice_agent is not None else VoiceAgent()
        self.video_builder = video_builder if video_builder is not None else VideoBuilder()

        self.scene_cards: dict[int, SceneCard] = {}
        self._editing_enabled = True

    # =========================================================
    # DEPENDENCIES
    # =========================================================

    def set_project_model(self, project_model: ProjectModel) -> None:
        self.project_model = project_model

    def set_history_service(self, history_service: HistoryService) -> None:
        self.history_service = history_service

    def set_editing_enabled(self, enabled: bool) -> None:
        self._editing_enabled = bool(enabled)

    # =========================================================
    # SCENE CARD REGISTRY
    # =========================================================

    def register_card(self, card: SceneCard) -> None:
        existing_card = self.scene_cards.get(card.scene_number)

        if existing_card is card:
            return

        self.scene_cards[card.scene_number] = card

        card.image_requested.connect(self.generate_image)
        card.voice_requested.connect(self.generate_voice)
        card.video_requested.connect(self.generate_video)

        self.display_existing_assets(card.scene_number)

    def unregister_card(self, scene_number: int) -> None:
        self.scene_cards.pop(scene_number, None)

    def unregister_all_cards(self) -> None:
        self.scene_cards.clear()

    def rebuild_card_index(self) -> None:
        cards = list(self.scene_cards.values())
        self.scene_cards = {card.scene_number: card for card in cards}

    def find_card(self, scene_number: int) -> SceneCard | None:
        return self.scene_cards.get(scene_number)

    # =========================================================
    # SCENE EDITING
    # =========================================================

    def add_scene(
        self,
        scene_data: dict[str, Any] | None = None,
        position: int | None = None,
    ) -> int:
        if not self._editing_enabled:
            return 0

        model = self._require_project_model()
        data = deepcopy(scene_data if scene_data is not None else self.DEFAULT_SCENE)

        scene_number = model.add_scene(scene_data=data, position=position)

        self._push_history(f"Thêm Cảnh {scene_number}")
        self.scene_added.emit(scene_number)
        self.scene_focus_requested.emit(scene_number)

        return scene_number

    def duplicate_scene(self, scene_number: int) -> int:
        if not self._editing_enabled:
            return 0

        model = self._require_project_model()
        scene = model.get_scene(scene_number)

        if scene is None:
            self._emit_warning(
                "Không tìm thấy cảnh",
                f"Không tồn tại Cảnh {scene_number}.",
            )
            return 0

        duplicated_scene = deepcopy(scene)
        original_title = str(duplicated_scene.get("title", "")).strip()

        duplicated_scene["title"] = (
            f"{original_title} (bản sao)"
            if original_title
            else "Cảnh mới (bản sao)"
        )

        new_scene_number = model.add_scene(
            scene_data=duplicated_scene,
            position=scene_number + 1,
        )

        self._push_history(f"Nhân đôi Cảnh {scene_number}")
        self.scene_duplicated.emit(scene_number, new_scene_number)
        self.scene_focus_requested.emit(new_scene_number)

        return new_scene_number

    def delete_scene(self, scene_number: int) -> bool:
        if not self._editing_enabled:
            return False

        model = self._require_project_model()
        scene = model.get_scene(scene_number)

        if scene is None:
            self._emit_warning(
                "Không tìm thấy cảnh",
                f"Không tồn tại Cảnh {scene_number}.",
            )
            return False

        result = model.remove_scene(scene_number)

        if result is False:
            return False

        self._push_history(f"Xóa Cảnh {scene_number}")
        self.scene_deleted.emit(scene_number)

        remaining_count = model.get_scene_count()

        if remaining_count > 0:
            self.scene_focus_requested.emit(min(scene_number, remaining_count))

        return True

    def move_scene_up(self, scene_number: int) -> bool:
        if scene_number <= 1:
            return False

        return self.move_scene(
            from_scene_number=scene_number,
            to_scene_number=scene_number - 1,
        )

    def move_scene_down(self, scene_number: int) -> bool:
        model = self._require_project_model()

        if scene_number <= 0 or scene_number >= model.get_scene_count():
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
        if not self._editing_enabled:
            return False

        model = self._require_project_model()
        changed = model.move_scene(from_scene_number, to_scene_number)

        if not changed:
            return False

        direction = "lên" if to_scene_number < from_scene_number else "xuống"

        self._push_history(
            f"Di chuyển Cảnh {from_scene_number} {direction}"
        )
        self.scene_moved.emit(from_scene_number, to_scene_number)
        self.scene_focus_requested.emit(to_scene_number)

        return True

    def select_scene(self, scene_number: int) -> bool:
        model = self._require_project_model()

        if model.get_scene(scene_number) is None:
            return False

        self.scene_focus_requested.emit(scene_number)
        return True

    # =========================================================
    # PATHS
    # =========================================================

    def get_project_path(self) -> Path:
        return Path(self.project_path_provider())

    def get_image_path(self, scene_number: int) -> Path:
        return self.get_project_path() / "images" / f"scene_{scene_number:02d}.png"

    def get_audio_path(self, scene_number: int) -> Path:
        return self.get_project_path() / "audio" / f"scene_{scene_number:02d}.mp3"

    def get_video_path(self, scene_number: int) -> Path:
        return self.get_project_path() / "video" / f"scene_{scene_number:02d}.mp4"

    # =========================================================
    # ASSET DISPLAY
    # =========================================================

    def display_existing_assets(self, scene_number: int) -> None:
        card = self.find_card(scene_number)

        if card is None:
            return

        image_path = self.get_image_path(scene_number)
        audio_path = self.get_audio_path(scene_number)
        video_path = self.get_video_path(scene_number)

        if image_path.exists():
            card.display_image(image_path)

        if audio_path.exists():
            card.display_voice(audio_path)

        if video_path.exists():
            card.display_video(video_path)

    def refresh_scene(
        self,
        scene_number: int,
        video_path: Path | str | None = None,
    ) -> None:
        card = self.find_card(scene_number)

        if card is None:
            return

        image_path = self.get_image_path(scene_number)
        audio_path = self.get_audio_path(scene_number)
        resolved_video_path = (
            Path(video_path)
            if video_path is not None
            else self.get_video_path(scene_number)
        )

        if image_path.exists():
            card.display_image(image_path)

        if audio_path.exists():
            card.display_voice(audio_path)

        if resolved_video_path.exists():
            card.display_video(resolved_video_path)

    # =========================================================
    # IMAGE GENERATION
    # =========================================================

    def generate_image(self, scene_number: int, prompt: str) -> None:
        card = self.find_card(scene_number)

        if card is None:
            return

        clean_prompt = prompt.strip()

        if not clean_prompt:
            self._emit_warning(
                "Thiếu prompt",
                f"Cảnh {scene_number} chưa có prompt tạo ảnh.",
            )
            return

        card.set_image_loading(True)

        try:
            image_path = self.image_agent.generate(
                prompt=clean_prompt,
                output_path=self.get_image_path(scene_number),
            )
            card.display_image(Path(image_path))

        except Exception as error:
            self._emit_error("Lỗi tạo ảnh", str(error))

        finally:
            card.set_image_loading(False)

    # =========================================================
    # VOICE GENERATION
    # =========================================================

    def generate_voice(self, scene_number: int, narration: str) -> None:
        card = self.find_card(scene_number)

        if card is None:
            return

        clean_narration = narration.strip()

        if not clean_narration:
            self._emit_warning(
                "Thiếu lời đọc",
                f"Cảnh {scene_number} chưa có nội dung lời đọc.",
            )
            return

        card.set_voice_loading(True)

        try:
            audio_path = self.voice_agent.generate(
                narration=clean_narration,
                output_path=self.get_audio_path(scene_number),
            )
            card.display_voice(Path(audio_path))

        except Exception as error:
            self._emit_error("Lỗi tạo giọng đọc", str(error))

        finally:
            card.set_voice_loading(False)

    # =========================================================
    # VIDEO GENERATION
    # =========================================================

    def generate_video(self, scene_number: int) -> None:
        card = self.find_card(scene_number)

        if card is None:
            return

        image_path = self.get_image_path(scene_number)
        audio_path = self.get_audio_path(scene_number)

        if not image_path.exists():
            self._emit_warning(
                "Thiếu ảnh",
                f"Cảnh {scene_number} chưa có ảnh.",
            )
            return

        if not audio_path.exists():
            self._emit_warning(
                "Thiếu giọng đọc",
                f"Cảnh {scene_number} chưa có giọng đọc.",
            )
            return

        card.set_video_loading(True)

        try:
            video_path = self.video_builder.create_scene_video(
                image_path=image_path,
                audio_path=audio_path,
                output_path=self.get_video_path(scene_number),
            )
            card.display_video(Path(video_path))

        except Exception as error:
            self._emit_error("Lỗi tạo video cảnh", str(error))

        finally:
            card.set_video_loading(False)

    # =========================================================
    # HISTORY
    # =========================================================

    def _push_history(self, description: str) -> bool:
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

    def _require_project_model(self) -> ProjectModel:
        if self.project_model is None:
            raise RuntimeError(
                "SceneController chưa được gắn ProjectModel."
            )

        return self.project_model

    # =========================================================
    # EVENT BUS
    # =========================================================

    def _emit_warning(self, title: str, message: str) -> None:
        if (
            self.event_bus is not None
            and hasattr(self.event_bus, "scene_warning")
        ):
            self.event_bus.scene_warning.emit(title, message)
            return

        self.warning_requested.emit(title, message)

    def _emit_error(self, title: str, message: str) -> None:
        if (
            self.event_bus is not None
            and hasattr(self.event_bus, "scene_error")
        ):
            self.event_bus.scene_error.emit(title, message)
            return

        self.error_occurred.emit(title, message)
