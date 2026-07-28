import re
from pathlib import Path


class SubtitleBuilder:
    """
    Tạo file phụ đề SRT từ lời đọc của từng cảnh.

    Lời đọc được chia thành các đoạn ngắn và phân bổ đều
    theo thời lượng của file âm thanh.
    """

    def __init__(
        self,
        max_words_per_caption: int = 8,
    ) -> None:
        self.max_words_per_caption = max_words_per_caption

    def create_scene_subtitle(
        self,
        narration: str,
        duration: float,
        output_path: Path,
    ) -> Path:
        narration = narration.strip()
        output_path = Path(output_path)

        if not narration:
            raise ValueError(
                "Không có lời đọc để tạo phụ đề."
            )

        if duration <= 0:
            raise ValueError(
                "Thời lượng âm thanh không hợp lệ."
            )

        captions = self.split_narration(
            narration
        )

        if not captions:
            raise ValueError(
                "Không thể chia lời đọc thành phụ đề."
            )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        caption_weights = [
            max(len(caption.split()), 1)
            for caption in captions
        ]

        total_weight = sum(caption_weights)

        current_time = 0.0
        subtitle_blocks: list[str] = []

        for index, caption in enumerate(
            captions,
            start=1,
        ):
            weight = caption_weights[index - 1]

            caption_duration = (
                duration * weight / total_weight
            )

            start_time = current_time

            if index == len(captions):
                end_time = duration
            else:
                end_time = min(
                    duration,
                    current_time + caption_duration,
                )

            subtitle_blocks.append(
                self.create_srt_block(
                    index=index,
                    start_time=start_time,
                    end_time=end_time,
                    text=caption,
                )
            )

            current_time = end_time

        output_path.write_text(
            "\n\n".join(subtitle_blocks) + "\n",
            encoding="utf-8",
        )

        self.validate_output(output_path)

        return output_path

    def split_narration(
        self,
        narration: str,
    ) -> list[str]:
        """
        Chia lời đọc thành các đoạn phụ đề ngắn.

        Ưu tiên chia theo dấu câu, sau đó giới hạn số từ
        trong mỗi đoạn.
        """

        cleaned_text = re.sub(
            r"\s+",
            " ",
            narration,
        ).strip()

        sentences = re.split(
            r"(?<=[.!?…])\s+",
            cleaned_text,
        )

        captions: list[str] = []

        for sentence in sentences:
            sentence = sentence.strip()

            if not sentence:
                continue

            words = sentence.split()

            while words:
                caption_words = words[
                    :self.max_words_per_caption
                ]

                words = words[
                    self.max_words_per_caption:
                ]

                caption = " ".join(
                    caption_words
                ).strip()

                if caption:
                    captions.append(caption)

        return captions

    def create_srt_block(
        self,
        index: int,
        start_time: float,
        end_time: float,
        text: str,
    ) -> str:
        start_text = self.format_srt_time(
            start_time
        )

        end_text = self.format_srt_time(
            end_time
        )

        return (
            f"{index}\n"
            f"{start_text} --> {end_text}\n"
            f"{text}"
        )

    def format_srt_time(
        self,
        seconds: float,
    ) -> str:
        milliseconds_total = max(
            0,
            int(round(seconds * 1000)),
        )

        hours = (
            milliseconds_total // 3_600_000
        )

        minutes = (
            milliseconds_total % 3_600_000
        ) // 60_000

        seconds_value = (
            milliseconds_total % 60_000
        ) // 1000

        milliseconds = (
            milliseconds_total % 1000
        )

        return (
            f"{hours:02d}:"
            f"{minutes:02d}:"
            f"{seconds_value:02d},"
            f"{milliseconds:03d}"
        )

    def validate_output(
        self,
        output_path: Path,
    ) -> None:
        if not output_path.exists():
            raise RuntimeError(
                "Không thể tạo file phụ đề."
            )

        if output_path.stat().st_size == 0:
            raise RuntimeError(
                "File phụ đề không có dữ liệu."
            )