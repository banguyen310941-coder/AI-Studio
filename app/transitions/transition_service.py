from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.transitions.transition_model import TransitionModel
from app.transitions.transition_registry import TransitionRegistry
from app.transitions.xfade import XFadeCompiler
from app.transitions.render_plan import TransitionRenderPlanner


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


    def add_all_adjacent(
        self,
        transition_type: str = "cross_dissolve",
        duration: float | None = None,
        easing: str = "ease-in-out",
    ) -> int:
        """Tạo transition cho mọi cặp clip video liền nhau trên tất cả track."""
        self.registry.require(transition_type)
        pairs: list[tuple[str, str]] = []
        for track in self.timeline_service.data.get("tracks", []):
            if track.get("type") != "video" or not track.get("visible", True):
                continue
            clips = sorted(
                [clip for clip in track.get("clips", []) if clip.get("enabled", True)],
                key=lambda item: float(item.get("start", 0.0)),
            )
            for first, second in zip(clips, clips[1:]):
                first_id = str(first.get("id", ""))
                second_id = str(second.get("id", ""))
                if first_id and second_id:
                    pairs.append((first_id, second_id))
        if not pairs:
            return 0
        self.timeline_service.checkpoint()
        created = 0
        for first_id, second_id in pairs:
            from_result = self.timeline_service.find_clip(first_id)
            to_result = self.timeline_service.find_clip(second_id)
            if from_result is None or to_result is None:
                continue
            _, from_clip = from_result
            _, to_clip = to_result
            preset = self.registry.require(transition_type)
            duration_value = preset.default_duration if duration is None else duration
            model = TransitionModel(
                from_clip_id=first_id,
                to_clip_id=second_id,
                transition_type=transition_type,
                duration=self._bounded_duration(from_clip, to_clip, duration_value),
                easing=easing if easing in self.EASINGS else "ease-in-out",
            )
            self._remove_duplicate_pair(first_id, second_id)
            self.data.append(model.to_dict())
            created += 1
        return created

    def duplicate(self, transition_id: str) -> dict[str, Any]:
        """Nhân đôi transition sang cặp clip liền sau nếu có."""
        source = self.get(transition_id)
        if source is None:
            raise KeyError("Không tìm thấy transition để nhân đôi.")
        next_pair = self.adjacent_pair(str(source.get("to_clip_id", "")))
        if next_pair is None:
            raise ValueError("Không còn cặp clip liền sau để nhân đôi transition.")
        return self.add(
            next_pair[0],
            next_pair[1],
            str(source.get("type", "cross_dissolve")),
            float(source.get("duration", 1.0)),
            str(source.get("easing", "ease-in-out")),
        )

    def set_all_enabled(self, enabled: bool) -> int:
        """Bật hoặc tắt toàn bộ transition trong một checkpoint Undo."""
        changed = [item for item in self.data if bool(item.get("enabled", True)) != bool(enabled)]
        if not changed:
            return 0
        self.timeline_service.checkpoint()
        for item in changed:
            item["enabled"] = bool(enabled)
        return len(changed)

    def validate(self) -> list[str]:
        """Trả về danh sách cảnh báo dữ liệu transition."""
        issues: list[str] = []
        seen_pairs: set[tuple[str, str]] = set()
        for index, item in enumerate(self.data, start=1):
            transition_id = str(item.get("id", ""))
            from_id = str(item.get("from_clip_id", ""))
            to_id = str(item.get("to_clip_id", ""))
            prefix = f"Transition {index}" if not transition_id else transition_id[:8]
            if self.timeline_service.find_clip(from_id) is None:
                issues.append(f"{prefix}: clip trước không tồn tại")
            if self.timeline_service.find_clip(to_id) is None:
                issues.append(f"{prefix}: clip sau không tồn tại")
            pair = (from_id, to_id)
            if pair in seen_pairs:
                issues.append(f"{prefix}: trùng cặp clip")
            seen_pairs.add(pair)
            if self.registry.get(str(item.get("type", ""))) is None:
                issues.append(f"{prefix}: preset không hợp lệ")
            if str(item.get("easing", "")) not in self.EASINGS:
                issues.append(f"{prefix}: easing không hợp lệ")
            try:
                duration = float(item.get("duration", 0.0))
            except (TypeError, ValueError):
                duration = 0.0
            if duration < 0.1 or duration > 10.0:
                issues.append(f"{prefix}: thời lượng ngoài giới hạn")
        return issues

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


    def build_render_plan(self, *, track_id: str | None = None, include_audio: bool = True):
        """Tạo RenderPlan FFmpeg cho video track và transition đang bật."""
        return TransitionRenderPlanner(self.timeline_service, self.registry).build(
            track_id=track_id, include_audio=include_audio
        )

    def export_render_plan(
        self,
        path: str,
        *,
        track_id: str | None = None,
        include_audio: bool = True,
    ) -> str:
        plan = self.build_render_plan(track_id=track_id, include_audio=include_audio)
        return str(plan.save(path))

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
