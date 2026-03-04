"""最小任务状态管理。

即使保持同步执行，也提供 task_id、状态流转和耗时记录，
为后续异步队列预留接口。当前使用内存实现。
"""

from __future__ import annotations

import time
import uuid
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Task:
    task_id: str
    agent_id: str
    status: str = "pending"  # pending | running | success | failed
    params_snapshot: dict[str, Any] = field(default_factory=dict)
    started_at: float | None = None
    ended_at: float | None = None
    duration_seconds: float | None = None
    error_message: str | None = None
    input_rows: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "status": self.status,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_seconds": self.duration_seconds,
            "error_message": self.error_message,
            "input_rows": self.input_rows,
        }


class TaskManager:
    """内存任务管理器。线程不安全（Streamlit 单线程足够）。"""

    def __init__(self):
        self._tasks: dict[str, Task] = {}

    def create_task(
        self,
        agent_id: str,
        params: dict[str, Any] | None = None,
        input_rows: int = 0,
    ) -> Task:
        task_id = uuid.uuid4().hex[:12]
        safe_params = {
            k: v for k, v in (params or {}).items()
            if not k.startswith("_")
        }
        task = Task(
            task_id=task_id,
            agent_id=agent_id,
            params_snapshot=safe_params,
            input_rows=input_rows,
        )
        self._tasks[task_id] = task
        logger.info("任务创建: %s (agent=%s)", task_id, agent_id)
        return task

    def start_task(self, task_id: str) -> Task:
        task = self._tasks[task_id]
        task.status = "running"
        task.started_at = time.time()
        logger.info("任务开始: %s", task_id)
        return task

    def complete_task(self, task_id: str) -> Task:
        task = self._tasks[task_id]
        task.status = "success"
        task.ended_at = time.time()
        if task.started_at:
            task.duration_seconds = round(task.ended_at - task.started_at, 2)
        logger.info("任务成功: %s (%.2fs)", task_id, task.duration_seconds or 0)
        return task

    def fail_task(self, task_id: str, error: str) -> Task:
        task = self._tasks[task_id]
        task.status = "failed"
        task.ended_at = time.time()
        task.error_message = error
        if task.started_at:
            task.duration_seconds = round(task.ended_at - task.started_at, 2)
        logger.warning("任务失败: %s - %s", task_id, error)
        return task

    def get_task(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[Task]:
        return list(self._tasks.values())


task_manager = TaskManager()
