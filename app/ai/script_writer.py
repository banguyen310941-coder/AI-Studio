import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


class ScriptWriter:
    def __init__(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        env_path = project_root / ".env"

        load_dotenv(dotenv_path=env_path)

        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.model = os.getenv(
            "OPENAI_MODEL",
            "gpt-4.1-mini",
        ).strip()

        if not api_key:
            raise ValueError(
                f"Không tìm thấy OPENAI_API_KEY trong {env_path}"
            )

        self.client = OpenAI(api_key=api_key)

    def generate_scenes(self, topic: str) -> list[dict]:
        clean_topic = topic.strip()

        if not clean_topic:
            raise ValueError("Chủ đề video đang để trống.")

        prompt = f"""
Bạn là chuyên gia viết kịch bản video quảng cáo ngắn bằng tiếng Việt.

Hãy tạo kịch bản cho chủ đề sau:

{clean_topic}

Yêu cầu:
- Video dài khoảng 30 đến 45 giây.
- Chia thành 4 đến 6 cảnh.
- Mỗi cảnh có tiêu đề ngắn.
- Có mô tả hình ảnh hoặc footage.
- Có lời đọc tự nhiên.
- Có chữ xuất hiện trên màn hình.
- Có prompt tiếng Anh để tạo hình ảnh AI.
- Prompt ảnh cụ thể, chân thực, phong cách quảng cáo.
- Cảnh đầu phải thu hút.
- Cảnh cuối có lời kêu gọi hành động.

Chỉ trả về JSON hợp lệ theo cấu trúc:

{{
  "scenes": [
    {{
      "scene_number": 1,
      "title": "Tên cảnh",
      "visual": "Mô tả hình ảnh",
      "narration": "Lời đọc",
      "screen_text": "Chữ trên màn hình",
      "image_prompt": "English image generation prompt"
    }}
  ]
}}

Không dùng Markdown.
Không đặt JSON trong dấu ba dấu nháy.
Không viết giải thích bên ngoài JSON.
""".strip()

        response = self.client.responses.create(
            model=self.model,
            input=prompt,
        )

        raw_content = response.output_text.strip()

        if not raw_content:
            raise RuntimeError(
                "AI không trả về nội dung kịch bản."
            )

        cleaned_content = self.clean_json_text(raw_content)

        try:
            result = json.loads(cleaned_content)
        except json.JSONDecodeError as error:
            raise RuntimeError(
                "AI trả về dữ liệu không đúng định dạng JSON. "
                "Bạn hãy thử tạo lại."
            ) from error

        scenes = result.get("scenes", [])

        if not isinstance(scenes, list) or not scenes:
            raise RuntimeError(
                "AI không tạo được danh sách cảnh."
            )

        return self.normalize_scenes(scenes)

    def clean_json_text(self, content: str) -> str:
        cleaned = content.strip()

        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]

        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]

        return cleaned.strip()

    def normalize_scenes(
        self,
        scenes: list[dict],
    ) -> list[dict]:
        normalized: list[dict] = []

        for index, scene in enumerate(scenes, start=1):
            normalized.append(
                {
                    "scene_number": index,
                    "title": str(
                        scene.get("title", f"Cảnh {index}")
                    ).strip(),
                    "visual": str(
                        scene.get("visual", "")
                    ).strip(),
                    "narration": str(
                        scene.get("narration", "")
                    ).strip(),
                    "screen_text": str(
                        scene.get("screen_text", "")
                    ).strip(),
                    "image_prompt": str(
                        scene.get("image_prompt", "")
                    ).strip(),
                }
            )

        return normalized
