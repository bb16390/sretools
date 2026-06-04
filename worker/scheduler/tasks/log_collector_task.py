import logging
import time

from worker.scheduler.base_task import BaseTask, ExecutionMode, TaskStatus
from worker.collector.log_collector import LogCollector
from worker.core.settings import settings

logger = logging.getLogger(__name__)


class LogCollectorTask(BaseTask):

    def __init__(self, config: dict, task_id: str = None, central_client=None):
        super().__init__(
            task_type="log_collector",
            config=config,
            task_id=task_id,
        )
        self.central_client = central_client

    def _default_execution_mode(self) -> ExecutionMode:
        return ExecutionMode.PROCESS

    def _run(self):
        logger.info("LogCollectorTask %s starting...", self.task_id)
        log_collector = None
        last_report_time = time.time()
        report_interval = self.config.get("report_interval", 30)
        try:
            log_collector = LogCollector(central_client=self.central_client)
            collect_interval = self.config.get(
                "collect_interval", settings.log_collect_interval
            )

            while True:
                if self._stop_event.is_set():
                    logger.info(
                        "LogCollectorTask %s received stop signal", self.task_id
                    )
                    break

                if not self._pause_event.is_set():
                    time.sleep(0.5)
                    continue

                try:
                    # 如果 Kafka 没有启用，继续使用模拟收集
                    if not settings.kafka_enabled:
                        log_collector.simulate_log_collection()
                    
                    logger.debug(
                        "LogCollectorTask %s: collected logs, queue size: %d",
                        self.task_id,
                        log_collector.get_queue_size(),
                    )

                    now = time.time()
                    if now - last_report_time >= report_interval:
                        self._notify_status(
                            "running",
                            result=f"queue_size={log_collector.get_queue_size()}",
                            duration_ms=0,
                        )
                        last_report_time = now

                except Exception as e:
                    logger.error(
                        "LogCollectorTask %s: error collecting logs: %s",
                        self.task_id,
                        e,
                    )

                time.sleep(collect_interval)

        except Exception as e:
            logger.error(
                "LogCollectorTask %s failed: %s", self.task_id, e, exc_info=True
            )
        finally:
            logger.info("LogCollectorTask %s stopped", self.task_id)