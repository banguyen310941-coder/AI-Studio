from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


ProgressCallback = Callable[[int, str], None]


class MediaRenderError(RuntimeError):
    """Lỗi dựng media có thông báo dễ hiểu cho giao diện."""


@dataclass(slots=True)
class ImageVideoOptions:
    images: list[Path]
    output_path: Path
    seconds_per_image: float = 4.0
    resolution: str = "1920x1080"
    fps: int = 30
    motion: str = "cinematic"
    audio_path: Path | None = None


@dataclass(slots=True)
class VideoEditOptions:
    input_path: Path
    output_path: Path
    start_seconds: float = 0.0
    end_seconds: float | None = None
    speed: float = 1.0
    crop_mode: str = "keep"
    mute_original: bool = False
    subtitle_path: Path | None = None
    music_path: Path | None = None
    music_volume: float = 0.18


class MediaRenderService:
    """Các tác vụ FFmpeg dùng chung cho Image to Video và AI Video Editor."""

    def __init__(self) -> None:
        self.ffmpeg = shutil.which("ffmpeg")
        self.ffprobe = shutil.which("ffprobe")

    def ensure_tools(self) -> None:
        if not self.ffmpeg:
            raise MediaRenderError(
                "Không tìm thấy FFmpeg. Hãy cài bằng Homebrew: brew install ffmpeg"
            )
        if not self.ffprobe:
            raise MediaRenderError(
                "Không tìm thấy ffprobe. ffprobe thường được cài cùng FFmpeg."
            )

    def supports_subtitles_filter(self) -> bool:
        self.ensure_tools()
        result = subprocess.run(
            [self.ffmpeg, "-hide_banner", "-filters"],
            capture_output=True,
            text=True,
            check=False,
        )
        return bool(re.search(r"\bsubtitles\b", result.stdout + result.stderr))

    def probe_duration(self, media_path: Path) -> float:
        self.ensure_tools()
        result = subprocess.run(
            [
                self.ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(media_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise MediaRenderError(result.stderr.strip() or "Không đọc được thời lượng video.")
        try:
            return float(json.loads(result.stdout)["format"]["duration"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise MediaRenderError("FFprobe trả về thời lượng không hợp lệ.") from exc

    @staticmethod
    def parse_natural_edit_request(text: str) -> dict[str, object]:
        """Phân tích các yêu cầu chỉnh sửa phổ biến bằng tiếng Việt."""
        normalized = text.lower().replace(",", ".")
        result: dict[str, object] = {}

        start_match = re.search(r"(?:cắt|bỏ)\s*(?:đoạn\s*)?(?:đầu|mở đầu)\s*(\d+(?:\.\d+)?)\s*giây", normalized)
        if not start_match:
            start_match = re.search(r"(?:cắt|bỏ)\s*(\d+(?:\.\d+)?)\s*giây\s*(?:đầu|mở đầu)", normalized)
        if start_match:
            result["start_seconds"] = float(start_match.group(1))

        end_match = re.search(r"(?:cắt|bỏ)\s*(?:đoạn\s*)?(?:cuối|kết)\s*(\d+(?:\.\d+)?)\s*giây", normalized)
        if end_match:
            result["trim_end_seconds"] = float(end_match.group(1))

        speed_match = re.search(r"(?:tăng tốc|tốc độ)\s*(\d+(?:\.\d+)?)\s*x", normalized)
        if speed_match:
            result["speed"] = max(0.25, min(4.0, float(speed_match.group(1))))

        if any(token in normalized for token in ("dọc", "9:16", "tiktok", "shorts", "reels")):
            result["crop_mode"] = "vertical"
        elif any(token in normalized for token in ("vuông", "1:1")):
            result["crop_mode"] = "square"
        elif any(token in normalized for token in ("ngang", "16:9", "youtube")):
            result["crop_mode"] = "horizontal"

        if any(token in normalized for token in ("tắt tiếng gốc", "bỏ tiếng gốc", "mute")):
            result["mute_original"] = True

        return result

    def create_video_from_images(
        self,
        options: ImageVideoOptions,
        progress: ProgressCallback | None = None,
    ) -> Path:
        self.ensure_tools()
        images = [Path(path) for path in options.images if Path(path).is_file()]
        if not images:
            raise MediaRenderError("Hãy chọn ít nhất một ảnh hợp lệ.")
        if options.seconds_per_image <= 0:
            raise MediaRenderError("Thời lượng mỗi ảnh phải lớn hơn 0.")

        width, height = self._parse_resolution(options.resolution)
        options.output_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="ai_studio_images_") as tmp:
            temp_dir = Path(tmp)
            segments: list[Path] = []
            total_steps = len(images) + 2

            for index, image_path in enumerate(images):
                segment_path = temp_dir / f"segment_{index:04d}.mp4"
                filter_expr = self._motion_filter(
                    motion=options.motion,
                    index=index,
                    width=width,
                    height=height,
                    seconds=options.seconds_per_image,
                    fps=options.fps,
                )
                command = [
                    self.ffmpeg,
                    "-y",
                    "-loop",
                    "1",
                    "-i",
                    str(image_path),
                    "-vf",
                    filter_expr,
                    "-t",
                    f"{options.seconds_per_image:.3f}",
                    "-r",
                    str(options.fps),
                    "-an",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "medium",
                    "-crf",
                    "20",
                    "-pix_fmt",
                    "yuv420p",
                    str(segment_path),
                ]
                self._run(command, f"Không thể tạo chuyển động cho ảnh {index + 1}.")
                segments.append(segment_path)
                if progress:
                    progress(int(((index + 1) / total_steps) * 100), f"Đã xử lý ảnh {index + 1}/{len(images)}")

            concat_file = temp_dir / "concat.txt"
            concat_file.write_text(
                "\n".join(f"file '{self._concat_escape(path)}'" for path in segments),
                encoding="utf-8",
            )
            silent_video = temp_dir / "silent_video.mp4"
            self._run(
                [
                    self.ffmpeg,
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(concat_file),
                    "-c",
                    "copy",
                    str(silent_video),
                ],
                "Không thể ghép các đoạn ảnh.",
            )
            if progress:
                progress(int(((len(images) + 1) / total_steps) * 100), "Đang ghép video")

            if options.audio_path and options.audio_path.is_file():
                self._run(
                    [
                        self.ffmpeg,
                        "-y",
                        "-i",
                        str(silent_video),
                        "-stream_loop",
                        "-1",
                        "-i",
                        str(options.audio_path),
                        "-map",
                        "0:v:0",
                        "-map",
                        "1:a:0",
                        "-c:v",
                        "copy",
                        "-c:a",
                        "aac",
                        "-b:a",
                        "192k",
                        "-shortest",
                        "-movflags",
                        "+faststart",
                        str(options.output_path),
                    ],
                    "Không thể thêm nhạc vào video.",
                )
            else:
                shutil.copy2(silent_video, options.output_path)

        if progress:
            progress(100, "Hoàn thành")
        return options.output_path

    def edit_video(
        self,
        options: VideoEditOptions,
        progress: ProgressCallback | None = None,
    ) -> Path:
        self.ensure_tools()
        if not options.input_path.is_file():
            raise MediaRenderError("File video đầu vào không tồn tại.")
        if not 0.25 <= options.speed <= 4.0:
            raise MediaRenderError("Tốc độ phải nằm trong khoảng 0.25x đến 4x.")

        duration = self.probe_duration(options.input_path)
        start = max(0.0, options.start_seconds)
        end = min(duration, options.end_seconds) if options.end_seconds else duration
        if end <= start:
            raise MediaRenderError("Mốc kết thúc phải lớn hơn mốc bắt đầu.")

        options.output_path.parent.mkdir(parents=True, exist_ok=True)
        if progress:
            progress(10, "Đang phân tích video")

        vf: list[str] = []
        if options.crop_mode == "vertical":
            vf.append("scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920")
        elif options.crop_mode == "square":
            vf.append("scale=1080:1080:force_original_aspect_ratio=increase,crop=1080:1080")
        elif options.crop_mode == "horizontal":
            vf.append("scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080")

        if options.speed != 1.0:
            vf.append(f"setpts=PTS/{options.speed:.6f}")

        subtitle_temp_dir: tempfile.TemporaryDirectory[str] | None = None
        try:
            if options.subtitle_path and options.subtitle_path.is_file():
                if not self.supports_subtitles_filter():
                    raise MediaRenderError(
                        "FFmpeg hiện tại không hỗ trợ đốt phụ đề. Hãy cài ffmpeg-full hoặc bỏ chọn file phụ đề."
                    )
                subtitle_temp_dir = tempfile.TemporaryDirectory(prefix="ai_studio_sub_")
                subtitle_copy = Path(subtitle_temp_dir.name) / f"subtitle{options.subtitle_path.suffix.lower()}"
                shutil.copy2(options.subtitle_path, subtitle_copy)
                escaped = str(subtitle_copy).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
                vf.append(
                    "subtitles=filename='{}':force_style='FontName=Arial,FontSize=22,"
                    "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,MarginV=48'".format(escaped)
                )

            command = [self.ffmpeg, "-y", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(options.input_path)]
            music_index: int | None = None
            if options.music_path and options.music_path.is_file():
                music_index = 1
                command.extend(["-stream_loop", "-1", "-i", str(options.music_path)])

            if vf:
                command.extend(["-vf", ",".join(vf)])

            if options.speed != 1.0 and not options.mute_original:
                command.extend(["-filter:a", self._atempo_filter(options.speed)])

            if music_index is not None:
                if options.mute_original:
                    command.extend([
                        "-filter_complex",
                        f"[{music_index}:a]volume={options.music_volume:.3f}[aout]",
                        "-map",
                        "0:v:0",
                        "-map",
                        "[aout]",
                    ])
                else:
                    command.extend([
                        "-filter_complex",
                        f"[0:a]volume=1.0[a0];[{music_index}:a]volume={options.music_volume:.3f}[a1];[a0][a1]amix=inputs=2:duration=first:dropout_transition=2[aout]",
                        "-map",
                        "0:v:0",
                        "-map",
                        "[aout]",
                    ])
            elif options.mute_original:
                command.append("-an")

            command.extend([
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
            ])
            if not options.mute_original or music_index is not None:
                command.extend(["-c:a", "aac", "-b:a", "192k"])
            command.extend(["-movflags", "+faststart", "-shortest", str(options.output_path)])

            if progress:
                progress(30, "Đang dựng video theo yêu cầu")
            self._run(command, "Không thể chỉnh sửa video.")
        finally:
            if subtitle_temp_dir is not None:
                subtitle_temp_dir.cleanup()

        if progress:
            progress(100, "Hoàn thành")
        return options.output_path

    @staticmethod
    def _parse_resolution(value: str) -> tuple[int, int]:
        try:
            width_text, height_text = value.lower().split("x", maxsplit=1)
            width, height = int(width_text), int(height_text)
        except (ValueError, AttributeError) as exc:
            raise MediaRenderError("Độ phân giải không hợp lệ.") from exc
        if width <= 0 or height <= 0:
            raise MediaRenderError("Độ phân giải không hợp lệ.")
        return width, height

    @staticmethod
    def _motion_filter(motion: str, index: int, width: int, height: int, seconds: float, fps: int) -> str:
        frames = max(1, round(seconds * fps))
        base = f"scale={width * 2}:{height * 2}:force_original_aspect_ratio=increase,crop={width * 2}:{height * 2}"
        presets = {
            "zoom_in": "z='min(zoom+0.0018,1.14)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
            "zoom_out": "z='if(eq(on,1),1.14,max(1.0,zoom-0.0018))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
            "pan_left": "z='1.10':x='(iw-iw/zoom)*(1-on/{frames})':y='ih/2-(ih/zoom/2)'".format(frames=frames),
            "pan_right": "z='1.10':x='(iw-iw/zoom)*(on/{frames})':y='ih/2-(ih/zoom/2)'".format(frames=frames),
        }
        if motion in ("cinematic", "random"):
            choices = ["zoom_in", "zoom_out", "pan_left", "pan_right"]
            motion = choices[index % len(choices)]
        expression = presets.get(motion, presets["zoom_in"])
        return f"{base},zoompan={expression}:d={frames}:s={width}x{height}:fps={fps},format=yuv420p"

    @staticmethod
    def _atempo_filter(speed: float) -> str:
        parts: list[float] = []
        remaining = speed
        while remaining > 2.0:
            parts.append(2.0)
            remaining /= 2.0
        while remaining < 0.5:
            parts.append(0.5)
            remaining /= 0.5
        parts.append(remaining)
        return ",".join(f"atempo={part:.6f}" for part in parts)

    @staticmethod
    def _concat_escape(path: Path) -> str:
        return str(path.resolve()).replace("'", "'\\''")

    @staticmethod
    def _run(command: Iterable[str], message: str) -> None:
        result = subprocess.run(list(command), capture_output=True, text=True, check=False)
        if result.returncode != 0:
            details = (result.stderr or result.stdout).strip()
            if len(details) > 5000:
                details = details[-5000:]
            raise MediaRenderError(f"{message}\n\n{details}")
