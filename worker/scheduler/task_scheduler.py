import time
import threading
import logging
from typing import Any, Dict, List, Optional, Type

from worker.scheduler.base_task import BaseTask, ExecutionMode, TaskStatus

logger = logging.getLogger(__name__)


class TaskScheduler:
    """Worker 端任务调度管理器"""

    def __init__(self, central_client=None):
        self._tasks: Dict[str, BaseTask] = {}
        self._task_factory: Dict[str, Type[BaseTask]] = {}
        self._lock = threading.Lock()
        self._central_client = central_client

        # 进程存活监控
        self._monitor_thread: Optional[threading.Thread] = None
        self._monitor_running = False
        self._monitor_interval = 5  # 秒

    def set_central_client(self, central_client):
        """设置中心端客户端引用"""
        self._central_client = central_client

    def register_task_type(
        self,
        task_type: str,
        task_cls: Type[BaseTask],
    ):
        """注册任务类型到工厂"""
        self._task_factory[task_type] = task_cls
        logger.info(f"Registered task type: {task_type} -> {task_cls.__name__}")

    def create_task(self, task_type: str, config: Dict[str, Any]) -> Optional[str]:
        """创建并启动一个任务，返回 task_id"""
        if task_type not in self._task_factory:
            logger.error(f"Unknown task type: {task_type}")
            return None

        task_cls = self._task_factory[task_type]

        # 如果未指定 execution_mode，使用该类型默认值
        if "execution_mode" not in config:
            temp_instance = task_cls(task_type=task_type, config=config)
            config["execution_mode"] = temp_instance._default_execution_mode().value

        task = task_cls(task_type=task_type, config=config)
        task.set_status_callback(self._on_task_status)

        with self._lock:
            self._tasks[task.task_id] = task

        task.start()
        logger.info(f"Task created and started: {task.task_id} (type={task_type}, mode={task.execution_mode.value})")
        return task.task_id

    def stop_task(self, task_id: str):
        """停止指定任务"""
        task = self._get_task(task_id)
        if task is None:
            logger.warning(f"Task not found: {task_id}")
            return

        logger.info(f"Stopping task: {task_id} (mode={task.execution_mode.value})")
        task.stop()

        with self._lock:
            del self._tasks[task_id]

    def pause_task(self, task_id: str):
        """暂停指定任务"""
        task = self._get_task(task_id)
        if task:
            task.pause()
            logger.info(f"Task paused: {task_id}")

    def resume_task(self, task_id: str):
        """恢复指定任务"""
        task = self._get_task(task_id)
        if task:
            task.resume()
            logger.info(f"Task resumed: {task_id}")

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """查询单个任务状态"""
        task = self._get_task(task_id)
        if task is None:
            return None
        return self._task_to_dict(task)

    def list_tasks(self) -> List[Dict[str, Any]]:
        """列出所有任务状态"""
        with self._lock:
            return [self._task_to_dict(t) for t in self._tasks.values()]

    def shutdown(self):
        """优雅关闭：停止所有运行中的任务"""
        logger.info("Shutting down TaskScheduler...")
        self._monitor_running = False

        with self._lock:
            task_ids = list(self._tasks.keys())

        for task_id in task_ids:
            try:
                self.stop_task(task_id)
            except Exception as e:
                logger.error(f"Error stopping task {task_id}: {e}")

        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=3)

        logger.info("TaskScheduler shutdown complete")

    def _get_task(self, task_id: str) -> Optional[BaseTask]:
        with self._lock:
            return self._tasks.get(task_id)

    def _task_to_dict(self, task: BaseTask) -> Dict[str, Any]:
        return {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "status": task.status.value,
            "execution_mode": task.execution_mode.value,
            "config": task.config,
        }

    def _on_task_status(self, task_id: str, task_type: str, status: str,
                        result: Any = None, duration_ms: float = 0):
        """任务状态回调，触发上报"""
        self.report_task_status(task_id, status, result, duration_ms)

    def report_task_status(self, task_id: str, status: str,
                           result: Any = None, duration_ms: float = 0,
                           extra: Optional[Dict[str, Any]] = None):
        """上报任务状态到 Master"""
        if self._central_client is None:
            return

        task = self._get_task(task_id)
        task_type = task.task_type if task else "unknown"
        execution_mode = task.execution_mode.value if task else "unknown"

        import asyncio
        message = {
            "type": "task_status",
            "worker_id": getattr(self, "_worker_id", "unknown"),
            "task_id": task_id,
            "task_type": task_type,
            "execution_mode": execution_mode,
            "status": status,
            "result": str(result) if result else None,
            "duration_ms": duration_ms,
            "timestamp": time.time(),
            "extra": extra or {},
        }

        try:
            asyncio.run_coroutine_threadsafe(
                self._central_client.send_websocket_message(message),
                asyncio.get_event_loop(),
            )
        except Exception as e:
            logger.error(f"Failed to report task status: {e}")

    # --- 进程存活监控 ---

    def _start_monitor(self):
        """启动进程存活监控线程"""
        if self._monitor_running:
            return
        self._monitor_running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Process monitor started")

    def _monitor_loop(self):
        """监控循环：定期检查进程模式任务的存活状态"""
        while self._monitor_running:
            try:
                time.sleep(self._monitor_interval)
                self._check_process_health()
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")

    def _check_process_health(self):
        """检查所有进程模式任务的状态"""
        with self._lock:
            tasks = list(self._tasks.items())

        for task_id, task in tasks:
            if task.execution_mode != ExecutionMode.PROCESS:
                continue
            if task.status in (TaskStatus.STOPPED, TaskStatus.FAILED, TaskStatus.IDLE):
                continue

            if not task.is_alive():
                logger.warning(f"Process task died unexpectedly: {task_id}")
                task._status = TaskStatus.FAILED
                self.report_task_status(
                    task_id,
                    status="failed",
                    result="Process exited unexpectedly",
                )