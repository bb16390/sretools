import enum
import uuid
import threading
import multiprocessing
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class ExecutionMode(enum.Enum):
    THREAD = "thread"
    PROCESS = "process"


class TaskStatus(enum.Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    FAILED = "failed"


class BaseTask(ABC):
    """任务抽象基类，定义统一的任务生命周期接口"""

    def __init__(
        self,
        task_type: str,
        config: Dict[str, Any],
        task_id: Optional[str] = None,
    ):
        self.task_id = task_id or str(uuid.uuid4())
        self.task_type = task_type
        self.config = config
        self._status = TaskStatus.IDLE

        # 解析执行模式
        mode_str = config.get("execution_mode", None)
        if mode_str == "thread":
            self.execution_mode = ExecutionMode.THREAD
        elif mode_str == "process":
            self.execution_mode = ExecutionMode.PROCESS
        else:
            self.execution_mode = self._default_execution_mode()

        # 控制信号
        self._stop_event: Optional[threading.Event] = None
        self._pause_event: Optional[threading.Event] = None

        # 执行载体
        self._thread: Optional[threading.Thread] = None
        self._process: Optional[multiprocessing.Process] = None

        # 状态回调
        self._status_callback: Optional[callable] = None

    @property
    def status(self) -> TaskStatus:
        return self._status

    def set_status_callback(self, callback: callable):
        """设置状态上报回调函数"""
        self._status_callback = callback

    def _notify_status(self, status: str, result: Any = None, duration_ms: float = 0):
        """通知调度器上报任务状态"""
        if self._status_callback:
            self._status_callback(
                task_id=self.task_id,
                task_type=self.task_type,
                status=status,
                result=result,
                duration_ms=duration_ms,
            )

    @abstractmethod
    def _default_execution_mode(self) -> ExecutionMode:
        """返回默认执行模式，子类必须实现"""
        ...

    @abstractmethod
    def _run(self):
        """核心执行逻辑，子类必须实现。在子线程/子进程中运行。"""
        ...

    def start(self):
        """启动任务"""
        if self._status in (TaskStatus.RUNNING, TaskStatus.PAUSED):
            return

        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # 初始为不暂停状态

        self._status = TaskStatus.RUNNING

        if self.execution_mode == ExecutionMode.THREAD:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        else:
            self._process = multiprocessing.Process(target=self._run, daemon=True)
            self._process.start()

    def stop(self):
        """停止任务"""
        if self._status in (TaskStatus.STOPPED, TaskStatus.FAILED):
            return

        self._status = TaskStatus.STOPPED
        if self._stop_event:
            self._stop_event.set()

        if self.execution_mode == ExecutionMode.THREAD:
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=5)
        else:
            if self._process and self._process.is_alive():
                self._process.join(timeout=5)
                if self._process.is_alive():
                    self._process.terminate()
                    self._process.join(timeout=3)

    def pause(self):
        """暂停任务"""
        if self._status != TaskStatus.RUNNING:
            return
        self._status = TaskStatus.PAUSED
        if self._pause_event:
            self._pause_event.clear()

    def resume(self):
        """恢复任务"""
        if self._status != TaskStatus.PAUSED:
            return
        self._status = TaskStatus.RUNNING
        if self._pause_event:
            self._pause_event.set()

    def is_alive(self) -> bool:
        """检查任务执行载体是否存活"""
        if self.execution_mode == ExecutionMode.THREAD:
            return self._thread is not None and self._thread.is_alive()
        else:
            return self._process is not None and self._process.is_alive()