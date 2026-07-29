from __future__ import annotations

from dataclasses import dataclass
import os
import shutil


@dataclass(slots=True)
class ResourceSnapshot:
    cpu_load_percent: float
    available_disk_gb: float
    overloaded: bool


class ResourceMonitor:
    """Lightweight, dependency-free resource guard for background rendering."""

    def __init__(self, cpu_limit_percent: float = 92.0, min_free_disk_gb: float = 1.0) -> None:
        self.cpu_limit_percent = float(cpu_limit_percent)
        self.min_free_disk_gb = float(min_free_disk_gb)

    def snapshot(self, path: str = ".") -> ResourceSnapshot:
        cpu_count = max(1, os.cpu_count() or 1)
        try:
            one_minute_load = os.getloadavg()[0]
            cpu_load = max(0.0, min(100.0, one_minute_load / cpu_count * 100.0))
        except (AttributeError, OSError):
            cpu_load = 0.0
        try:
            available_disk = shutil.disk_usage(path).free / (1024 ** 3)
        except OSError:
            available_disk = float("inf")
        overloaded = cpu_load >= self.cpu_limit_percent or available_disk < self.min_free_disk_gb
        return ResourceSnapshot(cpu_load, available_disk, overloaded)
