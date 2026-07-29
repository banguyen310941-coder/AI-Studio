from __future__ import annotations

from typing import Any

from .color_correction_service import ColorCorrectionService


class FFmpegColorCompiler:
    """Biên dịch thiết lập Color Correction thành chuỗi filter FFmpeg."""

    @staticmethod
    def compile(settings: dict[str, Any]) -> str:
        normalized = ColorCorrectionService._normalize(settings)
        if not normalized["enabled"]:
            return ""

        filters = [
            "eq="
            f"brightness={normalized['brightness']:.4f}:"
            f"contrast={normalized['contrast']:.4f}:"
            f"saturation={normalized['saturation']:.4f}:"
            f"gamma={normalized['gamma']:.4f}"
        ]

        temperature = normalized["temperature"]
        tint = normalized["tint"]
        if abs(temperature) > 0.0001 or abs(tint) > 0.0001:
            red = max(0.0, min(2.0, 1.0 + temperature * 0.18 + tint * 0.08))
            green = max(0.0, min(2.0, 1.0 - tint * 0.12))
            blue = max(0.0, min(2.0, 1.0 - temperature * 0.18 + tint * 0.08))
            filters.append(f"colorchannelmixer=rr={red:.4f}:gg={green:.4f}:bb={blue:.4f}")

        return ",".join(filters)
