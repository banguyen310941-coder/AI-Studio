from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.transitions.render_plan import RenderClip, RenderPlan


class RenderJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class RenderJob:
    name: str
    output_path: str
    plan_data: dict[str, Any]
    id: str = field(default_factory=lambda: uuid4().hex)
    status: RenderJobStatus = RenderJobStatus.QUEUED
    progress: float = 0.0
    message: str = "Đang chờ"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: str | None = None
    finished_at: str | None = None

    @classmethod
    def from_plan(cls, plan: RenderPlan, output_path: str | Path, name: str = "") -> "RenderJob":
        target = Path(output_path).expanduser()
        return cls(name=name.strip() or target.stem or "Render", output_path=str(target), plan_data=plan.to_dict())

    def to_plan(self) -> RenderPlan:
        clips = [RenderClip(**item) for item in self.plan_data.get("clips", [])]
        return RenderPlan(
            clips=clips,
            transitions=list(self.plan_data.get("transitions", [])),
            filter_complex=str(self.plan_data.get("filter_complex", "")),
            output_label=str(self.plan_data.get("output_label", "")),
            audio_filter_complex=str(self.plan_data.get("audio_filter_complex", "")),
            audio_output_label=str(self.plan_data.get("audio_output_label", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RenderJob":
        payload = dict(data)
        try:
            payload["status"] = RenderJobStatus(str(payload.get("status", "queued")))
        except ValueError:
            payload["status"] = RenderJobStatus.QUEUED
        return cls(**payload)
