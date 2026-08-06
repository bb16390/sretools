"""数据采集任务的内存存储。

负责维护 master 端已下发任务的元数据，并对外暴露简单的 CRUD 接口。
存储层刻意保持内存实现（与 ``master/grpc/server.py`` 中的 ``workers`` 字典
风格一致），后续可平滑替换为 SQLModel 持久化。
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from .models import DispatchStatus, TaskRecord


class TaskStore:
    """线程安全的任务记录存储。"""

    def __init__(self) -> None:
        self._tasks: Dict[str, TaskRecord] = {}
        self._lock = threading.Lock()

    def add(self, record: TaskRecord) -> TaskRecord:
        with self._lock:
            self._tasks[record.task_id] = record
        return record

    def get(self, task_id: str) -> Optional[TaskRecord]:
        with self._lock:
            return self._tasks.get(task_id)

    def list(self, worker_id: Optional[str] = None) -> List[TaskRecord]:
        with self._lock:
            records = list(self._tasks.values())
        if worker_id is not None:
            records = [r for r in records if r.worker_id == worker_id]
        return records

    def update(self, task_id: str, **changes) -> Optional[TaskRecord]:
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                return None
            for key, value in changes.items():
                if hasattr(record, key):
                    setattr(record, key, value)
            record.touch()
            return record

    def remove(self, task_id: str) -> bool:
        with self._lock:
            return self._tasks.pop(task_id, None) is not None

    def set_status(
        self, task_id: str, status: DispatchStatus, error: Optional[str] = None
    ) -> Optional[TaskRecord]:
        return self.update(task_id, status=status, last_dispatch_error=error)


# ---------------------------------------------------------------------------
# 全局单例（与 ``master/grpc/server.py`` 共享同一份状态）
# ---------------------------------------------------------------------------
_default_store: Optional[TaskStore] = None
_store_lock = threading.Lock()


def get_default_store() -> TaskStore:
    """获取全局默认 TaskStore 单例。"""
    global _default_store
    if _default_store is None:
        with _store_lock:
            if _default_store is None:
                _default_store = TaskStore()
    return _default_store


def set_default_store(store: TaskStore) -> None:
    """替换全局默认 TaskStore（主要用于测试注入）。"""
    global _default_store
    with _store_lock:
        _default_store = store
