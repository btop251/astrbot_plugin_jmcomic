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

    def cancel_task(self, task_id: str) -> JmTaskRecord:
        task = self.get_task(task_id)
        if task.status == "success" and not task.uploaded:
            task.cancel_requested = True
            task.status = "cancelled"
            task.summary = (task.summary or "").strip() + "；已请求停止，跳过后续上传"
            self.store.save_tasks(self.tasks)
            return task

        if task.status in {"success", "failed", "upload_failed", "cancelled"}:
            task.summary = task.summary or "任务已结束，无法再次停止。"
            self.store.save_tasks(self.tasks)
            return task

        task.cancel_requested = True
        if task.status == "queued":
            task.status = "cancelled"
            task.finished_at = datetime.now().isoformat(timespec="seconds")
            task.summary = "任务在排队阶段已取消。"
        else:
            task.summary = "已请求停止；如果底层下载已开始，将在当前阶段结束后停止后续上传。"
        self.store.save_tasks(self.tasks)
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
            if record.cancel_requested or record.status == "cancelled":
                record.status = "cancelled"
                record.finished_at = datetime.now().isoformat(timespec="seconds")
                record.summary = record.summary or "任务已取消。"
                self.store.save_tasks(self.tasks)
                return None

            record.status = "running"
            record.started_at = datetime.now().isoformat(timespec="seconds")
            self.store.save_tasks(self.tasks)

            result = None
            try:
                result = await asyncio.to_thread(func, *args, **kwargs)
                record.status = "cancelled" if record.cancel_requested else "success"
                record.finished_at = datetime.now().isoformat(timespec="seconds")
                if result:
                    record.save_dir = str(result.get("save_dir", ""))
                    record.summary = str(result.get("summary", ""))
                if record.cancel_requested:
                    record.summary = (record.summary or "").strip() + "；已按停止请求跳过后续上传"
            except Exception as e:  # pragma: no cover
                record.status = "failed"
                record.finished_at = datetime.now().isoformat(timespec="seconds")
                record.error_type = type(e).__name__
                record.error_message = str(e)
            finally:
                self.store.save_tasks(self.tasks)

            return result
