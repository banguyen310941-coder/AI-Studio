from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


MIN_DURATION = 0.1
MAX_DURATION = 10.0
SUPPORTED_EASINGS = ("linear", "ease-in", "ease-out", "ease-in-out")


@dataclass(slots=True)
class TransitionModel:
    """Dữ liệu transition chuẩn hóa và tương thích timeline JSON schema 2."""

    id: str
    type: str
    from_clip_id: str
    to_clip_id: str
    duration: float = 1.0
    easing: str = "ease-in-out"
    enabled: bool = True

    def __post_init__(self) -> None:
        self.id = str(self.id).strip()
        self.type = str(self.type).strip()
        self.from_clip_id = str(self.from_clip_id).strip()
        self.to_clip_id = str(self.to_clip_id).strip()
        self.duration = round(max(MIN_DURATION, min(MAX_DURATION, float(self.duration))), 3)
        self.easing = self.easing if self.easing in SUPPORTED_EASINGS else "ease-in-out"
        self.enabled = bool(self.enabled)
        if not self.id:
            raise ValueError("Transition phải có id.")
        if not self.type:
            raise ValueError("Transition phải có type.")
        if not self.from_clip_id or not self.to_clip_id:
            raise ValueError("Transition phải tham chiếu hai clip.")
        if self.from_clip_id == self.to_clip_id:
            raise ValueError("Hai clip của transition phải khác nhau.")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "TransitionModel":
        return cls(
            id=str(value.get("id", "")),
            type=str(value.get("type", "cross_dissolve")),
            from_clip_id=str(value.get("from_clip_id", "")),
            to_clip_id=str(value.get("to_clip_id", "")),
            duration=float(value.get("duration", 1.0)),
            easing=str(value.get("easing", "ease-in-out")),
            enabled=bool(value.get("enabled", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
