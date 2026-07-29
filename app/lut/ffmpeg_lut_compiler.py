from __future__ import annotations

from pathlib import Path
from typing import Any


class FFmpegLUTCompiler:
    """Biên dịch thiết lập LUT thành filter lut3d của FFmpeg."""

    @staticmethod
    def compile(settings: dict[str, Any]) -> str:
        if not settings.get("enabled"):
            return ""
        path = Path(str(settings.get("path", ""))).expanduser()
        if not path.is_file():
            return ""
        interpolation = str(settings.get("interpolation", "tetrahedral"))
        if interpolation not in {"nearest", "trilinear", "tetrahedral"}:
            interpolation = "tetrahedral"
        escaped = str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
        return f"lut3d=file='{escaped}':interp={interpolation}"
