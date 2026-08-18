"""APScheduler 调度器封装，串联采集-存储-日志流程。"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .collectors import BaseCollector, CollectorResult, get_collector
from .models import (
    CollectorLog,
    CollectorTask,
    ExecStatus,
    ScheduleType,
    TaskStatus,
)
from .storages import BaseStorage, StorageResult, get_storage

log = logging.getLogger(__name__)


class CollectorScheduler:
    """采集调度器：负责注册任务、执行采集、调用存储、写日志。"""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sess_factory = session_factory
        self._scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
        self._running: set[str] = set()  # 正在执行的 task_id，防并发重叠
        self._lock = asyncio.Lock()
        self._started = False

    # ---------------- 生命周期 ----------------

    def start(self) -> None:
        if self._started:
            return
        self._scheduler.start()
        self._started = True
        log.info("CollectorScheduler started")

    def shutdown(self, wait: bool = True) -> None:
        if not self._started:
            return
        self._scheduler.shutdown(wait=wait)
        self._started = False
        log.info("CollectorScheduler shutdown")

    # ---------------- 内部：数据库操作 ----------------

    async def _save(self, *objs: Any) -> None:
        async with self._sess_factory() as sess:
            for o in objs:
                sess.add(o)
            await sess.commit()
            for o in objs:
                await sess.refresh(o)

    async def _update_task(self, task_id: str, **fields: Any) -> None:
        async with self._sess_factory() as sess:
            res = await sess.execute(
                select(CollectorTask).where(CollectorTask.id == task_id)
            )
            task = res.scalar_one_or_none()
            if not task:
                return
            for k, v in fields.items():
                setattr(task, k, v)
            await sess.commit()

    # ---------------- 调度触发器构造 ----------------

    @staticmethod
    def _build_trigger(schedule_type: ScheduleType, config: dict[str, Any]):
        if schedule_type == ScheduleType.CRON:
            cfg = dict(config or {})
            if "expression" in cfg:
                expr = cfg.pop("expression")
                # 支持 "*/5 * * * *" 这种 5 段式
                parts = str(expr).split()
                if len(parts) == 5:
                    minute, hour, day, month, day_of_week = parts
                    return CronTrigger(
                        minute=minute, hour=hour, day=day, month=month,
                        day_of_week=day_of_week, **cfg,
                    )
                if len(parts) == 6:
                    second, minute, hour, day, month, day_of_week = parts
                    return CronTrigger(
                        second=second, minute=minute, hour=hour, day=day,
                        month=month, day_of_week=day_of_week, **cfg,
                    )
                # 其他表达式直接让 CronTrigger 自己解析
                return CronTrigger.from_crontab(expr, **cfg)
            return CronTrigger(**cfg)
        if schedule_type == ScheduleType.INTERVAL:
            cfg = dict(config or {})
            # 允许 duration-like: {"seconds": 30}
            for k in ("weeks", "days", "hours", "minutes", "seconds"):
                if k in cfg:
                    cfg[k] = int(cfg[k])
            start_date = cfg.pop("start_date", None)
            end_date = cfg.pop("end_date", None)
            return IntervalTrigger(start_date=start_date, end_date=end_date, **cfg)
        if schedule_type == ScheduleType.DATE:
            cfg = dict(config or {})
            run_date = cfg.pop("run_date", None)
            if isinstance(run_date, str):
                try:
                    # 优先使用标准 ISO 格式
                    from datetime import datetime as _dt
                    run_date = _dt.fromisoformat(run_date.replace("Z", "+00:00"))
                except Exception:
                    # 回退: 让 apscheduler/dateutil 自己解析
                    pass
            return DateTrigger(run_date=run_date, **cfg)
        raise ValueError(f"Unknown schedule_type: {schedule_type}")

    # ---------------- 任务注册/取消 ----------------

    async def add_or_update_job(self, task: CollectorTask) -> None:
        """根据 task.schedule_* 配置，创建/更新 APScheduler job。"""
        if not self._started:
            self.start()

        job_id = task.apscheduler_job_id or f"collector:{task.id}"
        trigger = self._build_trigger(task.schedule_type, task.schedule_config)

        # 若该任务已经存在 job，先移除
        existing = self._scheduler.get_job(job_id)
        if existing is not None:
            try:
                self._scheduler.remove_job(job_id)
            except Exception as exc:  # noqa: BLE001
                log.warning("remove existing job %s failed: %s", job_id, exc)

        if not task.enabled:
            log.info("Task %s disabled; skip scheduling", task.id)
            await self._update_task(task.id, apscheduler_job_id=None, status=TaskStatus.STOPPED)
            return

        self._scheduler.add_job(
            self._execute_task_entrypoint,
            trigger=trigger,
            id=job_id,
            args=[task.id],
            kwargs={"trigger": "scheduler"},
            misfire_grace_time=60,
            coalesce=True,
            max_instances=1,
            replace_existing=True,
        )
        await self._update_task(
            task.id,
            apscheduler_job_id=job_id,
            status=TaskStatus.RUNNING if task.status != TaskStatus.ERROR else TaskStatus.RUNNING,
        )
        log.info("Scheduled task %s (job_id=%s, trigger=%s)", task.id, job_id, task.schedule_type)

    async def remove_job(self, task: CollectorTask) -> None:
        job_id = task.apscheduler_job_id or f"collector:{task.id}"
        try:
            self._scheduler.remove_job(job_id)
        except Exception as exc:  # noqa: BLE001
            log.warning("remove job %s failed: %s", job_id, exc)
        await self._update_task(task.id, apscheduler_job_id=None, status=TaskStatus.STOPPED)

    async def pause_job(self, task: CollectorTask) -> None:
        job_id = task.apscheduler_job_id
        if job_id:
            try:
                self._scheduler.pause_job(job_id)
            except Exception as exc:  # noqa: BLE001
                log.warning("pause job %s failed: %s", job_id, exc)
        await self._update_task(task.id, status=TaskStatus.PAUSED)

    async def resume_job(self, task: CollectorTask) -> None:
        job_id = task.apscheduler_job_id
        if job_id:
            try:
                self._scheduler.resume_job(job_id)
            except Exception as exc:  # noqa: BLE001
                log.warning("resume job %s failed: %s", job_id, exc)
        await self._update_task(task.id, status=TaskStatus.RUNNING)

    # ---------------- 执行核心 ----------------

    async def run_task_manually(self, task_id: str) -> CollectorLog:
        """手动触发一次执行，返回日志记录。"""
        return await self._execute_task_entrypoint(task_id, trigger="manual")

    async def _execute_task_entrypoint(self, task_id: str, *, trigger: str = "scheduler") -> CollectorLog:
        """APScheduler / 手动触发的实际执行入口。"""
        async with self._lock:
            if task_id in self._running:
                log.warning("Task %s is already running; skip this execution", task_id)
                # 返回空的占位日志，避免抛异常导致 APScheduler 告警
                return CollectorLog(task_id=task_id, trigger=trigger, status=ExecStatus.FAILED,
                                    error_message="Skip overlap execution")
            self._running.add(task_id)
        try:
            return await self._execute_task(task_id, trigger=trigger)
        finally:
            async with self._lock:
                self._running.discard(task_id)

    async def _execute_task(self, task_id: str, *, trigger: str) -> CollectorLog:
        # 加载任务配置
        async with self._sess_factory() as sess:
            res = await sess.execute(
                select(CollectorTask).where(CollectorTask.id == task_id)
            )
            task = res.scalar_one_or_none()
            if task is None:
                log.error("Task %s not found", task_id)
                raise RuntimeError(f"Task {task_id} not found")
            # 必要字段快照
            collector_type = task.collector_type.value if hasattr(task.collector_type, "value") else str(task.collector_type)
            collector_config = dict(task.collector_config or {})
            storage_type = task.storage_type.value if hasattr(task.storage_type, "value") else str(task.storage_type)
            storage_config = dict(task.storage_config or {})
            timeout = int(task.timeout or 30)

        log_record = CollectorLog(
            task_id=task_id,
            trigger=trigger,
            status=ExecStatus.RUNNING,
            started_at=datetime.now(),
        )
        async with self._sess_factory() as sess:
            sess.add(log_record)
            await sess.commit()
            await sess.refresh(log_record)
        log_id = int(log_record.id)  # type: ignore[arg-type]

        start_ts = time.monotonic()
        collector_result: CollectorResult | None = None
        storage_result: StorageResult | None = None
        error_message: str | None = None
        last_status: ExecStatus = ExecStatus.SUCCESS

        try:
            collector_cls = get_collector(collector_type)
            collector = collector_cls(collector_config)
            storage_cls = get_storage(storage_type)
            storage = storage_cls(storage_config)

            try:
                # 执行采集（带超时）
                try:
                    collector_result = await asyncio.wait_for(
                        collector.collect(), timeout=timeout,
                    )
                except asyncio.TimeoutError as exc:
                    raise TimeoutError(f"Collect timed out after {timeout}s") from exc

                # 执行存储（带超时）
                try:
                    storage_result = await asyncio.wait_for(
                        storage.store(collector_result.data, task_id=task_id, log_id=log_id),
                        timeout=timeout,
                    )
                except asyncio.TimeoutError as exc:
                    raise TimeoutError(f"Storage timed out after {timeout}s") from exc

                if not storage_result.success:
                    last_status = ExecStatus.FAILED
                    error_message = storage_result.message or "Storage failed"
            finally:
                try:
                    await collector.close()
                except Exception as exc:  # noqa: BLE001
                    log.warning("Collector close error task=%s: %s", task_id, exc)
                try:
                    await storage.close()
                except Exception as exc:  # noqa: BLE001
                    log.warning("Storage close error task=%s: %s", task_id, exc)
        except Exception as exc:  # noqa: BLE001
            log.exception("Task %s execution error", task_id)
            last_status = ExecStatus.FAILED
            error_message = f"{type(exc).__name__}: {exc}"

        duration_ms = int((time.monotonic() - start_ts) * 1000)

        # 写日志 & 汇总统计
        fields_update: dict[str, Any] = {
            "last_run_at": datetime.now(),
            "last_run_status": last_status,
            "last_run_duration_ms": duration_ms,
        }
        if last_status == ExecStatus.SUCCESS:
            fields_update["total_success_count"] = CollectorTask.total_success_count + 1
        else:
            fields_update["total_failed_count"] = CollectorTask.total_failed_count + 1
            fields_update["status"] = TaskStatus.ERROR

        async with self._sess_factory() as sess:
            res = await sess.execute(
                select(CollectorLog).where(CollectorLog.id == log_id)
            )
            log_obj = res.scalar_one_or_none()
            if log_obj is not None:
                log_obj.status = last_status
                log_obj.finished_at = datetime.now()
                log_obj.duration_ms = duration_ms
                log_obj.rows_count = collector_result.rows_count if collector_result else 0
                log_obj.error_message = error_message
                log_obj.storage_result = storage_result.as_dict() if storage_result else None
                log_obj.sample_data = collector_result.sample(3) if collector_result else None
                log_obj.raw_data_size = collector_result.raw_size if collector_result else 0
                sess.add(log_obj)

            task_obj = await sess.execute(
                select(CollectorTask).where(CollectorTask.id == task_id)
            )
            task_obj = task_obj.scalar_one_or_none()
            if task_obj is not None:
                for k, v in fields_update.items():
                    if isinstance(v, int) and k in ("total_success_count", "total_failed_count"):
                        # v 是 SQLAlchemy 表达式
                        pass
                    else:
                        setattr(task_obj, k, v)
                if last_status == ExecStatus.SUCCESS:
                    task_obj.total_success_count = (task_obj.total_success_count or 0) + 1
                else:
                    task_obj.total_failed_count = (task_obj.total_failed_count or 0) + 1
                sess.add(task_obj)
            await sess.commit()
            if log_obj is not None:
                await sess.refresh(log_obj)
                return log_obj
            return CollectorLog(
                task_id=task_id, trigger=trigger, status=last_status,
                started_at=datetime.now(), finished_at=datetime.now(),
                duration_ms=duration_ms, error_message=error_message,
            )

    # ---------------- 启动时恢复已启用任务 ----------------

    async def bootstrap(self) -> int:
        """从数据库加载所有 enabled 任务并加入调度器。返回注册数量。"""
        if not self._started:
            self.start()
        async with self._sess_factory() as sess:
            res = await sess.execute(
                select(CollectorTask).where(CollectorTask.enabled.is_(True))
            )
            tasks = res.scalars().all()
        for t in tasks:
            try:
                await self.add_or_update_job(t)
            except Exception as exc:  # noqa: BLE001
                log.exception("bootstrap task %s failed", t.id)
                try:
                    await self._update_task(t.id, status=TaskStatus.ERROR)
                except Exception:
                    pass
        return len(tasks)
