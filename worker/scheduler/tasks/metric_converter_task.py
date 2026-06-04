import time
import logging
from typing import Any, Dict

from worker.scheduler.base_task import BaseTask, ExecutionMode, TaskStatus
from worker.metrics.metric_converter import MetricConverter
from worker.core.settings import settings

logger = logging.getLogger(__name__)


class MetricConverterTask(BaseTask):
    """指标转换任务，负责将日志数据转换为结构化指标"""

    def __init__(self, config: Dict[str, Any] = None, task_id: str = None):
        super().__init__(
            task_type="metric_converter",
            config=config or {},
            task_id=task_id,
        )

    def _default_execution_mode(self) -> ExecutionMode:
        return ExecutionMode.PROCESS

    def _run(self):
        logger.info(f"MetricConverterTask [{self.task_id}] starting")
        metric_converter = None
        last_report_time = time.time()
        report_interval = self.config.get("report_interval", 30)

        try:
            metric_converter = MetricConverter()
            collect_interval = settings.metric_collect_interval

            while not self._stop_event.is_set():
                # 检查是否需要暂停
                if not self._pause_event.is_set():
                    self._pause_event.wait(timeout=1.0)
                    continue

                try:
                    metric_converter.simulate_log_conversion()
                    logger.debug(
                        f"MetricConverterTask [{self.task_id}] metrics collected, "
                        f"queue size: {metric_converter.get_queue_size()}"
                    )

                    now = time.time()
                    if now - last_report_time >= report_interval:
                        self._notify_status(
                            "running",
                            result=f"queue_size={metric_converter.get_queue_size()}",
                            duration_ms=0,
                        )
                        last_report_time = now

                except Exception as e:
                    logger.error(
                        f"MetricConverterTask [{self.task_id}] error during conversion: {e}",
                        exc_info=True,
                    )

                # 按配置的间隔休眠，期间检查停止/暂停信号
                self._stop_event.wait(timeout=collect_interval)

        except Exception as e:
            logger.error(
                f"MetricConverterTask [{self.task_id}] fatal error: {e}",
                exc_info=True,
            )
        finally:
            logger.info(f"MetricConverterTask [{self.task_id}] stopped")