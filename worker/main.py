"""Worker 入口。

无论是从项目根目录运行（如 ``python -m worker.main``），
还是直接进入 ``worker/`` 目录运行（如 ``python main.py``），
本文件都会把 **项目根目录** 正确加入 ``sys.path``，
避免 ``worker/grpc`` 子包名与第三方 ``grpcio`` 库发生名称冲突。
"""

import os
import sys
import time
import logging

# ---------------------------------------------------------------------------
# 1. 确定项目根目录，并清理 / 重置 sys.path，避免 ``worker/grpc`` 与
#    第三方 ``grpcio`` 发生包名冲突
# ---------------------------------------------------------------------------
def _detect_project_root() -> str:
    """向上探测包含 ``pyproject.toml`` 的目录作为项目根。"""
    # 优先使用本文件路径；在 ``python -c`` 等没有 __file__ 的场景里使用 cwd
    start = globals().get("__file__") or os.getcwd()
    start = os.path.abspath(start)
    if os.path.isfile(start):
        cur = os.path.dirname(start)
    else:
        cur = start
    # 向上最多 5 级，寻找 pyproject.toml
    for _ in range(5):
        if os.path.isfile(os.path.join(cur, "pyproject.toml")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    # 回退：如果当前目录名是 worker，则上一级是项目根
    if os.path.basename(os.getcwd()) == "worker":
        return os.path.dirname(os.getcwd())
    return os.getcwd()


PROJECT_ROOT = _detect_project_root()
_WORKER_DIR = os.path.join(PROJECT_ROOT, "worker")

# 关键修复：当以 ``cd worker && python main.py`` 或 ``python worker/main.py``
# 运行时，Python 会把 ``worker/`` 加入 sys.path[0]，此时 ``import grpc``
# 会命中本地的 ``worker/grpc/`` 子包而非真正的 ``grpcio``。
# 解决：把任何指向 ``worker/`` 的条目从 sys.path 中剔除；然后把 ``PROJECT_ROOT``
# 放到首位，确保 ``import worker.*`` 仍能解析。
def _normalize(p: str) -> str:
    try:
        return os.path.normcase(os.path.realpath(p))
    except OSError:
        return p


_WORKER_DIR_NORM = _normalize(_WORKER_DIR)
sys.path[:] = [
    p for p in sys.path
    if p and _normalize(p) not in (_WORKER_DIR_NORM, _normalize(""))
]

if _normalize(PROJECT_ROOT) not in {_normalize(p) for p in sys.path}:
    sys.path.insert(0, PROJECT_ROOT)

# 切换工作目录到项目根，使相对路径行为一致
try:
    os.chdir(PROJECT_ROOT)
except OSError:
    pass

# ---------------------------------------------------------------------------
# 2. 导入内部模块（必须放在 sys.path 调整之后）
# ---------------------------------------------------------------------------
from worker.core.settings import settings  # noqa: E402
from worker.core.logging import AsyncFileHandler  # noqa: E402
from worker.grpc.client import CentralGrpcClient  # noqa: E402
from worker.scheduler.task_scheduler import TaskScheduler  # noqa: E402
from worker.scheduler.trade_day_cache import TradeDayCache  # noqa: E402
from worker.scheduler.tasks import (  # noqa: E402
    LogCollectorTask,
    MetricConverterTask,
    DatabaseCollectorTask,
    KafkaCollectorTask,
)


def setup_logging() -> None:
    """初始化日志系统（FileHandler + AsyncFileHandler + Console Handler）。"""
    log_dir = os.path.dirname(settings.log_dir)
    os.makedirs(log_dir, exist_ok=True)

    file_handler = logging.FileHandler(settings.log_dir, encoding="utf-8")
    file_handler.setLevel(getattr(logging, settings.log_level, logging.INFO))

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)

    async_file_handler = AsyncFileHandler(file_handler)

    # 控制台 handler：用于冒烟测试和日常调试
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.log_level, logging.INFO))
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level, logging.INFO))
    # 避免重复添加（被重复导入的保护措施）
    if not any(isinstance(h, (AsyncFileHandler, logging.StreamHandler)) for h in root_logger.handlers):
        root_logger.addHandler(async_file_handler)
        root_logger.addHandler(console_handler)


class Worker:
    """Worker 主进程：初始化 gRPC 客户端、调度器、交易日缓存，并注册任务类型。"""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing worker...")
        self.logger.info("Project root: %s", PROJECT_ROOT)
        self.logger.info("sys.path[0]: %s", sys.path[0])

        try:
            # gRPC 客户端
            self.grpc_client = CentralGrpcClient()
            self.logger.info("gRPC client created")

            registered = self.grpc_client.register()
            if registered:
                self.logger.info("Worker registered with master")
            else:
                self.logger.warning(
                    "Worker registration failed (master may be unreachable); "
                    "will retry later via heartbeat."
                )

            # 任务调度器
            self.scheduler = TaskScheduler(
                central_client=None, grpc_client=self.grpc_client
            )
            self.logger.info("TaskScheduler created")

            # 交易日缓存
            self.trade_day_cache = TradeDayCache(self.grpc_client)
            self.logger.info("TradeDayCache initialized")

            self.grpc_client.set_trade_day_cache(self.trade_day_cache)
            self.scheduler._trade_day_cache = self.trade_day_cache  # noqa: SLF001
            self.grpc_client.register_task_scheduler(self.scheduler)
            self.logger.info("References wired between grpc_client / scheduler / trade_day_cache")

            # 注册任务类型
            self.scheduler.register_task_type("log_collector", LogCollectorTask)
            self.scheduler.register_task_type("metric_converter", MetricConverterTask)
            self.scheduler.register_task_type("database_collector", DatabaseCollectorTask)
            self.scheduler.register_task_type("kafka_collector", KafkaCollectorTask)
            self.logger.info("Task types registered with scheduler factory")

            # worker ID
            self.scheduler._worker_id = settings.worker_id  # noqa: SLF001
            self.logger.info("Scheduler worker_id set to: %s", settings.worker_id)

            # 启动进程监控
            self.scheduler._start_monitor()  # noqa: SLF001
            self.logger.info("Process monitor started")

            self.logger.info("Worker initialized successfully")
        except Exception:
            self.logger.exception("Worker initialization failed")
            raise

    def run(self) -> None:
        self.logger.info("Starting worker main loop (Ctrl+C to stop)...")
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            self.logger.info("Worker stopped by user")
            self.shutdown()
        except Exception:
            self.logger.exception("Fatal error in worker main loop")
            self.shutdown()
            raise

    def shutdown(self) -> None:
        self.logger.info("Shutting down worker...")
        try:
            self.scheduler.shutdown()
        except Exception:  # pragma: no cover - 保护关闭流程
            self.logger.exception("Error shutting down scheduler")
        try:
            self.grpc_client.close()
        except Exception:  # pragma: no cover
            self.logger.exception("Error closing grpc_client")
        self.logger.info("Worker shutdown complete")


if __name__ == "__main__":
    setup_logging()
    worker = Worker()
    worker.run()
