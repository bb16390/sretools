import logging
import time
import os
import json
from queue import Queue
from datetime import datetime
from typing import List, Dict, Any

from worker.scheduler.base_task import BaseTask, ExecutionMode, TaskStatus
from worker.core.settings import settings

logger = logging.getLogger(__name__)


class LogCollectorTask(BaseTask):

    def __init__(self, config: dict, task_id: str = None):
        super().__init__(
            task_type="log_collector",
            config=config,
            task_id=task_id,
        )
        self.log_queue = Queue(maxsize=settings.log_queue_size)
        self.batch_size = settings.log_batch_size
        self.local_storage_path = settings.local_storage_path
        self.max_local_storage_size = settings.max_local_storage_size
        
        os.makedirs(self.local_storage_path, exist_ok=True)

    def _default_execution_mode(self) -> ExecutionMode:
        return ExecutionMode.PROCESS

    def simulate_log_collection(self):
        for i in range(10):
            log = {
                "timestamp": datetime.now().isoformat(),
                "level": "INFO",
                "message": f"Simulated log message {i}",
                "source": "simulation",
                "worker_id": settings.worker_id
            }
            self.log_queue.put(log)

    def save_to_local(self, logs: List[Dict[str, Any]]):
        date_str = datetime.now().strftime("%Y-%m-%d")
        file_path = os.path.join(self.local_storage_path, f"logs_{date_str}.jsonl")
        
        with open(file_path, 'a', encoding='utf-8') as f:
            for log in logs:
                f.write(json.dumps(log, ensure_ascii=False) + '\n')
        
        self.check_storage_size()

    def check_storage_size(self):
        total_size = 0
        files = []
        
        for file_name in os.listdir(self.local_storage_path):
            file_path = os.path.join(self.local_storage_path, file_name)
            if os.path.isfile(file_path):
                file_size = os.path.getsize(file_path) / (1024 * 1024)
                total_size += file_size
                files.append((file_path, os.path.getmtime(file_path)))
        
        if total_size > self.max_local_storage_size:
            files.sort(key=lambda x: x[1])
            while total_size > self.max_local_storage_size and files:
                file_path, _ = files.pop(0)
                file_size = os.path.getsize(file_path) / (1024 * 1024)
                total_size -= file_size
                os.remove(file_path)

    def process_batch(self):
        batch = []
        while len(batch) < self.batch_size:
            try:
                log = self.log_queue.get(timeout=0.1)
                batch.append(log)
            except Exception:
                break
        
        if batch:
            self.save_to_local(batch)

    def get_queue_size(self) -> int:
        return self.log_queue.qsize()

    def _run(self):
        logger.info("LogCollectorTask %s starting...", self.task_id)
        last_report_time = time.time()
        report_interval = self.config.get("report_interval", 30)
        try:
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
                    self.simulate_log_collection()
                    self.process_batch()
                    logger.debug(
                        "LogCollectorTask %s: collected logs, queue size: %d",
                        self.task_id,
                        self.get_queue_size(),
                    )

                    now = time.time()
                    if now - last_report_time >= report_interval:
                        self._notify_status(
                            "running",
                            result=f"queue_size={self.get_queue_size()}",
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