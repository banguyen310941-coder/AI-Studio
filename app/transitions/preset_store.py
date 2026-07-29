from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(slots=True)
class UserTransitionPreset:
    id: str
    name: str
    transition_type: str
    duration: float
    easing: str
    favorite: bool = False

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "UserTransitionPreset":
        preset_id = str(value.get("id", "")).strip()
        name = str(value.get("name", "")).strip()
        transition_type = str(value.get("transition_type", "cross_dissolve")).strip()
        easing = str(value.get("easing", "ease-in-out")).strip()
        if not preset_id or not name:
            raise ValueError("Preset phải có id và tên.")
        duration = max(0.1, min(10.0, float(value.get("duration", 1.0))))
        return cls(preset_id, name, transition_type, round(duration, 3), easing, bool(value.get("favorite", False)))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TransitionPresetStore:
    """Kho preset transition do người dùng tạo, lưu bằng JSON thuần."""

    SCHEMA_VERSION = 1

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path or Path.cwd() / "data" / "transition_presets.json")
        self._presets: dict[str, UserTransitionPreset] = {}
        self.load()

    def all(self, *, favorites_first: bool = True) -> tuple[UserTransitionPreset, ...]:
        values = list(self._presets.values())
        values.sort(key=lambda item: (not item.favorite if favorites_first else False, item.name.casefold()))
        return tuple(values)

    def get(self, preset_id: str) -> UserTransitionPreset | None:
        return self._presets.get(preset_id)

    def upsert(self, preset: UserTransitionPreset) -> None:
        self._presets[preset.id] = preset
        self.save()

    def remove(self, preset_id: str) -> bool:
        if preset_id not in self._presets:
            return False
        del self._presets[preset_id]
        self.save()
        return True

    def rename(self, preset_id: str, name: str) -> bool:
        preset = self.get(preset_id)
        if preset is None or not name.strip():
            return False
        preset.name = name.strip()
        self.save()
        return True

    def set_favorite(self, preset_id: str, favorite: bool) -> bool:
        preset = self.get(preset_id)
        if preset is None:
            return False
        preset.favorite = bool(favorite)
        self.save()
        return True

    def import_file(self, path: str | Path) -> int:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        items: Iterable[dict[str, Any]]
        if isinstance(raw, dict):
            items = raw.get("presets", [])
        elif isinstance(raw, list):
            items = raw
        else:
            raise ValueError("Tệp preset JSON không hợp lệ.")
        count = 0
        for item in items:
            preset = UserTransitionPreset.from_dict(dict(item))
            self._presets[preset.id] = preset
            count += 1
        self.save()
        return count

    def export_file(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "presets": [item.to_dict() for item in self.all(favorites_first=False)],
        }
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return target

    def load(self) -> None:
        self._presets = {}
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            for item in raw.get("presets", []):
                preset = UserTransitionPreset.from_dict(item)
                self._presets[preset.id] = preset
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            self._presets = {}

    def save(self) -> None:
        self.export_file(self.path)
