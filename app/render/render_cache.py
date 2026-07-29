from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class CacheRecord:
    key: str
    output_path: str
    completed: bool = True


class RenderCache:
    """Persistent cache that detects identical render plans and existing outputs."""

    def __init__(self, path: str | Path = "data/render_cache.json") -> None:
        self.path = Path(path)
        self.records: dict[str, CacheRecord] = {}
        self.load()

    @staticmethod
    def key_for(plan_data: dict[str, Any], output_path: str = "") -> str:
        payload = {"plan": plan_data, "output": str(Path(output_path).expanduser())}
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def lookup(self, plan_data: dict[str, Any], output_path: str) -> CacheRecord | None:
        key = self.key_for(plan_data, output_path)
        record = self.records.get(key)
        if record and record.completed and Path(record.output_path).expanduser().exists():
            return record
        return None

    def remember(self, plan_data: dict[str, Any], output_path: str) -> CacheRecord:
        key = self.key_for(plan_data, output_path)
        record = CacheRecord(key=key, output_path=str(Path(output_path).expanduser()), completed=True)
        self.records[key] = record
        self.save()
        return record

    def clear_missing(self) -> int:
        before = len(self.records)
        self.records = {
            key: record for key, record in self.records.items()
            if Path(record.output_path).expanduser().exists()
        }
        self.save()
        return before - len(self.records)

    def save(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = [{"key": record.key, "output_path": record.output_path, "completed": record.completed} for record in self.records.values()]
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)
        return self.path

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                self.records = {
                    str(item["key"]): CacheRecord(**item)
                    for item in data if isinstance(item, dict) and item.get("key")
                }
        except (OSError, ValueError, TypeError, KeyError):
            self.records = {}
