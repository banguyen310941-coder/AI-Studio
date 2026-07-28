from pathlib import Path

from app.ai.image_generator import ImageGenerator


class ImageAgent:
    """
    Agent phụ trách tạo ảnh cho từng cảnh.

    ProjectPage chỉ làm việc với ImageAgent,
    không gọi trực tiếp ImageGenerator nữa.
    """

    def __init__(
        self,
        image_generator: ImageGenerator | None = None,
    ) -> None:
        self.image_generator = (
            image_generator
            if image_generator is not None
            else ImageGenerator()
        )

    def generate(
        self,
        prompt: str,
        output_path: Path,
    ) -> Path:
        clean_prompt = prompt.strip()

        if not clean_prompt:
            raise ValueError(
                "Prompt tạo ảnh không được để trống."
            )

        output_path = Path(output_path)

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        image_path = (
            self.image_generator.generate_image(
                prompt=clean_prompt,
                output_path=output_path,
            )
        )

        image_path = Path(image_path)

        if not image_path.exists():
            raise RuntimeError(
                "Ảnh đã tạo nhưng không tìm thấy file kết quả."
            )

        return image_path