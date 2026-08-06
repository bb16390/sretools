"""任务下发器。

``TaskDispatcher`` 是数据采集模块的核心：把外部调用方提交的任务请求
转换成 gRPC ``TaskUpdate`` 消息，并通过 ``master/grpc/server.py`` 中
``WorkerServiceServicer`` 维护的 per-worker 消息队列推送到目标 worker。

worker 在线时立即下发；离线时把任务标记为 ``PENDING`` 暂存，等 worker
重新建立 Communicate 流后由 ``flush_pending_tasks`` 补发。
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, Optional

from .models import (
    DispatchResult,
    DispatchStatus,
    LogTaskConfig,
    ScheduledTaskConfig,
    TaskAction,
    TaskKind,
    TaskRecord,
    new_task_id,
)
from .store import TaskStore, get_default_store

logger = logging.getLogger(__name__)


class TaskDispatcher:
    """把数据采集任务下发给指定 worker。"""

    def __init__(self, store: Optional[TaskStore] = None) -> None:
        self.store = store or get_default_store()
        # servicer 引用由 master.grpc.server 注入，避免循环导入
        self._servicer = None

    # ------------------------------------------------------------------
    # servicer 绑定
    # ------------------------------------------------------------------
    def bind_servicer(self, servicer) -> None:
        """注入 ``WorkerServiceServicer`` 实例，用于访问 per-worker 队列。"""
        self._servicer = servicer
        logger.info("TaskDispatcher bound to WorkerServiceServicer")

    def _worker_online(self, worker_id: str) -> bool:
        """判断 worker 是否已建立 Communicate 流。"""
        if self._servicer is None:
            return False
        return self._servicer.is_worker_connected(worker_id)

    # ------------------------------------------------------------------
    # 下发：定时数据采集任务
    # ------------------------------------------------------------------
    def dispatch_scheduled_task(
        self,
        worker_id: str,
        config: ScheduledTaskConfig,
        task_id: Optional[str] = None,
    ) -> DispatchResult:
        task_id = task_id or new_task_id()
        worker_config = config.to_worker_config()
        record = TaskRecord(
            task_id=task_id,
            worker_id=worker_id,
            task_kind=config.task_kind,
            config=worker_config,
        )
        self.store.add(record)
        return self._push_task_update(
            record=record,
            action=TaskAction.CREATE,
            task_type=config.task_kind.value,
            worker_config=worker_config,
        )

    # ------------------------------------------------------------------
    # 下发：实时日志采集任务
    # ------------------------------------------------------------------
    def dispatch_log_task(
        self,
        worker_id: str,
        config: LogTaskConfig,
        task_id: Optional[str] = None,
    ) -> DispatchResult:
        task_id = task_id or new_task_id()
        worker_config = config.to_worker_config()
        record = TaskRecord(
            task_id=task_id,
            worker_id=worker_id,
            task_kind=TaskKind.LOG_COLLECTOR,
            config=worker_config,
        )
        self.store.add(record)
        return self._push_task_update(
            record=record,
            action=TaskAction.CREATE,
            task_type=TaskKind.LOG_COLLECTOR.value,
            worker_config=worker_config,
        )

    # ------------------------------------------------------------------
    # 控制任务
    # ------------------------------------------------------------------
    def control_task(
        self, worker_id: str, task_id: str, action: TaskAction
    ) -> DispatchResult:
        record = self.store.get(task_id)
        if record is None:
            return DispatchResult(
                success=False,
                message=f"task not found: {task_id}",
                worker_id=worker_id,
                task_id=task_id,
                worker_online=self._worker_online(worker_id),
            )
        if record.worker_id != worker_id:
            return DispatchResult(
                success=False,
                message=(
                    f"task {task_id} does not belong to worker {worker_id}"
                ),
                worker_id=worker_id,
                task_id=task_id,
                worker_online=self._worker_online(worker_id),
            )

        result = self._push_task_update(
            record=record,
            action=action,
            task_type=record.task_kind.value,
            worker_config=record.config,
        )
        # 同步本地状态
        if result.success and action == TaskAction.STOP:
            self.store.set_status(task_id, DispatchStatus.STOPPED)
        return result

    # ------------------------------------------------------------------
    # 内部：构造 TaskUpdate 并投递到 worker 的消息队列
    # ------------------------------------------------------------------
    def _push_task_update(
        self,
        record: TaskRecord,
        action: TaskAction,
        task_type: str,
        worker_config: Dict[str, Any],
    ) -> DispatchResult:
        worker_online = self._worker_online(record.worker_id)

        if self._servicer is None:
            # gRPC 服务尚未启动：暂存任务，等待 servicer 绑定后补发
            self.store.set_status(
                record.task_id,
                DispatchStatus.PENDING,
                error="servicer not bound yet",
            )
            logger.warning(
                "TaskDispatcher.servicer not bound; task %s queued as PENDING",
                record.task_id,
            )
            return DispatchResult(
                success=True,
                message="task queued (servicer not bound)",
                worker_id=record.worker_id,
                task_id=record.task_id,
                worker_online=False,
            )

        if not worker_online:
            # worker 离线：暂存任务，等 worker 上线后补发
            self.store.set_status(
                record.task_id,
                DispatchStatus.PENDING,
                error="worker offline",
            )
            logger.info(
                "worker %s offline; task %s queued as PENDING",
                record.worker_id,
                record.task_id,
            )
            return DispatchResult(
                success=True,
                message="task queued (worker offline, will dispatch on reconnect)",
                worker_id=record.worker_id,
                task_id=record.task_id,
                worker_online=False,
            )

        # worker 在线：构造 TaskUpdate 并投递
        pushed = self._servicer.push_task_update(
            worker_id=record.worker_id,
            task_id=record.task_id,
            action=action.value,
            task_type=task_type,
            config=worker_config,
        )
        if pushed:
            self.store.set_status(record.task_id, DispatchStatus.DISPATCHED, error=None)
            logger.info(
                "task %s dispatched to worker %s (action=%s)",
                record.task_id,
                record.worker_id,
                action.value,
            )
            return DispatchResult(
                success=True,
                message="task dispatched",
                worker_id=record.worker_id,
                task_id=record.task_id,
                worker_online=True,
            )

        self.store.set_status(
            record.task_id,
            DispatchStatus.PENDING,
            error="push_task_update returned False",
        )
        return DispatchResult(
            success=False,
            message="failed to push task update to worker stream",
            worker_id=record.worker_id,
            task_id=record.task_id,
            worker_online=False,
        )

    # ------------------------------------------------------------------
    # worker 重连后补发暂存任务
    # ------------------------------------------------------------------
    def flush_pending_tasks(self, worker_id: str) -> int:
        """worker 上线后，把所有 PENDING 任务补发。返回补发任务数。"""
        pending = [
            r
            for r in self.store.list(worker_id)
            if r.status == DispatchStatus.PENDING
        ]
        if not pending:
            return 0

        flushed = 0
        for record in pending:
            pushed = self._servicer.push_task_update(
                worker_id=record.worker_id,
                task_id=record.task_id,
                action=TaskAction.CREATE.value,
                task_type=record.task_kind.value,
                config=record.config,
            )
            if pushed:
                self.store.set_status(
                    record.task_id, DispatchStatus.DISPATCHED, error=None
                )
                flushed += 1
                logger.info(
                    "pending task %s flushed to worker %s",
                    record.task_id,
                    worker_id,
                )
            else:
                logger.warning(
                    "failed to flush pending task %s to worker %s",
                    record.task_id,
                    worker_id,
                )
        return flushed


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------
_default_dispatcher: Optional[TaskDispatcher] = None
_dispatcher_lock = threading.Lock()


def get_default_dispatcher() -> TaskDispatcher:
    global _default_dispatcher
    if _default_dispatcher is None:
        with _dispatcher_lock:
            if _default_dispatcher is None:
                _default_dispatcher = TaskDispatcher()
    return _default_dispatcher
