"""采集模块 HTTP API。

除了 fastapi_amis_admin 自动暴露的 CRUD 路由外，额外提供：
- GET    /api/collector/status                 调度器状态概览
- POST   /api/collector/bootstrap              从数据库重载已启用任务（启动时调用）
- POST   /api/collector/tasks/{id}/run         手动触发执行
- GET    /api/collector/tasks/{id}/logs        该任务的最近日志
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, func, select

from .core.models import CollectorLog, CollectorTask
from .core.scheduler import CollectorScheduler

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/collector", tags=["collector"])

_scheduler: CollectorScheduler | None = None
_session_factory: Any = None


def setup_collector_module(session_factory, scheduler: CollectorScheduler) -> None:
    """设置全局调度器和 DB session factory。"""
    global _scheduler, _session_factory
    _scheduler = scheduler
    _session_factory = session_factory


# ---------- 响应模型 ----------


class StatusOut(BaseModel):
    scheduler_started: bool
    total_tasks: int = 0
    enabled_tasks: int = 0
    total_success: int = 0
    total_failed: int = 0
    today_executions: int = 0


# ---------- 路由 ----------


@router.get("/status", response_model=StatusOut)
async def get_status():
    started = _scheduler is not None and _scheduler._started  # noqa: SLF001
    total_tasks = enabled_tasks = 0
    total_success = total_failed = today_exec = 0
    if _session_factory is not None:
        from datetime import datetime, time
        async with _session_factory() as sess:
            total_tasks = (await sess.execute(
                select(func.count(CollectorTask.id))
            )).scalar_one()
            enabled_tasks = (await sess.execute(
                select(func.count(CollectorTask.id)).where(CollectorTask.enabled.is_(True))
            )).scalar_one()
            total_success = (await sess.execute(
                select(func.coalesce(func.sum(CollectorTask.total_success_count), 0))
            )).scalar_one()
            total_failed = (await sess.execute(
                select(func.coalesce(func.sum(CollectorTask.total_failed_count), 0))
            )).scalar_one()
            today_start = datetime.combine(datetime.now().date(), time.min)
            today_exec = (await sess.execute(
                select(func.count(CollectorLog.id)).where(CollectorLog.started_at >= today_start)
            )).scalar_one()
    return StatusOut(
        scheduler_started=started,
        total_tasks=total_tasks,
        enabled_tasks=enabled_tasks,
        total_success=int(total_success or 0),
        total_failed=int(total_failed or 0),
        today_executions=int(today_exec or 0),
    )


@router.post("/bootstrap")
async def bootstrap():
    if _scheduler is None:
        raise HTTPException(status_code=503, detail="scheduler not initialized")
    count = await _scheduler.bootstrap()
    return {"scheduled": count}


@router.post("/tasks/{task_id}/run")
async def run_task_manually(task_id: str):
    if _scheduler is None:
        raise HTTPException(status_code=503, detail="scheduler not initialized")
    if _session_factory is None:
        raise HTTPException(status_code=503, detail="db session not initialized")
    async with _session_factory() as sess:
        t = (await sess.execute(
            select(CollectorTask).where(CollectorTask.id == task_id)
        )).scalar_one_or_none()
        if t is None:
            raise HTTPException(status_code=404, detail="task not found")
    log_rec = await _scheduler.run_task_manually(task_id)
    status_v = log_rec.status.value if hasattr(log_rec.status, "value") else str(log_rec.status)
    return {
        "log_id": log_rec.id,
        "task_id": log_rec.task_id,
        "status": status_v,
        "started_at": log_rec.started_at,
        "finished_at": log_rec.finished_at,
        "duration_ms": log_rec.duration_ms,
        "rows_count": log_rec.rows_count,
        "error_message": log_rec.error_message,
        "storage_result": log_rec.storage_result,
    }


@router.get("/tasks/{task_id}/logs")
async def list_task_logs(task_id: str, limit: int = 50):
    if _session_factory is None:
        raise HTTPException(status_code=503, detail="db session not initialized")
    async with _session_factory() as sess:
        q = (
            select(CollectorLog)
            .where(CollectorLog.task_id == task_id)
            .order_by(desc(CollectorLog.started_at))
            .limit(limit)
        )
        logs = (await sess.execute(q)).scalars().all()
    return [
        {
            "id": l.id,
            "trigger": l.trigger,
            "status": l.status.value if hasattr(l.status, "value") else str(l.status),
            "started_at": l.started_at,
            "finished_at": l.finished_at,
            "duration_ms": l.duration_ms,
            "rows_count": l.rows_count,
            "raw_size": l.raw_data_size,
            "error_message": (l.error_message or "")[:200],
            "sample_data": l.sample_data,
            "storage_result": l.storage_result,
        }
        for l in logs
    ]


@router.post("/shutdown")
async def shutdown_scheduler():
    if _scheduler is None:
        return {"ok": False, "msg": "scheduler not initialized"}
    try:
        _scheduler.shutdown(wait=False)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "msg": str(exc)}
    return {"ok": True}
