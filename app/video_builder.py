from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


class VideoBuilder:
    """
    Dựng video cảnh bằng FFmpeg.

    Cách xử lý phụ đề:
    1. Nếu FFmpeg có filter `subtitles`, phụ đề được đốt trực tiếp vào hình.
    2. Nếu FFmpeg không có filter đó, phụ đề được nhúng vào MP4 dưới dạng
       mov_text để pipeline vẫn hoàn thành thay vì dừng toàn bộ.

    Đường dẫn phụ đề được sao chép sang thư mục tạm với tên ASCII đơn giản,
    giúp tránh lỗi FFmpeg khi đường dẫn macOS có khoảng trắng hoặc ký tự đặc biệt.
    """

    def __init__(
        self,
        width: int = 1280,
        height: int = 720,
        fps: int = 30,
    ) -> None:
        self.width = int(width)
        self.height = int(height)
        self.fps = int(fps)

        self.ffmpeg_path = shutil.which("ffmpeg")
        self.ffprobe_path = shutil.which("ffprobe")

        if not self.ffmpeg_path:
            raise RuntimeError(
                "Không tìm thấy FFmpeg trên máy."
            )

        if not self.ffprobe_path:
            raise RuntimeError(
                "Không tìm thấy FFprobe trên máy."
            )

        self._subtitle_filter_available: bool | None = None

    # =========================================================
    # SCENE VIDEO
    # =========================================================

    def create_scene_video(
        self,
        image_path: Path,
        audio_path: Path,
        output_path: Path,
        scene_number: int = 1,
        subtitle_path: Path | None = None,
    ) -> Path:
        image_path = Path(image_path).expanduser().resolve()
        audio_path = Path(audio_path).expanduser().resolve()
        output_path = Path(output_path).expanduser().resolve()

        resolved_subtitle_path: Path | None = None

        if subtitle_path is not None:
            resolved_subtitle_path = (
                Path(subtitle_path)
                .expanduser()
                .resolve()
            )

        self._validate_input_file(
            image_path,
            "ảnh",
        )
        self._validate_input_file(
            audio_path,
            "giọng đọc",
        )

        if resolved_subtitle_path is not None:
            self._validate_input_file(
                resolved_subtitle_path,
                "phụ đề",
            )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        duration = self.get_audio_duration(
            audio_path
        )

        total_frames = max(
            1,
            round(duration * self.fps),
        )

        base_video_filter = (
            self.build_ken_burns_filter(
                scene_number=scene_number,
                total_frames=total_frames,
            )
        )

        if resolved_subtitle_path is None:
            self._create_without_subtitle(
                image_path=image_path,
                audio_path=audio_path,
                output_path=output_path,
                duration=duration,
                video_filter=base_video_filter,
            )

        elif self.has_subtitles_filter():
            self._create_with_burned_subtitle(
                image_path=image_path,
                audio_path=audio_path,
                subtitle_path=resolved_subtitle_path,
                output_path=output_path,
                duration=duration,
                video_filter=base_video_filter,
            )

        else:
            self._create_with_embedded_subtitle(
                image_path=image_path,
                audio_path=audio_path,
                subtitle_path=resolved_subtitle_path,
                output_path=output_path,
                duration=duration,
                video_filter=base_video_filter,
            )

        self.validate_output(
            output_path
        )

        return output_path

    def _create_without_subtitle(
        self,
        image_path: Path,
        audio_path: Path,
        output_path: Path,
        duration: float,
        video_filter: str,
    ) -> None:
        command = self._base_scene_command(
            image_path=image_path,
            audio_path=audio_path,
        )

        command.extend(
            [
                "-vf",
                video_filter,
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
            ]
        )

        command.extend(
            self._scene_output_options(
                duration=duration,
                output_path=output_path,
            )
        )

        self.run_command(
            command,
            "Không thể tạo video cảnh.",
        )

    def _create_with_burned_subtitle(
        self,
        image_path: Path,
        audio_path: Path,
        subtitle_path: Path,
        output_path: Path,
        duration: float,
        video_filter: str,
    ) -> None:
        """
        Đốt phụ đề vào hình.

        FFmpeg được chạy trong một thư mục tạm và phụ đề được đặt tên
        `subtitle.srt`, nên filter không phải xử lý đường dẫn dài,
        khoảng trắng hoặc ký tự tiếng Việt.
        """

        with tempfile.TemporaryDirectory(
            prefix="ai_studio_subtitle_"
        ) as temporary_directory:
            temporary_path = Path(
                temporary_directory
            )

            temporary_subtitle = (
                temporary_path
                / "subtitle.srt"
            )

            shutil.copy2(
                subtitle_path,
                temporary_subtitle,
            )

            subtitle_filter = (
                self.build_subtitle_filter(
                    temporary_subtitle.name
                )
            )

            combined_filter = (
                f"{video_filter},"
                f"{subtitle_filter}"
            )

            command = self._base_scene_command(
                image_path=image_path,
                audio_path=audio_path,
            )

            command.extend(
                [
                    "-vf",
                    combined_filter,
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                ]
            )

            command.extend(
                self._scene_output_options(
                    duration=duration,
                    output_path=output_path,
                )
            )

            self.run_command(
                command,
                "Không thể tạo video cảnh và chèn phụ đề.",
                cwd=temporary_path,
            )

    def _create_with_embedded_subtitle(
        self,
        image_path: Path,
        audio_path: Path,
        subtitle_path: Path,
        output_path: Path,
        duration: float,
        video_filter: str,
    ) -> None:
        """
        Phương án dự phòng khi FFmpeg không có filter `subtitles`.

        Phụ đề được nhúng dưới dạng mov_text. Video vẫn dựng thành công;
        người xem có thể bật/tắt phụ đề trong trình phát hỗ trợ.
        """

        command = [
            self.ffmpeg_path,
            "-y",
            "-loop",
            "1",
            "-framerate",
            str(self.fps),
            "-i",
            str(image_path),
            "-i",
            str(audio_path),
            "-i",
            str(subtitle_path),
            "-vf",
            video_filter,
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-map",
            "2:0",
            "-c:s",
            "mov_text",
            "-metadata:s:s:0",
            "language=vie",
            "-disposition:s:0",
            "default",
        ]

        command.extend(
            self._scene_output_options(
                duration=duration,
                output_path=output_path,
            )
        )

        self.run_command(
            command,
            (
                "Không thể tạo video cảnh "
                "với phụ đề nhúng."
            ),
        )

    def _base_scene_command(
        self,
        image_path: Path,
        audio_path: Path,
    ) -> list[str]:
        return [
            self.ffmpeg_path,
            "-y",
            "-loop",
            "1",
            "-framerate",
            str(self.fps),
            "-i",
            str(image_path),
            "-i",
            str(audio_path),
        ]

    def _scene_output_options(
        self,
        duration: float,
        output_path: Path,
    ) -> list[str]:
        return [
            "-t",
            f"{duration:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-tune",
            "stillimage",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "44100",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-shortest",
            str(output_path),
        ]

    # =========================================================
    # FILTERS
    # =========================================================

    def build_ken_burns_filter(
        self,
        scene_number: int,
        total_frames: int,
    ) -> str:
        effect_index = (
            (int(scene_number) - 1) % 3
        )

        total_frames = max(
            1,
            int(total_frames),
        )

        large_width = self.width * 2
        large_height = self.height * 2

        base_scale = (
            f"scale={large_width}:"
            f"{large_height}:"
            "force_original_aspect_ratio=increase,"
            f"crop={large_width}:"
            f"{large_height},"
        )

        frame_divisor = max(
            total_frames - 1,
            1,
        )

        if effect_index == 0:
            zoompan = (
                "zoompan="
                "z='min(zoom+0.0008,1.12)':"
                "x='iw/2-(iw/zoom/2)':"
                "y='ih/2-(ih/zoom/2)':"
                f"d={total_frames}:"
                f"s={self.width}x{self.height}:"
                f"fps={self.fps}"
            )

        elif effect_index == 1:
            zoompan = (
                "zoompan="
                "z='1.08':"
                "x='(iw-iw/zoom)*on/"
                f"{frame_divisor}':"
                "y='ih/2-(ih/zoom/2)':"
                f"d={total_frames}:"
                f"s={self.width}x{self.height}:"
                f"fps={self.fps}"
            )

        else:
            zoompan = (
                "zoompan="
                "z='1.08':"
                "x='(iw-iw/zoom)*"
                f"(1-on/{frame_divisor})':"
                "y='ih/2-(ih/zoom/2)':"
                f"d={total_frames}:"
                f"s={self.width}x{self.height}:"
                f"fps={self.fps}"
            )

        return (
            base_scale
            + zoompan
            + ",format=yuv420p"
        )

    def build_subtitle_filter(
        self,
        subtitle_filename: str,
    ) -> str:
        """
        subtitle_filename chỉ nên là tên file đơn giản trong cwd,
        ví dụ `subtitle.srt`.
        """

        safe_filename = (
            str(subtitle_filename)
            .replace("\\", "\\\\")
            .replace("'", r"\'")
            .replace(":", r"\:")
            .replace(",", r"\,")
            .replace("[", r"\[")
            .replace("]", r"\]")
        )

        force_style = (
            "FontName=Arial,"
            "FontSize=22,"
            "PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,"
            "BackColour=&H80000000,"
            "BorderStyle=3,"
            "Outline=1,"
            "Shadow=0,"
            "Alignment=2,"
            "MarginV=42"
        )

        return (
            f"subtitles=filename='{safe_filename}':"
            f"force_style='{force_style}'"
        )

    def has_subtitles_filter(
        self,
    ) -> bool:
        """
        Kiểm tra chính xác FFmpeg hiện tại có filter subtitles hay không.
        Kết quả được cache để không gọi lại ở từng cảnh.
        """

        if self._subtitle_filter_available is not None:
            return self._subtitle_filter_available

        result = subprocess.run(
            [
                self.ffmpeg_path,
                "-hide_banner",
                "-filters",
            ],
            capture_output=True,
            text=True,
        )

        filter_output = (
            result.stdout
            + "\n"
            + result.stderr
        )

        self._subtitle_filter_available = any(
            line.strip().split()
            and "subtitles" in line.strip().split()
            for line in filter_output.splitlines()
        )

        return self._subtitle_filter_available

    # Giữ API cũ để các module khác không bị lỗi nếu đang gọi hàm này.
    def escape_filter_path(
        self,
        file_path: Path,
    ) -> str:
        path_text = str(
            Path(file_path)
        )

        return (
            path_text
            .replace("\\", "\\\\")
            .replace(":", r"\:")
            .replace("'", r"\'")
            .replace(",", r"\,")
            .replace("[", r"\[")
            .replace("]", r"\]")
        )

    # =========================================================
    # AUDIO
    # =========================================================

    def get_audio_duration(
        self,
        audio_path: Path,
    ) -> float:
        audio_path = (
            Path(audio_path)
            .expanduser()
            .resolve()
        )

        self._validate_input_file(
            audio_path,
            "giọng đọc",
        )

        command = [
            self.ffprobe_path,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            (
                "default="
                "noprint_wrappers=1:"
                "nokey=1"
            ),
            str(audio_path),
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            error_message = (
                result.stderr.strip()
                or (
                    "Không đọc được thời lượng "
                    "âm thanh."
                )
            )

            raise RuntimeError(
                "Không thể xác định thời lượng "
                f"giọng đọc.\n\n{error_message}"
            )

        try:
            duration = float(
                result.stdout.strip()
            )
        except ValueError as error:
            raise RuntimeError(
                "Thời lượng âm thanh không hợp lệ."
            ) from error

        if duration <= 0:
            raise RuntimeError(
                "File âm thanh có thời lượng bằng 0."
            )

        return duration

    # =========================================================
    # MERGE
    # =========================================================

    def merge_scene_videos(
        self,
        scene_paths: list[Path],
        output_path: Path,
    ) -> Path:
        if not scene_paths:
            raise ValueError(
                "Không có video cảnh để ghép."
            )

        normalized_paths: list[Path] = []

        for scene_path in scene_paths:
            path = (
                Path(scene_path)
                .expanduser()
                .resolve()
            )

            self._validate_input_file(
                path,
                "video cảnh",
            )

            normalized_paths.append(
                path
            )

        output_path = (
            Path(output_path)
            .expanduser()
            .resolve()
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        concat_file = (
            output_path.parent
            / "scene_list.txt"
        )

        concat_lines: list[str] = []

        for path in normalized_paths:
            safe_path = str(path).replace(
                "'",
                r"'\''",
            )

            concat_lines.append(
                f"file '{safe_path}'"
            )

        concat_file.write_text(
            "\n".join(concat_lines),
            encoding="utf-8",
        )

        command = [
            self.ffmpeg_path,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(output_path),
        ]

        try:
            self.run_command(
                command,
                (
                    "Không thể ghép video "
                    "hoàn chỉnh."
                ),
            )
        finally:
            concat_file.unlink(
                missing_ok=True
            )

        self.validate_output(
            output_path
        )

        return output_path

    # =========================================================
    # COMMAND / VALIDATION
    # =========================================================

    def run_command(
        self,
        command: list[str],
        error_title: str,
        cwd: Path | None = None,
    ) -> None:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=(
                str(cwd)
                if cwd is not None
                else None
            ),
        )

        if result.returncode == 0:
            return

        error_message = (
            result.stderr.strip()
            or result.stdout.strip()
            or (
                "FFmpeg không trả về "
                "thông báo lỗi."
            )
        )

        readable_command = " ".join(
            str(part)
            for part in command
        )

        raise RuntimeError(
            f"{error_title}\n\n"
            f"{error_message}\n\n"
            "Lệnh FFmpeg:\n"
            f"{readable_command}"
        )

    def validate_output(
        self,
        output_path: Path,
    ) -> None:
        output_path = Path(
            output_path
        )

        if not output_path.exists():
            raise RuntimeError(
                "FFmpeg chạy xong nhưng "
                "không tạo file."
            )

        if output_path.stat().st_size == 0:
            raise RuntimeError(
                "File đã tạo nhưng không có dữ liệu."
            )

    @staticmethod
    def _validate_input_file(
        file_path: Path,
        description: str,
    ) -> None:
        if not file_path.exists():
            raise FileNotFoundError(
                f"Không tìm thấy {description}:\n"
                f"{file_path}"
            )

        if not file_path.is_file():
            raise FileNotFoundError(
                f"Đường dẫn {description} không phải file:\n"
                f"{file_path}"
            )

        if file_path.stat().st_size == 0:
            raise RuntimeError(
                f"File {description} không có dữ liệu:\n"
                f"{file_path}"
            )
