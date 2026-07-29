from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.transitions.transition_model import TransitionModel
from app.transitions.transition_registry import TransitionRegistry
from app.transitions.xfade import XFadeCompiler


@dataclass(slots=True)
class TransitionSummary:
    count: int
    total_duration: float


class TransitionService:
    """Quản lý transition trong timeline JSON schema 2."""

    EASINGS = ("linear", "ease-in", "ease-out", "ease-in-out")

    def __init__(self, timeline_service) -> None:
        self.timeline_service = timeline_service
        self.registry = TransitionRegistry()
        self.compiler = XFadeCompiler(self.registry)
        self.ensure_document()

    @property
    def data(self) -> list[dict[str, Any]]:
        self.ensure_document()
        return self.timeline_service.data["transitions"]

    @property
    def presets(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            {
                "id": item.id,
                "name": item.name,
                "category": item.category,
                "default_duration": item.default_duration,
                "ffmpeg_name": item.ffmpeg_name,
            }
            for item in self.registry.all()
        )

    def ensure_document(self) -> None:
        document = self.timeline_service.data
        document.setdefault("transitions", [])
        document["schema_version"] = max(2, int(document.get("schema_version", 1)))

    def add(
        self,
        from_clip_id: str,
        to_clip_id: str,
        transition_type: str = "cross_dissolve",
        duration: float | None = None,
        easing: str = "ease-in-out",
    ) -> dict[str, Any]:
        from_track, from_clip = self._require_video_clip(from_clip_id)
        to_track, to_clip = self._require_video_clip(to_clip_id)
        del from_track, to_track
        preset = self.registry.require(transition_type)
        if easing not in self.EASINGS:
            easing = "ease-in-out"
        duration_value = preset.default_duration if duration is None else duration
        duration_value = self._bounded_duration(from_clip, to_clip, duration_value)

        model = TransitionModel(
            from_clip_id=from_clip_id,
            to_clip_id=to_clip_id,
            transition_type=transition_type,
            duration=duration_value,
            easing=easing,
        )
        self.timeline_service.checkpoint()
        self._remove_duplicate_pair(from_clip_id, to_clip_id)
        transition = model.to_dict()
        self.data.append(transition)
        return transition

    def add_between_adjacent(
        self,
        first_clip_id: str,
        transition_type: str = "cross_dissolve",
    ) -> dict[str, Any]:
        pair = self.adjacent_pair(first_clip_id)
        if pair is None:
            raise ValueError("Không tìm thấy clip video liền sau trên cùng track.")
        return self.add(pair[0], pair[1], transition_type)

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
        from_result = self.timeline_service.find_clip(str(transition.get("from_clip_id", "")))
        to_result = self.timeline_service.find_clip(str(transition.get("to_clip_id", "")))
        if from_result is None or to_result is None:
            return False
        _, from_clip = from_result
        _, to_clip = to_result
        self.timeline_service.checkpoint()
        if transition_type is not None:
            self.registry.require(transition_type)
            transition["type"] = transition_type
        if duration is not None:
            transition["duration"] = self._bounded_duration(from_clip, to_clip, duration)
        if easing is not None:
            transition["easing"] = easing if easing in self.EASINGS else "ease-in-out"
        if enabled is not None:
            transition["enabled"] = bool(enabled)
        return True

    def remove(self, transition_id: str) -> bool:
        if self.get(transition_id) is None:
            return False
        self.timeline_service.checkpoint()
        self.timeline_service.data["transitions"] = [
            item for item in self.data if item.get("id") != transition_id
        ]
        return True

    def get(self, transition_id: str) -> dict[str, Any] | None:
        return next((item for item in self.data if item.get("id") == transition_id), None)

    def adjacent_pair(self, clip_id: str) -> tuple[str, str] | None:
        result = self.timeline_service.find_clip(clip_id)
        if result is None:
            return None
        track, _ = result
        if track.get("type") != "video":
            return None
        clips = sorted(track.get("clips", []), key=lambda item: float(item.get("start", 0.0)))
        for index, clip in enumerate(clips[:-1]):
            if str(clip.get("id", "")) == clip_id:
                return clip_id, str(clips[index + 1].get("id", ""))
        return None

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

    def xfade_filter(self, transition_id: str) -> str:
        transition = self.get(transition_id)
        if transition is None:
            raise KeyError("Không tìm thấy transition.")
        center = self.transition_time(transition)
        duration = float(transition.get("duration", 1.0))
        return self.compiler.compile(transition, offset=max(0.0, center - duration / 2.0))

    def clean_orphans(self) -> int:
        valid_ids = {
            str(clip.get("id"))
            for track in self.timeline_service.data.get("tracks", [])
            for clip in track.get("clips", [])
        }
        kept = [
            item for item in self.data
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
        preset = self.registry.get(preset_id)
        return preset.name if preset else preset_id

    def _require_video_clip(self, clip_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        result = self.timeline_service.find_clip(clip_id)
        if result is None:
            raise KeyError("Không tìm thấy clip để tạo transition.")
        track, clip = result
        if track.get("type") != "video":
            raise ValueError("Transition chỉ áp dụng cho clip video.")
        return track, clip

    @staticmethod
    def _bounded_duration(from_clip: dict[str, Any], to_clip: dict[str, Any], value: float) -> float:
        maximum = max(
            0.1,
            min(
                10.0,
                float(from_clip.get("duration", 1.0)),
                float(to_clip.get("duration", 1.0)),
            ),
        )
        return round(max(0.1, min(maximum, float(value))), 3)

    def _remove_duplicate_pair(self, from_clip_id: str, to_clip_id: str) -> None:
        self.timeline_service.data["transitions"] = [
            item for item in self.data
            if not (
                item.get("from_clip_id") == from_clip_id
                and item.get("to_clip_id") == to_clip_id
            )
        ]
