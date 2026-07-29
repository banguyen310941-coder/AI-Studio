
from __future__ import annotations
from typing import Any

class AudioMixerService:
    """Quản lý volume, pan, mute/solo và fade cho audio track/clip."""
    def __init__(self, timeline_service) -> None:
        self.timeline_service = timeline_service

    def audio_tracks(self) -> list[dict[str, Any]]:
        return [t for t in self.timeline_service.data.get("tracks", []) if t.get("type") == "audio"]

    def normalize(self) -> None:
        for track in self.audio_tracks():
            track.setdefault("volume", 1.0)
            track.setdefault("pan", 0.0)
            track.setdefault("muted", False)
            track.setdefault("solo", False)
            for clip in track.get("clips", []):
                clip.setdefault("volume", 1.0)
                clip.setdefault("fade_in", 0.0)
                clip.setdefault("fade_out", 0.0)

    def update_track(self, track_id: str, *, volume: float|None=None, pan: float|None=None,
                     muted: bool|None=None, solo: bool|None=None) -> bool:
        track=self.timeline_service.get_track(track_id)
        if not track or track.get("type")!="audio": return False
        self.timeline_service.checkpoint()
        if volume is not None: track["volume"]=max(0.0,min(2.0,float(volume)))
        if pan is not None: track["pan"]=max(-1.0,min(1.0,float(pan)))
        if muted is not None: track["muted"]=bool(muted)
        if solo is not None: track["solo"]=bool(solo)
        return True

    def update_clip_fades(self, clip_id: str, fade_in: float, fade_out: float) -> bool:
        result=self.timeline_service.find_clip(clip_id)
        if not result or result[0].get("type")!="audio": return False
        self.timeline_service.checkpoint()
        clip=result[1]; duration=max(0.1,float(clip.get("duration",0.1)))
        clip["fade_in"]=max(0.0,min(duration,float(fade_in)))
        clip["fade_out"]=max(0.0,min(duration,float(fade_out)))
        return True

    def effective_tracks(self) -> list[dict[str, Any]]:
        tracks=self.audio_tracks(); solo=any(t.get("solo",False) for t in tracks)
        return [t for t in tracks if not t.get("muted",False) and (not solo or t.get("solo",False)) and t.get("visible",True)]
