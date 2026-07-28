from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any


TRANSITION_PRESETS: tuple[dict[str, Any], ...] = (
    {"id": "cross_dissolve", "name": "Cross Dissolve", "category": "Cơ bản", "default_duration": 1.0},
    {"id": "fade", "name": "Fade", "category": "Cơ bản", "default_duration": 0.8},
    {"id": "dip_to_black", "name": "Dip to Black", "category": "Cơ bản", "default_duration": 0.8},
    {"id": "wipe_left", "name": "Wipe Left", "category": "Wipe", "default_duration": 0.7},
    {"id": "wipe_right", "name": "Wipe Right", "category": "Wipe", "default_duration": 0.7},
    {"id": "slide_left", "name": "Slide Left", "category": "Slide", "default_duration": 0.7},
    {"id": "slide_right", "name": "Slide Right", "category": "Slide", "default_duration": 0.7},
    {"id": "zoom", "name": "Zoom", "category": "Chuyển động", "default_duration": 0.6},
    {"id": "blur", "name": "Blur", "category": "Hiệu ứng", "default_duration": 0.8},
)


@dataclass(slots=True)
class TransitionSummary:
    count: int
    total_duration: float


class TransitionService:
    """Quản lý transition nằm trong document của TimelineService.

    Transition được lưu trực tiếp trong timeline JSON để không làm thay đổi
    quy trình save/load hiện có.
    """

    EASINGS = ("linear", "ease-in", "ease-out", "ease-in-out")

    def __init__(self, timeline_service) -> None:
        self.timeline_service = timeline_service
        self.ensure_document()

    @property
    def data(self) -> list[dict[str, Any]]:
        self.ensure_document()
        return self.timeline_service.data["transitions"]

    @property
    def presets(self) -> tuple[dict[str, Any], ...]:
        return TRANSITION_PRESETS

    def ensure_document(self) -> None:
        document = self.timeline_service.data
        document.setdefault("transitions", [])
        document["schema_version"] = max(2, int(document.get("schema_version", 1)))

    def add(
        self,
        from_clip_id: str,
        to_clip_id: str,
        transition_type: str = "cross_dissolve",
        duration: float = 1.0,
        easing: str = "ease-in-out",
    ) -> dict[str, Any]:
        self.ensure_document()
        if from_clip_id == to_clip_id:
            raise ValueError("Hai clip của transition phải khác nhau.")
        from_result = self.timeline_service.find_clip(from_clip_id)
        to_result = self.timeline_service.find_clip(to_clip_id)
        if from_result is None or to_result is None:
            raise KeyError("Không tìm thấy clip để tạo transition.")

        from_track, from_clip = from_result
        to_track, to_clip = to_result
        if from_track.get("type") != "video" or to_track.get("type") != "video":
            raise ValueError("Transition chỉ áp dụng cho clip video.")

        available = {preset["id"] for preset in TRANSITION_PRESETS}
        if transition_type not in available:
            raise ValueError(f"Transition không được hỗ trợ: {transition_type}")
        if easing not in self.EASINGS:
            easing = "ease-in-out"

        self.timeline_service.checkpoint()
        transition = {
            "id": str(uuid.uuid4()),
            "type": transition_type,
            "from_clip_id": from_clip_id,
            "to_clip_id": to_clip_id,
            "duration": round(max(0.1, min(10.0, float(duration))), 3),
            "easing": easing,
            "enabled": True,
        }
        self._remove_duplicate_pair(from_clip_id, to_clip_id)
        self.data.append(transition)
        return transition

    def update(
        self,
        transition_id: str,
        *,
        transition_type: str | None = None,
        duration: float | None = None,
        easing: str | None = None,
        enabled: bool | None = None,
    ) -> bool:
        transition = self.get(transition_id)
        if transition is None:
            return False
        self.timeline_service.checkpoint()
        if transition_type is not None:
            available = {preset["id"] for preset in TRANSITION_PRESETS}
            if transition_type not in available:
                raise ValueError(f"Transition không được hỗ trợ: {transition_type}")
            transition["type"] = transition_type
        if duration is not None:
            transition["duration"] = round(max(0.1, min(10.0, float(duration))), 3)
        if easing is not None:
            transition["easing"] = easing if easing in self.EASINGS else "ease-in-out"
        if enabled is not None:
            transition["enabled"] = bool(enabled)
        return True

    def remove(self, transition_id: str) -> bool:
        self.ensure_document()
        before = len(self.data)
        if not any(item.get("id") == transition_id for item in self.data):
            return False
        self.timeline_service.checkpoint()
        self.timeline_service.data["transitions"] = [
            item for item in self.data if item.get("id") != transition_id
        ]
        return len(self.timeline_service.data["transitions"]) != before

    def get(self, transition_id: str) -> dict[str, Any] | None:
        return next((item for item in self.data if item.get("id") == transition_id), None)

    def transition_time(self, transition: dict[str, Any]) -> float:
        from_result = self.timeline_service.find_clip(str(transition.get("from_clip_id", "")))
        to_result = self.timeline_service.find_clip(str(transition.get("to_clip_id", "")))
        if from_result is None or to_result is None:
            return 0.0
        _, from_clip = from_result
        _, to_clip = to_result
        from_end = float(from_clip.get("start", 0.0)) + float(from_clip.get("duration", 0.0))
        to_start = float(to_clip.get("start", 0.0))
        return max(0.0, (from_end + to_start) / 2.0)

    def clean_orphans(self) -> int:
        self.ensure_document()
        valid_ids = {
            str(clip.get("id"))
            for track in self.timeline_service.data.get("tracks", [])
            for clip in track.get("clips", [])
        }
        kept = [
            item
            for item in self.data
            if item.get("from_clip_id") in valid_ids and item.get("to_clip_id") in valid_ids
        ]
        removed = len(self.data) - len(kept)
        if removed:
            self.timeline_service.data["transitions"] = kept
        return removed

    def summary(self) -> TransitionSummary:
        enabled = [item for item in self.data if item.get("enabled", True)]
        return TransitionSummary(
            count=len(enabled),
            total_duration=round(sum(float(item.get("duration", 0.0)) for item in enabled), 3),
        )

    def preset_name(self, preset_id: str) -> str:
        for preset in TRANSITION_PRESETS:
            if preset["id"] == preset_id:
                return str(preset["name"])
        return preset_id

    def _remove_duplicate_pair(self, from_clip_id: str, to_clip_id: str) -> None:
        self.timeline_service.data["transitions"] = [
            item
            for item in self.data
            if not (
                item.get("from_clip_id") == from_clip_id
                and item.get("to_clip_id") == to_clip_id
            )
        ]
