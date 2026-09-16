import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, List

from croniter import croniter

from common.transform_runner import apply_transform
from worker.adapter.base import AdapterManager
from worker.scheduler.base_task import BaseTask, ExecutionMode, TaskStatus

logger = logging.getLogger(__name__)

_ADAPTER_CLASS_MAP: Dict[str, type] = {}


def _get_adapter_class(adapter_type: str):
    """Map adapter_type string to the actual adapter class."""
    if adapter_type not in _ADAPTER_CLASS_MAP:
        if adapter_type == "sql":
            from worker.adapter.sql_adapter import SqlAdapter
            _ADAPTER_CLASS_MAP["sql"] = SqlAdapter
        elif adapter_type == "clickhouse":
            from worker.adapter.clickhouse_adapter import ClickHouseAdapter
            _ADAPTER_CLASS_MAP["clickhouse"] = ClickHouseAdapter
        elif adapter_type == "influxdb":
            from worker.adapter.influxdb_adapter import InfluxDBAdapter
            _ADAPTER_CLASS_MAP["influxdb"] = InfluxDBAdapter
        elif adapter_type == "redis":
            from worker.adapter.redis_adapter import RedisAdapter
            _ADAPTER_CLASS_MAP["redis"] = RedisAdapter
        else:
            raise ValueError(f"Unknown adapter_type: {adapter_type}")
    return _ADAPTER_CLASS_MAP[adapter_type]


def _get_query_method(adapter):
    """Determine the query execution method based on adapter capabilities."""
    if hasattr(adapter, 'execute') and callable(adapter.execute):
        return adapter.execute
    elif hasattr(adapter, 'query') and callable(adapter.query):
        return adapter.query
    else:
        raise AttributeError(
            f"Adapter {type(adapter).__name__} has no execute or query method"
        )


class DatabaseCollectorTask(BaseTask):
    """Cron-based database query collector task.

    Config fields:
        cron_expression (required): Cron expression for scheduling.
        adapter_type (required): One of "sql", "clickhouse", "influxdb", "http", "redis".
        adapter_config (required): Dict of kwargs for the adapter constructor.
        query or queries (required): SQL string or list of SQL strings.
    """

    def __init__(
        self,
        task_type: str,
        config: Dict[str, Any],
        task_id: str = None,
        trade_day_cache=None,
    ):
        super().__init__(task_type, config, task_id)
        self._trade_day_cache = trade_day_cache
        self._validate_config()

    def _validate_config(self):
        """Validate that all required config fields are present."""
        required_fields = ["cron_expression", "adapter_type", "adapter_config"]
        for field in required_fields:
            if field not in self.config:
                raise ValueError(f"Missing required config field: {field}")
        if "query" not in self.config and "queries" not in self.config:
            raise ValueError("Missing required config field: query or queries")

    def _default_execution_mode(self) -> ExecutionMode:
        return ExecutionMode.THREAD

    def _run(self):
        """Core cron-based scheduling and query execution loop."""
        cron_expression = self.config["cron_expression"]
        adapter_type = self.config["adapter_type"]
        adapter_config = self.config["adapter_config"]

        queries = self.config.get("queries")
        if queries is None:
            queries = [self.config["query"]]
        elif isinstance(queries, str):
            queries = [queries]

        adapter_cls = _get_adapter_class(adapter_type)

        base_time = datetime.now()
        cron = croniter(cron_expression, base_time)
        next_time = cron.get_next(datetime)

        logger.info(
            f"DatabaseCollectorTask[{self.task_id}] started. Cron: {cron_expression}, Next run: {next_time}",
        )

        loop = asyncio.new_event_loop()

        try:
            while not self._stop_event.is_set():
                if self._pause_event is not None and not self._pause_event.is_set():
                    self._pause_event.wait(timeout=1)
                    continue

                now = datetime.now()
                if now >= next_time:
                    # Check trade day if configured
                    trade_day_only = self.config.get("trade_day_only", False)
                    if trade_day_only and self._trade_day_cache:
                        if not self._trade_day_cache.is_trade_day(now.date()):
                            logger.info(
                                f"DatabaseCollectorTask[{self.task_id}] skipped: not a trade day",
                            )
                            cron = croniter(cron_expression, now)
                            next_time = cron.get_next(datetime)
                            self._stop_event.wait(timeout=1)
                            continue

                    start_time = time.time()
                    try:
                        adapter = AdapterManager.get_or_create(adapter_cls, adapter_config)
                        query_method = _get_query_method(adapter)

                        results = []
                        for query in queries:
                            result = loop.run_until_complete(query_method(query))
                            results.append(result)

                        data = results[0] if len(results) == 1 else results

                        # 采集成功：计算 raw_rows_count 并（可选）应用 transform_script
                        raw_rows_count = len(data) if isinstance(data, list) else 1
                        extra: Dict[str, str] = {"raw_rows_count": str(raw_rows_count)}

                        transform_script = self.config.get("transform_script", "")
                        # transform 失败信息：(错误消息, 错误类型)；非空时跳过 success 上报
                        transform_failed = None
                        if transform_script:
                            ok, transformed, err_type = apply_transform(
                                transform_script, data, self.config
                            )
                            if not ok:
                                transform_failed = (transformed, err_type)
                            else:
                                data = transformed
                                if isinstance(transformed, list):
                                    extra["transformed_rows"] = str(len(transformed))
                                else:
                                    extra["transformed_rows"] = str(raw_rows_count)

                        duration_ms = (time.time() - start_time) * 1000
                        if transform_failed is not None:
                            # 转换失败：上报 failed，保留 raw_rows_count，附加 error_kind
                            err_msg, err_type = transform_failed
                            extra["error_kind"] = "transform_error"
                            self._notify_status(
                                "failed",
                                result=f"transform error: {err_msg}",
                                duration_ms=duration_ms,
                                extra=extra,
                            )
                            logger.error(
                                "DatabaseCollectorTask[%s] transform failed: %s (%s)",
                                self.task_id, err_msg, err_type,
                            )
                        else:
                            self._notify_status(
                                "success",
                                result=data,
                                duration_ms=duration_ms,
                                extra=extra,
                            )
                            logger.info(
                                f"DatabaseCollectorTask[{self.task_id}] query executed successfully. Duration: {duration_ms:.02f}ms",
                            )
                    except Exception as e:
                        duration_ms = (time.time() - start_time) * 1000
                        self._notify_status("failed", result=str(e), duration_ms=duration_ms)
                        logger.error(
                            f"DatabaseCollectorTask[{self.task_id}] query failed: {e}",
                        )

                    cron = croniter(cron_expression, now)
                    next_time = cron.get_next(datetime)
                    logger.debug(
                        f"DatabaseCollectorTask[{self.task_id}] next run: {next_time}",
                    )

                self._stop_event.wait(timeout=1)
        finally:
            loop.close()
            logger.info(f"DatabaseCollectorTask[{self.task_id}] stopped.") 
