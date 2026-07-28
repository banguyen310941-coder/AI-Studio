from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from app.transitions.easing import apply_easing
from app.transitions.ffmpeg_compiler import FFmpegTransitionCompiler
from app.transitions.transition_model import SUPPORTED_EASINGS, TransitionModel
from app.transitions.transition_registry import TransitionRegistry


REGISTRY = TransitionRegistry()
TRANSITION_PRESETS: tuple[dict[str, Any], ...] = REGISTRY.as_dicts()


@dataclass(slots=True)
class TransitionSummary:
    count: int
    total_duration: float


class TransitionService:
    """Quản lý transition trong TimelineService và cung cấp dữ liệu render."""

    EASINGS = SUPPORTED_EASINGS

    def __init__(self, timeline_service) -> None:
        self.timeline_service = timeline_service
        self.registry = REGISTRY
        self.compiler = FFmpegTransitionCompiler(self.registry)
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
        normalized: list[dict[str, Any]] = []
        for item in document["transitions"]:
            try:
                normalized.append(TransitionModel.from_mapping(item).to_dict())
            except (TypeError, ValueError):
                continue
        document["transitions"] = normalized

    def add(self, from_clip_id: str, to_clip_id: str, transition_type: str = "cross_dissolve", duration: float = 1.0, easing: str = "ease-in-out") -> dict[str, Any]:
        self.registry.require(transition_type)
        self._validate_clip_pair(from_clip_id, to_clip_id)
        transition = TransitionModel(
            id=str(uuid.uuid4()),
            type=transition_type,
            from_clip_id=from_clip_id,
            to_clip_id=to_clip_id,
            duration=duration,
            easing=easing,
            enabled=True,
        )
        self.timeline_service.checkpoint()
        self._remove_duplicate_pair(from_clip_id, to_clip_id)
        value = transition.to_dict()
        self.data.append(value)
        return value

    def update(self, transition_id: str, *, transition_type: str | None = None, duration: float | None = None, easing: str | None = None, enabled: bool | None = None) -> bool:
        current = self.get(transition_id)
        if current is None:
            return False
        candidate = dict(current)
        if transition_type is not None:
            self.registry.require(transition_type)
            candidate["type"] = transition_type
        if duration is not None:
            candidate["duration"] = duration
        if easing is not None:
            candidate["easing"] = easing
        if enabled is not None:
            candidate["enabled"] = enabled
        model = TransitionModel.from_mapping(candidate)
        self.timeline_service.checkpoint()
        current.clear()
        current.update(model.to_dict())
        return True

    def remove(self, transition_id: str) -> bool:
        if self.get(transition_id) is None:
            return False
        self.timeline_service.checkpoint()
        self.timeline_service.data["transitions"] = [item for item in self.data if item.get("id") != transition_id]
        return True

    def get(self, transition_id: str) -> dict[str, Any] | None:
        return next((item for item in self.data if item.get("id") == transition_id), None)

    def model(self, transition_id: str) -> TransitionModel | None:
        item = self.get(transition_id)
        return TransitionModel.from_mapping(item) if item else None

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

    def render_offset(self, transition: dict[str, Any]) -> float:
        """Offset xfade tương đối với clip đầu tiên."""
        from_result = self.timeline_service.find_clip(str(transition.get("from_clip_id", "")))
        if from_result is None:
            return 0.0
        _, from_clip = from_result
        duration = float(transition.get("duration", 1.0))
        return max(0.0, float(from_clip.get("duration", 0.0)) - duration)

    def compile_ffmpeg_filter(self, transition_id: str) -> str:
        model = self.model(transition_id)
        if model is None:
            raise KeyError(f"Không tìm thấy transition: {transition_id}")
        return self.compiler.compile(model, offset=self.render_offset(model.to_dict())).filter_expression

    def eased_progress(self, transition_id: str, progress: float) -> float:
        model = self.model(transition_id)
        if model is None:
            raise KeyError(f"Không tìm thấy transition: {transition_id}")
        return apply_easing(model.easing, progress)

    def clean_orphans(self) -> int:
        valid_ids = {str(clip.get("id")) for track in self.timeline_service.data.get("tracks", []) for clip in track.get("clips", [])}
        kept = [item for item in self.data if item.get("from_clip_id") in valid_ids and item.get("to_clip_id") in valid_ids]
        removed = len(self.data) - len(kept)
        if removed:
            self.timeline_service.data["transitions"] = kept
        return removed

    def summary(self) -> TransitionSummary:
        enabled = [item for item in self.data if item.get("enabled", True)]
        return TransitionSummary(len(enabled), round(sum(float(item.get("duration", 0.0)) for item in enabled), 3))

    def preset_name(self, preset_id: str) -> str:
        preset = self.registry.get(preset_id)
        return preset.name if preset else preset_id

    def _validate_clip_pair(self, from_clip_id: str, to_clip_id: str) -> None:
        if from_clip_id == to_clip_id:
            raise ValueError("Hai clip của transition phải khác nhau.")
        from_result = self.timeline_service.find_clip(from_clip_id)
        to_result = self.timeline_service.find_clip(to_clip_id)
        if from_result is None or to_result is None:
            raise KeyError("Không tìm thấy clip để tạo transition.")
        from_track, _ = from_result
        to_track, _ = to_result
        if from_track.get("type") != "video" or to_track.get("type") != "video":
            raise ValueError("Transition chỉ áp dụng cho clip video.")

    def _remove_duplicate_pair(self, from_clip_id: str, to_clip_id: str) -> None:
        self.timeline_service.data["transitions"] = [item for item in self.data if not (item.get("from_clip_id") == from_clip_id and item.get("to_clip_id") == to_clip_id)]
