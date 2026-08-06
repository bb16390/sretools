"""数据采集模块的 HTTP REST API。

路由前缀：``/api/data-collection``

提供以下端点：

- ``GET    /workers``                       已注册 worker 列表
- ``GET    /workers/{worker_id}``           单个 worker 详情
- ``GET    /tasks``                         任务列表（可选 worker_id 过滤）
- ``GET    /tasks/{task_id}``               任务详情
- ``POST   /scheduled-tasks``               下发定时数据采集任务
- ``POST   /log-tasks``                     下发实时日志采集任务
- ``POST   /tasks/{task_id}/control``       控制任务（stop/pause/resume）
- ``DELETE /tasks/{task_id}``               删除任务记录
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from .dispatcher import get_default_dispatcher
from .models import (
    ControlTaskRequest,
    CreateLogTaskRequest,
    CreateScheduledTaskRequest,
    DispatchResult,
    TaskAction,
    TaskOut,
    TaskRecord,
    WorkerOut,
)
from .store import get_default_store

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/data-collection", tags=["data-collection"])


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def _record_to_out(record: TaskRecord) -> TaskOut:
    return TaskOut(
        task_id=record.task_id,
        worker_id=record.worker_id,
        task_kind=record.task_kind,
        status=record.status,
        config=record.config,
        created_at=record.created_at,
        updated_at=record.updated_at,
        last_dispatch_error=record.last_dispatch_error,
    )


def _get_servicer():
    """获取已绑定的 WorkerServiceServicer（可能为 None）。"""
    dispatcher = get_default_dispatcher()
    return dispatcher._servicer  # noqa: SLF001


def _list_workers_from_servicer() -> List[WorkerOut]:
    """从 servicer 的 workers 字典构造 worker 列表。"""
    servicer = _get_servicer()
    if servicer is None:
        return []
    out: List[WorkerOut] = []
    # ``workers`` 由 master/grpc/server.py 维护
    for worker_id, info in servicer.workers.items():  # type: ignore[attr-defined]
        out.append(
            WorkerOut(
                worker_id=worker_id,
                status=info.get("status", "unknown"),
                host=info.get("info", {}).get("host", ""),
                port=info.get("info", {}).get("port", 0),
                version=info.get("info", {}).get("version", ""),
                last_heartbeat=info.get("last_heartbeat", 0.0),
                online=servicer.is_worker_connected(worker_id),  # type: ignore[attr-defined]
            )
        )
    return out


# ---------------------------------------------------------------------------
# Worker 相关
# ---------------------------------------------------------------------------
@router.get("/workers", response_model=List[WorkerOut])
def list_workers():
    """列出所有已注册的 worker。"""
    return _list_workers_from_servicer()


@router.get("/workers/{worker_id}", response_model=WorkerOut)
def get_worker(worker_id: str):
    servicer = _get_servicer()
    if servicer is None:
        raise HTTPException(status_code=503, detail="gRPC servicer not initialized")
    info = servicer.workers.get(worker_id)  # type: ignore[attr-defined]
    if info is None:
        raise HTTPException(status_code=404, detail=f"worker {worker_id} not found")
    return WorkerOut(
        worker_id=worker_id,
        status=info.get("status", "unknown"),
        host=info.get("info", {}).get("host", ""),
        port=info.get("info", {}).get("port", 0),
        version=info.get("info", {}).get("version", ""),
        last_heartbeat=info.get("last_heartbeat", 0.0),
        online=servicer.is_worker_connected(worker_id),  # type: ignore[attr-defined]
    )


# ---------------------------------------------------------------------------
# 任务相关
# ---------------------------------------------------------------------------
@router.get("/tasks", response_model=List[TaskOut])
def list_tasks(worker_id: Optional[str] = Query(None)):
    """列出所有已下发任务，可按 worker_id 过滤。"""
    store = get_default_store()
    return [_record_to_out(r) for r in store.list(worker_id)]


@router.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(task_id: str):
    store = get_default_store()
    record = store.get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"task {task_id} not found")
    return _record_to_out(record)


@router.post("/scheduled-tasks", response_model=DispatchResult)
def create_scheduled_task(payload: CreateScheduledTaskRequest):
    """下发定时数据采集任务到指定 worker。"""
    dispatcher = get_default_dispatcher()
    if payload.config.task_kind.value not in {
        "database_collector",
        "prefect_database_collector",
    }:
        raise HTTPException(
            status_code=400,
            detail="scheduled task task_kind must be database_collector "
            "or prefect_database_collector",
        )
    return dispatcher.dispatch_scheduled_task(
        worker_id=payload.worker_id,
        config=payload.config,
        task_id=payload.task_id,
    )


@router.post("/log-tasks", response_model=DispatchResult)
def create_log_task(payload: CreateLogTaskRequest):
    """下发实时日志采集任务到指定 worker。"""
    dispatcher = get_default_dispatcher()
    return dispatcher.dispatch_log_task(
        worker_id=payload.worker_id,
        config=payload.config,
        task_id=payload.task_id,
    )


@router.post("/tasks/{task_id}/control", response_model=DispatchResult)
def control_task(task_id: str, payload: ControlTaskRequest):
    """控制任务：stop / pause / resume。"""
    if payload.task_id != task_id:
        raise HTTPException(
            status_code=400, detail="task_id in path and body must match"
        )
    dispatcher = get_default_dispatcher()
    return dispatcher.control_task(
        worker_id=payload.worker_id,
        task_id=task_id,
        action=payload.action,
    )


@router.delete("/tasks/{task_id}")
def delete_task(task_id: str):
    """删除任务记录（不会自动停止 worker 上运行的任务）。"""
    store = get_default_store()
    if not store.remove(task_id):
        raise HTTPException(status_code=404, detail=f"task {task_id} not found")
    return {"deleted": task_id}
