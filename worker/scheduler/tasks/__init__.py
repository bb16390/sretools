from worker.scheduler.tasks.log_collector_task import LogCollectorTask
from worker.scheduler.tasks.metric_converter_task import MetricConverterTask
from worker.scheduler.tasks.database_collector_task import DatabaseCollectorTask
from worker.scheduler.tasks.kafka_collector_task import KafkaCollectorTask

# prefect 实现的数据库采集任务是可选的：当 prefect 未安装时降级跳过，
# 保留 DatabaseCollectorTask 作为基础实现。
try:
    from worker.scheduler.tasks.prefect_database_collector_task import (
        PrefectDatabaseCollectorTask,
        HAS_PREFECT,
    )
except ImportError:  # pragma: no cover
    PrefectDatabaseCollectorTask = None  # type: ignore
    HAS_PREFECT = False

__all__ = [
    "LogCollectorTask",
    "MetricConverterTask",
    "DatabaseCollectorTask",
    "KafkaCollectorTask",
    "PrefectDatabaseCollectorTask",
    "HAS_PREFECT",
]
