import base64
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


class ImageGenerator:
    def __init__(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        env_path = project_root / ".env"

        load_dotenv(dotenv_path=env_path)

        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.model = os.getenv(
            "OPENAI_IMAGE_MODEL",
            "gpt-image-2",
        ).strip()

        if not api_key:
            raise ValueError(
                f"Không tìm thấy OPENAI_API_KEY trong {env_path}"
            )

        self.client = OpenAI(api_key=api_key)

    def generate_image(
        self,
        prompt: str,
        output_path: Path,
    ) -> Path:
        clean_prompt = prompt.strip()

        if not clean_prompt:
            raise ValueError(
                "Prompt tạo ảnh đang để trống."
            )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        result = self.client.images.generate(
            model=self.model,
            prompt=clean_prompt,
            size="1536x1024",
            quality="medium",
            n=1,
        )

        if not result.data:
            raise RuntimeError(
                "AI không trả về dữ liệu hình ảnh."
            )

        image_base64 = result.data[0].b64_json

        if not image_base64:
            raise RuntimeError(
                "Không tìm thấy dữ liệu Base64 của hình ảnh."
            )

        image_bytes = base64.b64decode(image_base64)

        output_path.write_bytes(image_bytes)

        return output_path