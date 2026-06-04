import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, List

from croniter import croniter

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
        elif adapter_type == "http":
            from worker.adapter.http_adapter import HttpAdapter
            _ADAPTER_CLASS_MAP["http"] = HttpAdapter
        elif adapter_type == "redis":
            from worker.adapter.redis_adapter import RedisAdapter
            _ADAPTER_CLASS_MAP["redis"] = RedisAdapter
        elif adapter_type == "kafka":
            from worker.adapter.kafka_adapter import KafkaAdapter
            _ADAPTER_CLASS_MAP["kafka"] = KafkaAdapter
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
            "DatabaseCollectorTask[%s] started. Cron: %s, Next run: %s",
            self.task_id, cron_expression, next_time,
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
                                "DatabaseCollectorTask[%s] skipped: not a trade day",
                                self.task_id,
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

                        duration_ms = (time.time() - start_time) * 1000
                        self._notify_status("success", result=data, duration_ms=duration_ms)
                        logger.info(
                            "DatabaseCollectorTask[%s] query executed successfully. Duration: %.2fms",
                            self.task_id, duration_ms,
                        )
                    except Exception as e:
                        duration_ms = (time.time() - start_time) * 1000
                        self._notify_status("failed", result=str(e), duration_ms=duration_ms)
                        logger.error(
                            "DatabaseCollectorTask[%s] query failed: %s",
                            self.task_id, e,
                        )

                    cron = croniter(cron_expression, now)
                    next_time = cron.get_next(datetime)
                    logger.debug(
                        "DatabaseCollectorTask[%s] next run: %s",
                        self.task_id, next_time,
                    )

                self._stop_event.wait(timeout=1)
        finally:
            loop.close()
            logger.info("DatabaseCollectorTask[%s] stopped.", self.task_id)