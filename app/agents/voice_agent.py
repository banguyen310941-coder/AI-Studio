from pathlib import Path

from app.ai.voice_generator import VoiceGenerator


class VoiceAgent:
    """
    Agent phụ trách tạo giọng đọc cho từng cảnh.

    ProjectPage sẽ làm việc với VoiceAgent
    thay vì gọi trực tiếp VoiceGenerator.
    """

    def __init__(
        self,
        voice_generator: VoiceGenerator | None = None,
    ) -> None:
        self.voice_generator = (
            voice_generator
            if voice_generator is not None
            else VoiceGenerator()
        )

    def generate(
        self,
        narration: str,
        output_path: Path,
    ) -> Path:
        """
        Tạo file giọng đọc từ nội dung narration.
        """

        clean_narration = narration.strip()

        if not clean_narration:
            raise ValueError(
                "Nội dung giọng đọc không được để trống."
            )

        output_path = Path(output_path)

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        voice_path = self.voice_generator.generate_voice(
            narration=clean_narration,
            output_path=output_path,
        )

        voice_path = Path(voice_path)

        if not voice_path.exists():
            raise RuntimeError(
                "Đã tạo giọng đọc nhưng không tìm thấy file kết quả."
            )

        return voice_path