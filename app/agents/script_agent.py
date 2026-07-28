from app.ai.script_writer import ScriptWriter


class ScriptAgent:
    """
    Agent phụ trách tạo kịch bản và chia cảnh.

    Lớp này đứng giữa giao diện và ScriptWriter.
    Sau này có thể mở rộng để:

    - Chọn mô hình AI.
    - Kiểm tra nội dung đầu vào.
    - Chuẩn hóa kết quả cảnh.
    - Thử lại khi API lỗi.
    - Ghi nhật ký quá trình tạo kịch bản.
    """

    def __init__(
        self,
        script_writer: ScriptWriter | None = None,
    ) -> None:
        self.script_writer = (
            script_writer
            if script_writer is not None
            else ScriptWriter()
        )

    def generate(
        self,
        topic: str,
    ) -> list[dict]:
        clean_topic = topic.strip()

        if not clean_topic:
            raise ValueError(
                "Chủ đề video không được để trống."
            )

        scenes = self.script_writer.generate_scenes(
            clean_topic
        )

        if not isinstance(scenes, list):
            raise RuntimeError(
                "AI trả về dữ liệu kịch bản không hợp lệ."
            )

        if not scenes:
            raise RuntimeError(
                "AI không tạo được cảnh nào."
            )

        return self.normalize_scenes(scenes)

    def normalize_scenes(
        self,
        scenes: list[dict],
    ) -> list[dict]:
        """
        Chuẩn hóa dữ liệu để SceneCard luôn nhận đủ trường.
        """

        normalized_scenes: list[dict] = []

        for index, scene in enumerate(
            scenes,
            start=1,
        ):
            if not isinstance(scene, dict):
                raise RuntimeError(
                    f"Dữ liệu Cảnh {index} không hợp lệ."
                )

            normalized_scene = {
                "title": str(
                    scene.get(
                        "title",
                        f"Cảnh {index}",
                    )
                ).strip(),
                "visual": str(
                    scene.get(
                        "visual",
                        "",
                    )
                ).strip(),
                "narration": str(
                    scene.get(
                        "narration",
                        "",
                    )
                ).strip(),
                "screen_text": str(
                    scene.get(
                        "screen_text",
                        "",
                    )
                ).strip(),
                "image_prompt": str(
                    scene.get(
                        "image_prompt",
                        "",
                    )
                ).strip(),
            }

            if not normalized_scene["title"]:
                normalized_scene["title"] = (
                    f"Cảnh {index}"
                )

            if not normalized_scene["narration"]:
                raise RuntimeError(
                    f"Cảnh {index} chưa có lời đọc."
                )

            if not normalized_scene["image_prompt"]:
                raise RuntimeError(
                    f"Cảnh {index} chưa có prompt tạo ảnh."
                )

            normalized_scenes.append(
                normalized_scene
            )

        return normalized_scenes