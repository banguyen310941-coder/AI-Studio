from __future__ import annotations

from dataclasses import dataclass
import platform
import shutil
import subprocess


@dataclass(slots=True, frozen=True)
class GPUEncoder:
    id: str
    label: str
    codec: str
    hardware: bool
    available: bool


class GPUDetector:
    """Detect FFmpeg hardware encoders without adding external dependencies."""

    CANDIDATES = (
        ("videotoolbox", "Apple VideoToolbox", "h264_videotoolbox"),
        ("nvenc", "NVIDIA NVENC", "h264_nvenc"),
        ("qsv", "Intel Quick Sync", "h264_qsv"),
        ("amf", "AMD AMF", "h264_amf"),
    )

    def __init__(self, ffmpeg_path: str = "ffmpeg") -> None:
        self.ffmpeg_path = ffmpeg_path

    def ffmpeg_available(self) -> bool:
        return shutil.which(self.ffmpeg_path) is not None

    def encoder_names(self) -> set[str]:
        if not self.ffmpeg_available():
            return set()
        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-hide_banner", "-encoders"],
                capture_output=True, text=True, timeout=8, check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return set()
        text = (result.stdout or "") + "\n" + (result.stderr or "")
        return {codec for _, _, codec in self.CANDIDATES if codec in text}

    def detect(self) -> list[GPUEncoder]:
        names = self.encoder_names()
        encoders = [GPUEncoder("cpu", "CPU · libx264", "libx264", False, True)]
        for encoder_id, label, codec in self.CANDIDATES:
            encoders.append(GPUEncoder(encoder_id, label, codec, True, codec in names))
        return encoders

    def recommended(self) -> GPUEncoder:
        detected = self.detect()
        system = platform.system().lower()
        machine = platform.machine().lower()
        preferred = ["videotoolbox"] if system == "darwin" and machine in {"arm64", "aarch64", "x86_64"} else []
        preferred += ["nvenc", "qsv", "amf"]
        by_id = {item.id: item for item in detected}
        for encoder_id in preferred:
            candidate = by_id.get(encoder_id)
            if candidate and candidate.available:
                return candidate
        return detected[0]
