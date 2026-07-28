from __future__ import annotations

import json
import uuid
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_TRACKS = [
    {"id": "video-1", "name": "Video 1", "type": "video", "color": "#4355ff", "locked": False, "muted": False, "visible": True, "clips": []},
    {"id": "audio-1", "name": "Audio 1", "type": "audio", "color": "#20a36a", "locked": False, "muted": False, "visible": True, "clips": []},
    {"id": "subtitle-1", "name": "Phụ đề", "type": "subtitle", "color": "#d88722", "locked": False, "muted": False, "visible": True, "clips": []},
]


@dataclass(slots=True)
class TimelineSummary:
    fps: int
    duration: float
    track_count: int
    clip_count: int


class TimelineService:
    """Quản lý dữ liệu timeline và lưu timeline.json."""

    def __init__(self) -> None:
        self._data = self._new_document()
        self.current_path: Path | None = None
        self._undo_stack: list[dict[str, Any]] = []
        self._redo_stack: list[dict[str, Any]] = []

    @staticmethod
    def _new_document() -> dict[str, Any]:
        return {
            "schema_version": 2,
            "fps": 30,
            "duration": 60.0,
            "zoom": 1.0,
            "playhead": 0.0,
            "tracks": deepcopy(DEFAULT_TRACKS),
            "transitions": [],
        }

    @property
    def data(self) -> dict[str, Any]:
        return self._data

    def new(self) -> dict[str, Any]:
        self._push_history()
        self._data = self._new_document()
        self.current_path = None
        return self._data

    def checkpoint(self) -> None:
        self._push_history()

    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        self._redo_stack.append(deepcopy(self._data))
        self._data = self._undo_stack.pop()
        return True

    def redo(self) -> bool:
        if not self._redo_stack:
            return False
        self._undo_stack.append(deepcopy(self._data))
        self._data = self._redo_stack.pop()
        return True

    def set_fps(self, fps: int) -> None:
        self._push_history()
        self._data["fps"] = max(1, min(120, int(fps)))

    def set_duration(self, duration: float) -> None:
        self._push_history()
        self._data["duration"] = max(1.0, float(duration))

    def set_zoom(self, zoom: float) -> None:
        self._push_history()
        self._data["zoom"] = max(0.25, min(8.0, float(zoom)))

    def set_playhead(self, seconds: float) -> None:
        duration = float(self._data.get("duration", 60.0))
        self._data["playhead"] = max(0.0, min(duration, float(seconds)))

    def clips_at(
        self,
        seconds: float,
    ) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        current = max(0.0, float(seconds))
        active: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for track in self._data["tracks"]:
            for clip in track.get("clips", []):
                start = float(clip.get("start", 0.0))
                end = start + float(clip.get("duration", 0.0))
                if clip.get("enabled", True) and start <= current < end:
                    active.append((track, clip))
        return active

    def first_active_video(self, seconds: float) -> dict[str, Any] | None:
        for track, clip in self.clips_at(seconds):
            if track.get("type") == "video":
                return clip
        return None

    def add_track(self, name: str, track_type: str) -> dict[str, Any]:
        self._push_history()
        if track_type not in {"video", "audio", "subtitle"}:
            raise ValueError(f"Loại track không hợp lệ: {track_type}")
        colors = {"video": "#4355ff", "audio": "#20a36a", "subtitle": "#d88722"}
        track = {
            "id": str(uuid.uuid4()),
            "name": name.strip() or track_type.title(),
            "type": track_type,
            "color": colors[track_type],
            "locked": False,
            "muted": False,
            "visible": True,
            "clips": [],
        }
        self._data["tracks"].append(track)
        return track

    def remove_track(self, track_id: str) -> bool:
        self._push_history()
        before = len(self._data["tracks"])
        self._data["tracks"] = [
            track for track in self._data["tracks"] if track.get("id") != track_id
        ]
        return len(self._data["tracks"]) != before

    def add_clip(
        self,
        track_id: str,
        source: str,
        start: float,
        duration: float,
        *,
        title: str = "",
        text: str = "",
        volume: float = 1.0,
    ) -> dict[str, Any]:
        self._push_history()
        track = self.get_track(track_id)
        if track is None:
            raise KeyError(f"Không tìm thấy track: {track_id}")

        clip = {
            "id": str(uuid.uuid4()),
            "title": title.strip() or Path(source).name or "Clip",
            "source": source,
            "start": max(0.0, float(start)),
            "duration": max(0.1, float(duration)),
            "text": text,
            "volume": max(0.0, min(2.0, float(volume))),
            "enabled": True,
        }
        track["clips"].append(clip)
        self._sort_track(track)
        self._expand_duration_for_clip(clip)
        return clip

    def update_clip(
        self,
        clip_id: str,
        *,
        start: float | None = None,
        duration: float | None = None,
        title: str | None = None,
        text: str | None = None,
        volume: float | None = None,
        enabled: bool | None = None,
    ) -> bool:
        self._push_history()
        result = self.find_clip(clip_id)
        if result is None:
            return False

        track, clip = result
        if start is not None:
            clip["start"] = max(0.0, float(start))
        if duration is not None:
            clip["duration"] = max(0.1, float(duration))
        if title is not None:
            clip["title"] = title.strip() or clip.get("title", "Clip")
        if text is not None:
            clip["text"] = text
        if volume is not None:
            clip["volume"] = max(0.0, min(2.0, float(volume)))
        if enabled is not None:
            clip["enabled"] = bool(enabled)

        self._sort_track(track)
        self._expand_duration_for_clip(clip)
        return True

    def remove_clip(self, clip_id: str) -> bool:
        self._push_history()
        for track in self._data["tracks"]:
            clips = track.get("clips", [])
            before = len(clips)
            track["clips"] = [clip for clip in clips if clip.get("id") != clip_id]
            if len(track["clips"]) != before:
                return True
        return False

    def duplicate_clip(self, clip_id: str) -> dict[str, Any] | None:
        self._push_history()
        result = self.find_clip(clip_id)
        if result is None:
            return None
        track, clip = result
        duplicate = deepcopy(clip)
        duplicate["id"] = str(uuid.uuid4())
        duplicate["start"] = float(clip.get("start", 0.0)) + float(
            clip.get("duration", 1.0)
        )
        duplicate["title"] = f'{clip.get("title", "Clip")} - bản sao'
        track["clips"].append(duplicate)
        self._sort_track(track)
        self._expand_duration_for_clip(duplicate)
        return duplicate


    def split_clip(
        self,
        clip_id: str,
        split_time: float,
    ) -> tuple[dict[str, Any], dict[str, Any]] | None:
        result = self.find_clip(clip_id)
        if result is None:
            return None

        track, clip = result
        start = float(clip.get("start", 0.0))
        duration = float(clip.get("duration", 0.0))
        end = start + duration
        point = float(split_time)

        if point <= start + 0.05 or point >= end - 0.05:
            return None

        self._push_history()
        left_duration = point - start
        right_duration = end - point

        clip["duration"] = round(left_duration, 6)
        right_clip = deepcopy(clip)
        right_clip["id"] = str(uuid.uuid4())
        right_clip["start"] = round(point, 6)
        right_clip["duration"] = round(right_duration, 6)
        right_clip["title"] = f'{clip.get("title", "Clip")} - B'

        clip["title"] = f'{clip.get("title", "Clip")} - A'
        track["clips"].append(right_clip)
        self._sort_track(track)
        return clip, right_clip

    def move_resize_clip(
        self,
        clip_id: str,
        start: float,
        duration: float,
    ) -> bool:
        result = self.find_clip(clip_id)
        if result is None:
            return False

        self._push_history()
        track, clip = result
        clip["start"] = max(0.0, float(start))
        clip["duration"] = max(0.1, float(duration))
        self._sort_track(track)
        self._expand_duration_for_clip(clip)
        return True

    def get_track(self, track_id: str) -> dict[str, Any] | None:
        return next(
            (
                track
                for track in self._data["tracks"]
                if track.get("id") == track_id
            ),
            None,
        )

    def find_clip(
        self, clip_id: str
    ) -> tuple[dict[str, Any], dict[str, Any]] | None:
        for track in self._data["tracks"]:
            for clip in track.get("clips", []):
                if clip.get("id") == clip_id:
                    return track, clip
        return None

    def summary(self) -> TimelineSummary:
        clip_count = sum(
            len(track.get("clips", [])) for track in self._data["tracks"]
        )
        return TimelineSummary(
            fps=int(self._data.get("fps", 30)),
            duration=float(self._data.get("duration", 60.0)),
            track_count=len(self._data["tracks"]),
            clip_count=clip_count,
        )

    def save(self, path: str | Path) -> Path:
        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.current_path = target
        return target

    def load(self, path: str | Path) -> dict[str, Any]:
        source = Path(path).expanduser()
        raw = json.loads(source.read_text(encoding="utf-8"))
        self._validate(raw)
        colors = {"video": "#4355ff", "audio": "#20a36a", "subtitle": "#d88722"}
        for track in raw.get("tracks", []):
            track_type = str(track.get("type", "video"))
            track.setdefault("color", colors.get(track_type, "#667085"))
            track.setdefault("locked", False)
            track.setdefault("muted", False)
            track.setdefault("visible", True)
        raw.setdefault("transitions", [])
        raw["schema_version"] = max(2, int(raw.get("schema_version", 1)))
        self._data = raw
        self.current_path = source
        return self._data

    def _push_history(self) -> None:
        snapshot = deepcopy(self._data)
        if self._undo_stack and self._undo_stack[-1] == snapshot:
            return
        self._undo_stack.append(snapshot)
        if len(self._undo_stack) > 100:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    @staticmethod
    def _sort_track(track: dict[str, Any]) -> None:
        track["clips"].sort(key=lambda clip: float(clip.get("start", 0.0)))

    def _expand_duration_for_clip(self, clip: dict[str, Any]) -> None:
        clip_end = float(clip.get("start", 0.0)) + float(
            clip.get("duration", 0.0)
        )
        if clip_end > float(self._data.get("duration", 60.0)):
            self._data["duration"] = round(clip_end + 5.0, 3)

    @staticmethod
    def _validate(data: Any) -> None:
        if not isinstance(data, dict):
            raise ValueError("Timeline phải là một JSON object.")
        if "transitions" in data and not isinstance(data.get("transitions"), list):
            raise ValueError("Danh sách transition không hợp lệ.")
        if not isinstance(data.get("tracks"), list):
            raise ValueError("Timeline thiếu danh sách tracks.")
        for track in data["tracks"]:
            if not isinstance(track, dict):
                raise ValueError("Track không hợp lệ.")
            if track.get("type") not in {"video", "audio", "subtitle"}:
                raise ValueError("Timeline có loại track không hợp lệ.")
            if not isinstance(track.get("clips", []), list):
                raise ValueError("Danh sách clip không hợp lệ.")
