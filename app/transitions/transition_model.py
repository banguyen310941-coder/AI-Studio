from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import uuid


@dataclass(slots=True)
class TransitionModel:
    """Dữ liệu transition độc lập với giao diện và timeline canvas."""

    from_clip_id: str
    to_clip_id: str
    transition_type: str = "cross_dissolve"
    duration: float = 1.0
    easing: str = "ease-in-out"
    enabled: bool = True
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        if not self.from_clip_id or not self.to_clip_id:
            raise ValueError("Transition cần đủ clip trước và clip sau.")
        if self.from_clip_id == self.to_clip_id:
            raise ValueError("Hai clip của transition phải khác nhau.")
        self.duration = round(max(0.1, min(10.0, float(self.duration))), 3)
        self.enabled = bool(self.enabled)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.transition_type,
            "from_clip_id": self.from_clip_id,
            "to_clip_id": self.to_clip_id,
            "duration": self.duration,
            "easing": self.easing,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TransitionModel":
        return cls(
            id=str(value.get("id") or uuid.uuid4()),
            transition_type=str(value.get("type", "cross_dissolve")),
            from_clip_id=str(value.get("from_clip_id", "")),
            to_clip_id=str(value.get("to_clip_id", "")),
            duration=float(value.get("duration", 1.0)),
            easing=str(value.get("easing", "ease-in-out")),
            enabled=bool(value.get("enabled", True)),
        )
