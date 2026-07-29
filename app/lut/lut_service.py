from __future__ import annotations

import json
import shutil
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

DEFAULT_LUT_SETTINGS: dict[str, Any] = {
    "enabled": False,
    "lut_id": "",
    "path": "",
    "name": "",
    "interpolation": "tetrahedral",
}

SUPPORTED_EXTENSIONS = {".cube", ".3dl", ".dat", ".m3d"}
SUPPORTED_INTERPOLATIONS = {"nearest", "trilinear", "tetrahedral"}


class LUTService:
    """Quản lý thư viện LUT và thiết lập LUT trên từng video clip."""

    def __init__(self, timeline_service, library_path: str | Path | None = None) -> None:
        self.timeline_service = timeline_service
        project_root = Path(__file__).resolve().parents[2]
        self.library_path = Path(library_path or project_root / "data" / "lut_library.json")
        self.storage_dir = self.library_path.parent / "luts"
        self.library_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def list_presets(self, favorites_first: bool = True) -> list[dict[str, Any]]:
        entries = self._load_library()
        valid = [entry for entry in entries if Path(entry.get("path", "")).is_file()]
        if len(valid) != len(entries):
            self._save_library(valid)
        return sorted(
            valid,
            key=lambda item: (
                0 if favorites_first and item.get("favorite") else 1,
                str(item.get("name", "")).lower(),
            ),
        )

    def import_lut(self, source: str | Path, name: str | None = None) -> dict[str, Any]:
        source_path = Path(source).expanduser().resolve()
        if not source_path.is_file():
            raise FileNotFoundError(f"Không tìm thấy LUT: {source_path}")
        if source_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError("Định dạng LUT chưa hỗ trợ. Dùng .cube, .3dl, .dat hoặc .m3d")
        if source_path.stat().st_size <= 0:
            raise ValueError("Tệp LUT trống")

        entries = self._load_library()
        existing = next(
            (item for item in entries if Path(item.get("source", "")) == source_path),
            None,
        )
        if existing and Path(existing.get("path", "")).is_file():
            return deepcopy(existing)

        lut_id = uuid.uuid4().hex
        destination = self.storage_dir / f"{lut_id}{source_path.suffix.lower()}"
        shutil.copy2(source_path, destination)
        entry = {
            "id": lut_id,
            "name": (name or source_path.stem).strip() or source_path.stem,
            "path": str(destination),
            "source": str(source_path),
            "favorite": False,
            "extension": source_path.suffix.lower(),
        }
        entries.append(entry)
        self._save_library(entries)
        return deepcopy(entry)

    def remove_lut(self, lut_id: str, delete_file: bool = True) -> bool:
        entries = self._load_library()
        target = next((item for item in entries if item.get("id") == lut_id), None)
        if target is None:
            return False
        self._save_library([item for item in entries if item.get("id") != lut_id])
        if delete_file:
            path = Path(target.get("path", ""))
            if path.is_file() and path.parent == self.storage_dir:
                path.unlink(missing_ok=True)
        return True

    def set_favorite(self, lut_id: str, favorite: bool) -> bool:
        entries = self._load_library()
        changed = False
        for entry in entries:
            if entry.get("id") == lut_id:
                entry["favorite"] = bool(favorite)
                changed = True
                break
        if changed:
            self._save_library(entries)
        return changed

    def export_library(self, destination: str | Path) -> Path:
        destination_path = Path(destination).expanduser()
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "luts": self.list_presets(favorites_first=False)}
        destination_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return destination_path

    def settings_for_clip(self, clip_id: str) -> dict[str, Any]:
        result = self.timeline_service.find_clip(clip_id)
        if result is None or result[0].get("type") != "video":
            return deepcopy(DEFAULT_LUT_SETTINGS)
        settings = deepcopy(DEFAULT_LUT_SETTINGS)
        raw = result[1].get("lut", {})
        if isinstance(raw, dict):
            settings.update(raw)
        return self._normalize(settings)

    def apply_to_clip(self, clip_id: str, lut_id: str, interpolation: str = "tetrahedral") -> bool:
        result = self.timeline_service.find_clip(clip_id)
        if result is None or result[0].get("type") != "video":
            return False
        entry = next((item for item in self.list_presets(False) if item.get("id") == lut_id), None)
        if entry is None:
            return False
        self.timeline_service.checkpoint()
        result[1]["lut"] = self._normalize({
            "enabled": True,
            "lut_id": entry["id"],
            "path": entry["path"],
            "name": entry["name"],
            "interpolation": interpolation,
        })
        return True

    def clear_clip(self, clip_id: str) -> bool:
        result = self.timeline_service.find_clip(clip_id)
        if result is None or result[0].get("type") != "video":
            return False
        self.timeline_service.checkpoint()
        result[1]["lut"] = deepcopy(DEFAULT_LUT_SETTINGS)
        return True

    @staticmethod
    def _normalize(settings: dict[str, Any]) -> dict[str, Any]:
        interpolation = str(settings.get("interpolation", "tetrahedral"))
        if interpolation not in SUPPORTED_INTERPOLATIONS:
            interpolation = "tetrahedral"
        path = str(settings.get("path", ""))
        enabled = bool(settings.get("enabled", False)) and bool(path)
        return {
            "enabled": enabled,
            "lut_id": str(settings.get("lut_id", "")),
            "path": path,
            "name": str(settings.get("name", "")),
            "interpolation": interpolation,
        }

    def _load_library(self) -> list[dict[str, Any]]:
        if not self.library_path.is_file():
            return []
        try:
            raw = json.loads(self.library_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        entries = raw.get("luts", raw) if isinstance(raw, dict) else raw
        return entries if isinstance(entries, list) else []

    def _save_library(self, entries: list[dict[str, Any]]) -> None:
        payload = {"version": 1, "luts": entries}
        self.library_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
