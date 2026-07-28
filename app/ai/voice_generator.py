import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


class VoiceGenerator:
    def __init__(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        env_path = project_root / ".env"

        load_dotenv(dotenv_path=env_path)

        api_key = os.getenv("OPENAI_API_KEY", "").strip()

        self.model = os.getenv(
            "OPENAI_TTS_MODEL",
            "gpt-4o-mini-tts",
        ).strip()

        self.voice = os.getenv(
            "OPENAI_TTS_VOICE",
            "coral",
        ).strip()

        speed_text = os.getenv(
            "OPENAI_TTS_SPEED",
            "1.0",
        ).strip()

        try:
            self.speed = float(speed_text)
        except ValueError:
            self.speed = 1.0

        if not 0.25 <= self.speed <= 4.0:
            self.speed = 1.0

        if not api_key:
            raise ValueError(
                f"Không tìm thấy OPENAI_API_KEY trong {env_path}"
            )

        self.client = OpenAI(api_key=api_key)

    def generate_voice(
        self,
        narration: str,
        output_path: Path,
    ) -> Path:
        clean_text = narration.strip()

        if not clean_text:
            raise ValueError(
                "Lời đọc của cảnh đang để trống."
            )

        if len(clean_text) > 4096:
            raise ValueError(
                "Lời đọc vượt quá giới hạn 4096 ký tự."
            )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with self.client.audio.speech.with_streaming_response.create(
            model=self.model,
            voice=self.voice,
            input=clean_text,
            instructions=(
                "Đọc bằng tiếng Việt tự nhiên, rõ ràng, "
                "ấm áp, chuyên nghiệp, phù hợp video quảng cáo. "
                "Ngắt nghỉ hợp lý và không đọc quá nhanh."
            ),
            response_format="mp3",
            speed=self.speed,
        ) as response:
            response.stream_to_file(output_path)

        if not output_path.exists():
            raise RuntimeError(
                "Không tạo được file giọng đọc."
            )

        if output_path.stat().st_size == 0:
            raise RuntimeError(
                "File giọng đọc được tạo nhưng không có dữ liệu."
            )

        return output_path