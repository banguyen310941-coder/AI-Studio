from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class EncoderProfile:
    id: str
    name: str
    cpu_crf: int
    cpu_preset: str
    gpu_bitrate: str
    audio_bitrate: str

    def ffmpeg_args(self, codec: str) -> list[str]:
        if codec == "libx264":
            return ["-c:v", codec, "-preset", self.cpu_preset, "-crf", str(self.cpu_crf), "-c:a", "aac", "-b:a", self.audio_bitrate]
        return ["-c:v", codec, "-b:v", self.gpu_bitrate, "-maxrate", self.gpu_bitrate, "-bufsize", self.gpu_bitrate, "-c:a", "aac", "-b:a", self.audio_bitrate]


PROFILES = {
    "draft": EncoderProfile("draft", "Draft", 28, "veryfast", "4M", "128k"),
    "standard": EncoderProfile("standard", "Standard", 23, "medium", "8M", "192k"),
    "high": EncoderProfile("high", "High Quality", 19, "slow", "16M", "256k"),
    "master": EncoderProfile("master", "Master", 16, "slower", "28M", "320k"),
}


def get_profile(profile_id: str) -> EncoderProfile:
    return PROFILES.get(profile_id, PROFILES["standard"])
