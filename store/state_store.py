from __future__ import annotations

import json
from pathlib import Path

from ..core.models import JmTaskRecord


class StateStore:
    def __init__(self, state_dir: Path, history_limit: int) -> None:
        self.state_dir = state_dir
        self.history_limit = history_limit
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.tasks_path = self.state_dir / "tasks.json"

    def load_tasks(self) -> dict[str, JmTaskRecord]:
        if not self.tasks_path.exists():
            return {}
        data = json.loads(self.tasks_path.read_text(encoding="utf-8"))
        return {task_id: JmTaskRecord.from_dict(item) for task_id, item in data.items()}

    def save_tasks(self, tasks: dict[str, JmTaskRecord]) -> None:
        items = list(tasks.items())[-self.history_limit :]
        data = {task_id: task.to_dict() for task_id, task in items}
        self.tasks_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
