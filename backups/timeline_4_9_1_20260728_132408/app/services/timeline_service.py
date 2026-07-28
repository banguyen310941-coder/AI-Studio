from __future__ import annotations

import json
from pathlib import Path

from app.models.timeline import TimelineDocument


class TimelineService:
    FILE_NAME = "timeline.json"

    def load(self, path: str | Path) -> TimelineDocument:
        target = self._resolve(path)
        if not target.exists():
            return TimelineDocument()
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ValueError(f"Không thể đọc timeline: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError("timeline.json không đúng định dạng.")
        return TimelineDocument.from_dict(data)

    def save(self, path: str | Path, document: TimelineDocument) -> Path:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(
            json.dumps(document.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(target)
        return target

    @classmethod
    def _resolve(cls, path: str | Path) -> Path:
        target = Path(path).expanduser()
        return target / cls.FILE_NAME if target.suffix.lower() != ".json" else target
