"""基于 prefect 的数据库采集任务。

本模块复用 ``DatabaseCollectorTask`` 的配置契约（cron_expression /
adapter_type / adapter_config / query / queries / trade_day_only），
但用 `prefect <https://docs.prefect.io>`_ 的 ``@flow`` / ``@task`` 装饰器
组织执行逻辑：

- ``query_database`` 是一个 prefect task，封装单次数据库查询；
- ``database_collection_flow`` 是一个 prefect flow，串联「交易日校验 → 执行查询 → 上报状态」；
- ``PrefectDatabaseCollectorTask`` 是 ``BaseTask`` 子类，负责：
    * 维持 cron 调度循环（与 ``DatabaseCollectorTask`` 一致）
    * 在事件循环中调用 prefect flow
    * 处理 stop / pause 信号

prefect 在 worker 进程内以 **ephemeral** 模式运行（无需独立 prefect server），
通过 ``prefect.flow`` 的同步调用入口 ``flow(...)`` 触发执行，
任务的状态/日志会被 prefect 记录到本地，同时通过 ``_notify_status``
回传给 worker 的 ``TaskScheduler``。

如果 prefect 未安装，导入本模块时会抛出 ``ImportError``，调用方应在注册
任务类型时捕获并降级到 ``DatabaseCollectorTask``。
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from croniter import croniter

from worker.adapter.base import AdapterManager
from worker.scheduler.base_task import BaseTask, ExecutionMode
from worker.scheduler.tasks.database_collector_task import (
    _get_adapter_class,
    _get_query_method,
)

logger = logging.getLogger(__name__)

try:
    from prefect import flow, task  # type: ignore

    HAS_PREFECT = True
except ImportError:  # pragma: no cover - 仅在 prefect 缺失时触发
    HAS_PREFECT = False

    def flow(*_args, **_kwargs):  # type: ignore
        """prefect 缺失时的占位装饰器。"""

        def _wrap(fn):
            return fn

        return _wrap

    def task(*_args, **_kwargs):  # type: ignore
        """prefect 缺失时的占位装饰器。"""

        def _wrap(fn):
            return fn

        return _wrap


# ---------------------------------------------------------------------------
# prefect task / flow 定义
# ---------------------------------------------------------------------------
@task(name="query-database")
def _query_database_task(
    adapter_cls_name: str,
    adapter_config: Dict[str, Any],
    query: str,
) -> Any:
    """prefect task：在事件循环中执行一次数据库查询。

    prefect task 必须是同步函数（在 prefect 2.x 中），因此通过
    ``asyncio.run`` 调用异步 adapter 方法。
    """
    adapter_cls = _get_adapter_class(adapter_cls_name)
    adapter = AdapterManager.get_or_create(adapter_cls, adapter_config)
    query_method = _get_query_method(adapter)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 不应进入此分支（prefect task 在独立线程执行）
            future = asyncio.run_coroutine_threadsafe(query_method(query), loop)
            return future.result(timeout=60)
    except RuntimeError:
        # 没有正在运行的事件循环，使用 asyncio.run
        pass

    return asyncio.run(query_method(query))


@task(name="check-trade-day")
def _check_trade_day_task(
    trade_day_cache,
    target_date: datetime,
) -> bool:
    """prefect task：判断目标日期是否为交易日。"""
    if trade_day_cache is None:
        return True
    return trade_day_cache.is_trade_day(target_date.date())


@flow(name="prefect-database-collection-flow")
def database_collection_flow(
    adapter_cls_name: str,
    adapter_config: Dict[str, Any],
    queries: List[str],
    trade_day_only: bool,
    trade_day_cache,
) -> Dict[str, Any]:
    """prefect flow：串联交易日校验与查询执行。

    返回 ``{"skipped": bool, "results": [...]}``。
    """
    now = datetime.now()
    if trade_day_only:
        is_trade_day = _check_trade_day_task(trade_day_cache, now)
        if not is_trade_day:
            logger.info("prefect flow: skipped (not a trade day)")
            return {"skipped": True, "results": []}

    results: List[Any] = []
    for query in queries:
        result = _query_database_task(adapter_cls_name, adapter_config, query)
        results.append(result)
    return {"skipped": False, "results": results}


# ---------------------------------------------------------------------------
# BaseTask 实现
# ---------------------------------------------------------------------------
class PrefectDatabaseCollectorTask(BaseTask):
    """基于 prefect 的定时数据库采集任务。

    Config 字段与 ``DatabaseCollectorTask`` 完全一致：

        cron_expression (required): Cron 表达式
        adapter_type (required): sql / clickhouse / influxdb / http / redis / kafka
        adapter_config (required): adapter 构造参数
        query / queries (required): SQL 字符串或列表
        trade_day_only (optional): 仅在交易日执行，默认 False
    """

    def __init__(
        self,
        task_type: str,
        config: Dict[str, Any],
        task_id: str = None,
        trade_day_cache=None,
    ):
        if not HAS_PREFECT:
            raise ImportError(
                "prefect is not installed; "
                "install with `pip install prefect` or use DatabaseCollectorTask"
            )
        super().__init__(task_type, config, task_id)
        self._trade_day_cache = trade_day_cache
        self._validate_config()

    def _validate_config(self) -> None:
        required_fields = ["cron_expression", "adapter_type", "adapter_config"]
        for field in required_fields:
            if field not in self.config:
                raise ValueError(f"Missing required config field: {field}")
        if "query" not in self.config and "queries" not in self.config:
            raise ValueError("Missing required config field: query or queries")

    def _default_execution_mode(self) -> ExecutionMode:
        # prefect flow 内部会管理自己的执行线程，外层用 THREAD 即可
        return ExecutionMode.THREAD

    def _build_queries(self) -> List[str]:
        queries = self.config.get("queries")
        if queries is None:
            queries = [self.config["query"]]
        elif isinstance(queries, str):
            queries = [queries]
        return list(queries)

    def _run(self) -> None:
        """cron 调度循环：到点时触发 prefect flow。"""
        cron_expression = self.config["cron_expression"]
        adapter_type = self.config["adapter_type"]
        adapter_config = self.config["adapter_config"]
        trade_day_only = self.config.get("trade_day_only", False)
        queries = self._build_queries()

        base_time = datetime.now()
        cron = croniter(cron_expression, base_time)
        next_time = cron.get_next(datetime)

        logger.info(
            "PrefectDatabaseCollectorTask[%s] started. Cron: %s, Next run: %s",
            self.task_id, cron_expression, next_time,
        )

        while not self._stop_event.is_set():
            if self._pause_event is not None and not self._pause_event.is_set():
                self._pause_event.wait(timeout=1)
                continue

            now = datetime.now()
            if now >= next_time:
                start_time = time.time()
                try:
                    flow_result = database_collection_flow(
                        adapter_cls_name=adapter_type,
                        adapter_config=adapter_config,
                        queries=queries,
                        trade_day_only=trade_day_only,
                        trade_day_cache=self._trade_day_cache,
                    )

                    duration_ms = (time.time() - start_time) * 1000
                    if flow_result.get("skipped"):
                        self._notify_status(
                            "success",
                            result="skipped (not a trade day)",
                            duration_ms=duration_ms,
                        )
                        logger.info(
                            "PrefectDatabaseCollectorTask[%s] skipped: not a trade day",
                            self.task_id,
                        )
                    else:
                        data = flow_result["results"]
                        if len(data) == 1:
                            data = data[0]
                        self._notify_status(
                            "success", result=data, duration_ms=duration_ms
                        )
                        logger.info(
                            "PrefectDatabaseCollectorTask[%s] flow executed. Duration: %.2fms",
                            self.task_id, duration_ms,
                        )
                except Exception as e:
                    duration_ms = (time.time() - start_time) * 1000
                    self._notify_status(
                        "failed", result=str(e), duration_ms=duration_ms
                    )
                    logger.error(
                        "PrefectDatabaseCollectorTask[%s] flow failed: %s",
                        self.task_id, e, exc_info=True,
                    )

                cron = croniter(cron_expression, now)
                next_time = cron.get_next(datetime)
                logger.debug(
                    "PrefectDatabaseCollectorTask[%s] next run: %s",
                    self.task_id, next_time,
                )

            self._stop_event.wait(timeout=1)

        logger.info("PrefectDatabaseCollectorTask[%s] stopped.", self.task_id)
