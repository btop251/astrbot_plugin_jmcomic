from __future__ import annotations

import shutil
from pathlib import Path

from .models import JmTaskRecord


class CacheManager:
    def __init__(self, cache_root: Path, keep_last: int) -> None:
        self.cache_root = cache_root
        self.keep_last = max(1, keep_last)
        self.cache_root.mkdir(parents=True, exist_ok=True)

    def build_task_cache_dir(self, task_id: str) -> Path:
        path = self.cache_root / task_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def prune(self, tasks: list[JmTaskRecord]) -> None:
        finished = [task for task in tasks if task.finished_at]
        finished.sort(key=lambda item: item.finished_at)
        keep_ids = {task.task_id for task in finished[-self.keep_last :]}

        for child in self.cache_root.iterdir():
            if not child.is_dir():
                continue
            if child.name in keep_ids:
                continue
            shutil.rmtree(child, ignore_errors=True)
