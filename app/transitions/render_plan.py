from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import shlex
from typing import Any

from app.transitions.transition_registry import TransitionRegistry


@dataclass(slots=True)
class RenderClip:
    clip_id: str
    source: str
    start: float
    duration: float
    has_audio: bool = True


@dataclass(slots=True)
class RenderPlan:
    clips: list[RenderClip]
    transitions: list[dict[str, Any]]
    filter_complex: str
    output_label: str
    audio_filter_complex: str = ""
    audio_output_label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "clips": [asdict(item) for item in self.clips],
            "transitions": self.transitions,
            "filter_complex": self.filter_complex,
            "output_label": self.output_label,
            "audio_filter_complex": self.audio_filter_complex,
            "audio_output_label": self.audio_output_label,
        }

    @property
    def estimated_duration(self) -> float:
        total = sum(max(0.0, clip.duration) for clip in self.clips)
        overlap = sum(max(0.0, float(item.get("duration", 0.0))) for item in self.transitions)
        return max(0.001, total - overlap)

    def ffmpeg_args(
        self,
        output_path: str | Path = "output/transition_render.mp4",
        *,
        ffmpeg_path: str = "ffmpeg",
    ) -> list[str]:
        args: list[str] = [ffmpeg_path, "-y"]
        for clip in self.clips:
            args.extend(["-i", clip.source])
        combined = self.filter_complex
        if self.audio_filter_complex:
            combined = f"{combined};{self.audio_filter_complex}"
        args.extend(["-filter_complex", combined, "-map", self.output_label])
        if self.audio_output_label:
            args.extend(["-map", self.audio_output_label])
        else:
            args.append("-an")
        args.extend([
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p",
        ])
        if self.audio_output_label:
            args.extend(["-c:a", "aac", "-b:a", "192k"])
        args.extend(["-movflags", "+faststart", str(output_path)])
        return args

    def ffmpeg_command(self, output_path: str = "output/transition_render.mp4") -> str:
        return " ".join(shlex.quote(str(item)) for item in self.ffmpeg_args(output_path))

    def save(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return target


class TransitionRenderPlanner:
    """Biên dịch một video track tuyến tính thành kế hoạch FFmpeg xfade/acrossfade."""

    SOURCE_KEYS = ("source", "source_path", "path", "file_path", "media_path")

    def __init__(self, timeline_service, registry: TransitionRegistry | None = None) -> None:
        self.timeline_service = timeline_service
        self.registry = registry or TransitionRegistry()

    def build(self, *, track_id: str | None = None, include_audio: bool = True) -> RenderPlan:
        track = self._select_track(track_id)
        raw_clips = [clip for clip in track.get("clips", []) if clip.get("enabled", True)]
        raw_clips.sort(key=lambda item: float(item.get("start", 0.0)))
        if not raw_clips:
            raise ValueError("Track video không có clip để render.")

        clips = [self._render_clip(item) for item in raw_clips]
        transitions = self._transitions_for_clips(raw_clips)
        video_filter, video_label = self._video_graph(clips, transitions)
        audio_filter = ""
        audio_label = ""
        if include_audio and all(item.has_audio for item in clips):
            audio_filter, audio_label = self._audio_graph(clips, transitions)
        return RenderPlan(
            clips=clips,
            transitions=transitions,
            filter_complex=video_filter,
            output_label=video_label,
            audio_filter_complex=audio_filter,
            audio_output_label=audio_label,
        )

    def _select_track(self, track_id: str | None) -> dict[str, Any]:
        tracks = self.timeline_service.data.get("tracks", [])
        for track in tracks:
            if track.get("type") != "video" or not track.get("visible", True):
                continue
            if track_id is None or str(track.get("id", "")) == track_id:
                return track
        raise ValueError("Không tìm thấy video track khả dụng.")

    def _render_clip(self, clip: dict[str, Any]) -> RenderClip:
        source = next((str(clip.get(key, "")).strip() for key in self.SOURCE_KEYS if clip.get(key)), "")
        if not source:
            source = f"MISSING_SOURCE_{clip.get('id', 'clip')}.mp4"
        return RenderClip(
            clip_id=str(clip.get("id", "")),
            source=source,
            start=max(0.0, float(clip.get("start", 0.0))),
            duration=max(0.1, float(clip.get("duration", 0.1))),
            has_audio=bool(clip.get("has_audio", True)),
        )

    def _transitions_for_clips(self, clips: list[dict[str, Any]]) -> list[dict[str, Any]]:
        enabled = [item for item in self.timeline_service.data.get("transitions", []) if item.get("enabled", True)]
        by_pair = {
            (str(item.get("from_clip_id", "")), str(item.get("to_clip_id", ""))): item
            for item in enabled
        }
        result: list[dict[str, Any]] = []
        for first, second in zip(clips, clips[1:]):
            pair = (str(first.get("id", "")), str(second.get("id", "")))
            item = dict(by_pair.get(pair, {}))
            if not item:
                item = {
                    "id": f"cut-{pair[0]}-{pair[1]}",
                    "type": "cross_dissolve",
                    "from_clip_id": pair[0],
                    "to_clip_id": pair[1],
                    "duration": 0.001,
                    "easing": "linear",
                    "enabled": True,
                    "implicit_cut": True,
                }
            preset = self.registry.require(str(item.get("type", "cross_dissolve")))
            item["ffmpeg_name"] = preset.ffmpeg_name
            item["duration"] = max(0.001, float(item.get("duration", preset.default_duration)))
            result.append(item)
        return result

    @staticmethod
    def _video_graph(clips: list[RenderClip], transitions: list[dict[str, Any]]) -> tuple[str, str]:
        parts = [
            f"[{index}:v]settb=AVTB,setpts=PTS-STARTPTS,format=yuv420p[v{index}]"
            for index in range(len(clips))
        ]
        if len(clips) == 1:
            return ";".join(parts), "[v0]"
        previous = "v0"
        elapsed = clips[0].duration
        for index, transition in enumerate(transitions, start=1):
            duration = min(float(transition["duration"]), clips[index - 1].duration, clips[index].duration)
            offset = max(0.0, elapsed - duration)
            output = f"vx{index}"
            parts.append(
                f"[{previous}][v{index}]xfade=transition={transition['ffmpeg_name']}:"
                f"duration={duration:.3f}:offset={offset:.3f}[{output}]"
            )
            elapsed = elapsed + clips[index].duration - duration
            previous = output
        return ";".join(parts), f"[{previous}]"

    @staticmethod
    def _audio_graph(clips: list[RenderClip], transitions: list[dict[str, Any]]) -> tuple[str, str]:
        parts = [f"[{index}:a]asetpts=PTS-STARTPTS[a{index}]" for index in range(len(clips))]
        if len(clips) == 1:
            return ";".join(parts), "[a0]"
        previous = "a0"
        for index, transition in enumerate(transitions, start=1):
            duration = min(float(transition["duration"]), clips[index - 1].duration, clips[index].duration)
            duration = max(0.001, duration)
            output = f"ax{index}"
            parts.append(
                f"[{previous}][a{index}]acrossfade=d={duration:.3f}:c1=tri:c2=tri[{output}]"
            )
            previous = output
        return ";".join(parts), f"[{previous}]"
