from __future__ import annotations

import json
from pathlib import Path

from app.models.timeline import TimelineDocument


class TimelineService:
    FILE_NAME = "timeline.json"

    def load(self, path: str | Path) -> TimelineDocument:
        target = self._normalize(path)
        if not target.exists():
            return TimelineDocument()
        data = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("timeline.json phải chứa một JSON object")
        return TimelineDocument.from_dict(data)

    def save(self, path: str | Path, document: TimelineDocument) -> Path:
        target = self._normalize(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(target.suffix + ".tmp")
        temp.write_text(json.dumps(document.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(target)
        return target

    def _normalize(self, path: str | Path) -> Path:
        target = Path(path).expanduser()
        return target / self.FILE_NAME if target.is_dir() or target.suffix.lower() != ".json" else target
