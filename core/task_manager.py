from __future__ import annotations

import asyncio
from datetime import datetime
from uuid import uuid4

from ..store.state_store import StateStore
from .exceptions import JmTaskNotFoundError
from .models import JmTaskRecord


class TaskManager:
    def __init__(self, store: StateStore, max_concurrent_tasks: int) -> None:
        self.store = store
        self.max_concurrent_tasks = max(1, max_concurrent_tasks)
        self.semaphore = asyncio.Semaphore(self.max_concurrent_tasks)
        self.tasks = self.store.load_tasks()

    def list_tasks(self) -> list[JmTaskRecord]:
        return list(self.tasks.values())[-20:]

    def get_task(self, task_id: str) -> JmTaskRecord:
        task = self.tasks.get(task_id)
        if task is None:
            raise JmTaskNotFoundError(f"未找到任务: {task_id}")
        return task

    def create_task(
        self,
        task_type: str,
        target_id: str,
        requested_by: str,
        request_origin: str,
        output_format: str = "",
    ) -> JmTaskRecord:
        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"
        record = JmTaskRecord(
            task_id=task_id,
            task_type=task_type,
            target_id=target_id,
            requested_by=requested_by,
            request_origin=request_origin,
            output_format=output_format,
        )
        self.tasks[task_id] = record
        self.store.save_tasks(self.tasks)
        return record

    async def run_task(self, record: JmTaskRecord, func, *args, **kwargs):
        async with self.semaphore:
            record.status = "running"
            record.started_at = datetime.now().isoformat(timespec="seconds")
            self.store.save_tasks(self.tasks)

            result = None
            try:
                result = await asyncio.to_thread(func, *args, **kwargs)
                record.status = "success"
                record.finished_at = datetime.now().isoformat(timespec="seconds")
                record.save_dir = str(result.get("save_dir", ""))
                record.summary = str(result.get("summary", ""))
            except Exception as e:  # pragma: no cover
                record.status = "failed"
                record.finished_at = datetime.now().isoformat(timespec="seconds")
                record.error_type = type(e).__name__
                record.error_message = str(e)
            finally:
                self.store.save_tasks(self.tasks)

            return result
