from __future__ import annotations

import math
from dataclasses import dataclass

from app.models.film_project import FilmProject, FilmShot


@dataclass(slots=True)
class FilmPlanOptions:
    title: str
    idea: str
    genre: str = "Điện ảnh"
    target_minutes: int = 15
    aspect_ratio: str = "16:9"
    resolution: str = "720p"
    veo_model: str = "veo-3.1-fast-generate-preview"


class FilmPlanningService:
    """Tạo cấu trúc phim, lời dẫn và prompt Veo theo từng shot 8 giây."""

    SHOT_STYLES = (
        ("Establishing wide shot", "slow cinematic crane movement"),
        ("Medium tracking shot", "smooth lateral tracking"),
        ("Intimate close-up", "slow push-in with shallow depth of field"),
        ("Low-angle dramatic shot", "subtle handheld movement"),
        ("Over-the-shoulder shot", "gentle rack focus"),
        ("Aerial landscape shot", "slow forward drone movement"),
        ("Detailed insert shot", "controlled macro camera movement"),
        ("Dynamic action shot", "energetic stabilized tracking"),
    )

    BEATS = {
        1: (
            "Giới thiệu thế giới và nhân vật trung tâm",
            "Dấu hiệu bất thường đầu tiên xuất hiện",
            "Nhân vật bị buộc phải bước vào hành trình",
        ),
        2: (
            "Hành trình mở rộng và xung đột tăng dần",
            "Bí mật quan trọng được hé lộ",
            "Thất bại lớn khiến mọi thứ tưởng như kết thúc",
        ),
        3: (
            "Nhân vật tìm ra lựa chọn cuối cùng",
            "Cao trào điện ảnh và cuộc đối đầu quyết định",
            "Kết thúc, hậu quả và hình ảnh đọng lại",
        ),
    }

    def create_plan(self, options: FilmPlanOptions) -> FilmProject:
        if not options.idea.strip():
            raise ValueError("Bạn cần nhập ý tưởng phim.")
        minutes = max(15, int(options.target_minutes))
        shot_duration = 8
        shot_count = math.ceil(minutes * 60 / shot_duration)
        scene_size = 5
        shots: list[FilmShot] = []

        for index in range(1, shot_count + 1):
            progress = (index - 1) / max(1, shot_count)
            act = 1 if progress < 0.25 else 2 if progress < 0.75 else 3
            scene = math.ceil(index / scene_size)
            act_progress = (
                progress / 0.25 if act == 1 else
                (progress - 0.25) / 0.50 if act == 2 else
                (progress - 0.75) / 0.25
            )
            beat_list = self.BEATS[act]
            beat_index = min(2, int(act_progress * 3))
            beat = beat_list[beat_index]
            composition, movement = self.SHOT_STYLES[(index - 1) % len(self.SHOT_STYLES)]
            title = f"Hồi {act} · Cảnh {scene} · Shot {index}"
            narration = self._narration(options.idea, act, beat, index, shot_count)
            prompt = self._veo_prompt(
                idea=options.idea,
                genre=options.genre,
                act=act,
                beat=beat,
                composition=composition,
                movement=movement,
                index=index,
            )
            shots.append(
                FilmShot(
                    index=index,
                    act=act,
                    scene=scene,
                    title=title,
                    duration_seconds=shot_duration,
                    narration=narration,
                    veo_prompt=prompt,
                )
            )

        return FilmProject(
            title=options.title.strip() or "Bộ phim mới",
            idea=options.idea.strip(),
            genre=options.genre,
            target_minutes=minutes,
            aspect_ratio=options.aspect_ratio,
            resolution=options.resolution,
            veo_model=options.veo_model,
            shots=shots,
        )

    @staticmethod
    def _narration(idea: str, act: int, beat: str, index: int, total: int) -> str:
        return (
            f"Hồi {act}. {beat}. Diễn biến {index}/{total} tiếp tục phát triển câu chuyện: "
            f"{idea.strip()}"
        )

    @staticmethod
    def _veo_prompt(
        idea: str,
        genre: str,
        act: int,
        beat: str,
        composition: str,
        movement: str,
        index: int,
    ) -> str:
        lighting = "soft atmospheric light" if act == 1 else "high-contrast cinematic lighting" if act == 2 else "epic dramatic light with volumetric rays"
        pacing = "measured and immersive" if act == 1 else "tense and escalating" if act == 2 else "powerful, emotional and conclusive"
        return (
            f"Create an 8-second cinematic film shot. Story premise: {idea.strip()}. "
            f"Current dramatic beat: {beat}. Genre and visual language: {genre}. "
            f"Shot {index}: {composition}, {movement}. {lighting}. "
            f"Pacing is {pacing}. Natural realistic motion, coherent anatomy, consistent characters, "
            "production design continuity, realistic fabric and physics, cinematic color grading, "
            "24 fps, detailed environment, no subtitles, no captions, no logos, no watermark. "
            "Include synchronized ambience and sound effects appropriate to the action; use dialogue only when essential."
        )
