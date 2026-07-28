from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import re


@dataclass(frozen=True)
class DirectorOptions:
    title: str
    idea: str
    genre: str
    tone: str
    target_minutes: int
    language: str = "Tiếng Việt"


@dataclass(frozen=True)
class ShotPlan:
    number: int
    title: str
    description: str
    camera: str
    veo_prompt: str


@dataclass(frozen=True)
class ScenePlan:
    number: int
    act: int
    title: str
    purpose: str
    location: str
    time_of_day: str
    narration: str
    shots: list[ShotPlan]


@dataclass(frozen=True)
class DirectorPlan:
    title: str
    logline: str
    genre: str
    tone: str
    target_minutes: int
    characters: list[dict[str, str]]
    scenes: list[ScenePlan]


class AIDirectorService:
    CAMERA_PATTERNS = (
        ("Toàn cảnh mở đầu", "wide establishing shot, slow cinematic push-in"),
        ("Trung cảnh chuyển động", "medium tracking shot, smooth lateral movement"),
        ("Cận cảnh cảm xúc", "intimate close-up, shallow depth of field"),
        ("Góc thấp kịch tính", "low-angle dramatic shot, subtle handheld motion"),
        ("Qua vai đối thoại", "over-the-shoulder shot, gentle rack focus"),
        ("Chi tiết quan trọng", "macro insert shot, controlled camera movement"),
    )

    STORY_BEATS = (
        (1, "Mở đầu", "Giới thiệu thế giới, nhân vật trung tâm và trạng thái ban đầu."),
        (1, "Biến cố", "Một sự kiện bất ngờ phá vỡ cuộc sống bình thường."),
        (1, "Quyết định", "Nhân vật buộc phải lựa chọn và bước vào hành trình."),
        (2, "Khám phá", "Thế giới mở rộng, cơ hội và nguy hiểm cùng xuất hiện."),
        (2, "Đối đầu", "Xung đột tăng mạnh và mục tiêu trở nên khó đạt hơn."),
        (2, "Bí mật", "Một sự thật quan trọng thay đổi cách nhìn của nhân vật."),
        (2, "Thất bại", "Kế hoạch sụp đổ, nhân vật rơi vào điểm thấp nhất."),
        (3, "Tái sinh", "Nhân vật hiểu điều cốt lõi và chuẩn bị hành động cuối."),
        (3, "Cao trào", "Cuộc đối đầu quyết định giải quyết xung đột trung tâm."),
        (3, "Kết", "Hậu quả, sự thay đổi và hình ảnh cuối đọng lại."),
    )

    def create_plan(self, options: DirectorOptions) -> DirectorPlan:
        title = options.title.strip() or "Bộ phim mới"
        idea = options.idea.strip()
        if not idea:
            raise ValueError("Bạn cần nhập ý tưởng phim.")

        scene_count = max(6, min(24, round(max(3, options.target_minutes) / 2)))
        selected_beats = self._spread_beats(scene_count)

        characters = [
            {
                "name": "Nhân vật chính",
                "role": "Người dẫn dắt câu chuyện",
                "description": self._character_description(idea, options.tone),
            },
            {
                "name": "Đối trọng",
                "role": "Nguồn tạo xung đột",
                "description": f"Đại diện cho trở ngại lớn nhất trong câu chuyện {idea}.",
            },
        ]

        scenes: list[ScenePlan] = []
        shot_number = 1

        for scene_number, beat in enumerate(selected_beats, start=1):
            act, beat_title, purpose = beat
            shots: list[ShotPlan] = []

            for local_index in range(3):
                visual_title, camera = self.CAMERA_PATTERNS[
                    (shot_number - 1) % len(self.CAMERA_PATTERNS)
                ]
                description = (
                    f"{visual_title}: phát triển cảnh “{beat_title}”, "
                    f"làm rõ {purpose.lower()} Nội dung trung tâm: {idea}"
                )
                prompt = self._create_veo_prompt(
                    idea=idea,
                    genre=options.genre,
                    tone=options.tone,
                    act=act,
                    beat_title=beat_title,
                    camera=camera,
                    shot_number=shot_number,
                )
                shots.append(
                    ShotPlan(
                        number=shot_number,
                        title=f"Shot {shot_number} · {visual_title}",
                        description=description,
                        camera=camera,
                        veo_prompt=prompt,
                    )
                )
                shot_number += 1

            scenes.append(
                ScenePlan(
                    number=scene_number,
                    act=act,
                    title=f"Cảnh {scene_number}: {beat_title}",
                    purpose=purpose,
                    location=self._location_for(scene_number, idea),
                    time_of_day=self._time_for(scene_number),
                    narration=(
                        f"Cảnh này đưa câu chuyện tiến tới nhịp “{beat_title}”. "
                        f"Nhân vật phải phản ứng trước diễn biến liên quan đến: {idea}"
                    ),
                    shots=shots,
                )
            )

        return DirectorPlan(
            title=title,
            logline=self._logline(idea, options.genre, options.tone),
            genre=options.genre,
            tone=options.tone,
            target_minutes=options.target_minutes,
            characters=characters,
            scenes=scenes,
        )

    @staticmethod
    def _spread_beats(scene_count: int) -> list[tuple[int, str, str]]:
        beats = list(AIDirectorService.STORY_BEATS)
        if scene_count <= len(beats):
            indexes = [
                round(index * (len(beats) - 1) / max(1, scene_count - 1))
                for index in range(scene_count)
            ]
            return [beats[index] for index in indexes]

        result: list[tuple[int, str, str]] = []
        for index in range(scene_count):
            result.append(beats[index % len(beats)])
        return result

    @staticmethod
    def _character_description(idea: str, tone: str) -> str:
        return (
            f"Một nhân vật có mục tiêu rõ ràng nhưng mang xung đột nội tâm, "
            f"phù hợp sắc thái {tone.lower()}. Nhân vật bị cuốn vào câu chuyện: {idea}"
        )

    @staticmethod
    def _logline(idea: str, genre: str, tone: str) -> str:
        return (
            f"Một câu chuyện {genre.lower()} mang sắc thái {tone.lower()}, "
            f"trong đó {idea.rstrip('.')}."
        )

    @staticmethod
    def _location_for(scene_number: int, idea: str) -> str:
        locations = (
            "Không gian mở đầu gắn với đời sống nhân vật",
            "Địa điểm chuyển tiếp giàu chi tiết điện ảnh",
            "Không gian đối đầu có chiều sâu",
            "Địa điểm bí ẩn liên quan trực tiếp đến ý tưởng",
            "Không gian cao trào quy mô lớn",
        )
        return locations[(scene_number - 1) % len(locations)]

    @staticmethod
    def _time_for(scene_number: int) -> str:
        times = ("Bình minh", "Ban ngày", "Hoàng hôn", "Đêm", "Trước bình minh")
        return times[(scene_number - 1) % len(times)]

    @staticmethod
    def _create_veo_prompt(
        idea: str,
        genre: str,
        tone: str,
        act: int,
        beat_title: str,
        camera: str,
        shot_number: int,
    ) -> str:
        return (
            f"Create an 8-second cinematic shot for a {genre} film. "
            f"Story premise: {idea}. Act {act}, dramatic beat: {beat_title}. "
            f"Shot {shot_number}: {camera}. Tone: {tone}. "
            "Natural realistic movement, coherent anatomy, consistent recurring characters, "
            "cinematic production design, detailed environment, realistic physics, "
            "professional lighting, cinematic color grading, 24 fps, no text, no subtitles, "
            "no logos, no watermark."
        )

    @staticmethod
    def safe_project_name(title: str) -> str:
        cleaned = re.sub(r"[^\w\- ]+", "", title, flags=re.UNICODE).strip()
        return cleaned.replace(" ", "_") or "film_project"

    def save_plan(self, project_root: Path, plan: DirectorPlan) -> Path:
        project_dir = project_root / self.safe_project_name(plan.title)
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "images").mkdir(exist_ok=True)
        (project_dir / "audio").mkdir(exist_ok=True)
        (project_dir / "video").mkdir(exist_ok=True)
        (project_dir / "exports").mkdir(exist_ok=True)

        payload = asdict(plan)
        plan_path = project_dir / "director_plan.json"
        plan_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        screenplay_lines = [
            f"# {plan.title}",
            "",
            f"Logline: {plan.logline}",
            "",
        ]
        for scene in plan.scenes:
            screenplay_lines.extend(
                [
                    f"## {scene.title}",
                    f"Hồi: {scene.act}",
                    f"Bối cảnh: {scene.location} — {scene.time_of_day}",
                    f"Mục đích: {scene.purpose}",
                    f"Lời dẫn: {scene.narration}",
                    "",
                ]
            )
            for shot in scene.shots:
                screenplay_lines.extend(
                    [
                        f"- {shot.title}",
                        f"  Mô tả: {shot.description}",
                        f"  Camera: {shot.camera}",
                        f"  Veo: {shot.veo_prompt}",
                    ]
                )
            screenplay_lines.append("")

        (project_dir / "screenplay.md").write_text(
            "\n".join(screenplay_lines),
            encoding="utf-8",
        )
        return project_dir
