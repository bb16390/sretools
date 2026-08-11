import os
import logging
import logging.config
from logging import FileHandler, LogRecord, WARNING
from logging.handlers import QueueHandler, TimedRotatingFileHandler
from queue import Queue, Empty
from threading import Thread, Event
import atexit
import time
from time import sleep

class AsyncFileHandler(QueueHandler):
    def __init__(self, file_handler: FileHandler, max_queue_size: int = 10000, drop_threshold: float = 0.8, batch_size: int = 500, flush_interval: float = 0.2) -> None:
        queue = Queue(maxsize=max_queue_size)
        super().__init__(queue)
        # 使用 Event 来控制优雅关闭
        self.shutdown_event = Event()
        # 原FileHandler
        self._file_handler = file_handler
        self._exit = False
        # 队列配置
        self._max_size = max_queue_size
        self._drop_size = int(max_queue_size * drop_threshold)
        # 批处理配置
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        # 性能指标
        self._processed_count = 0
        self._start_time = time.time()
        # 写线程
        self._write_thread = Thread(target=self.write, daemon=True)
        self._write_thread.start()
        atexit.register(self.close)

    def close(self) -> None:
        super().close()
        if self.shutdown_event.is_set():
            return

        self.shutdown_event.set()
        self._write_thread.join()

        # 清空队列
        while True:
            try:
                record = self.queue.get_nowait()
                self._file_handler.handle(record)
            except Empty:
                break
            except Exception as e:
                # 记录错误但继续清空队列
                import traceback
                print(f"Error during queue cleanup: {e}")
                traceback.print_exc()
                break

    def write(self):
        # 使用内存缓冲区，减少磁盘I/O操作
        buffer = []
        buffer_size = 0
        max_buffer_size = self._batch_size
        
        while not self.shutdown_event.is_set():
            try:
                # 批量获取日志记录
                for _ in range(100):  # 一次尝试获取多条
                    try:
                        record = self.queue.get(timeout=0.01)
                        buffer.append(record)
                        buffer_size += 1
                        if buffer_size >= max_buffer_size:
                            break
                    except Empty:
                        break
                
                # 批量处理日志
                if buffer:
                    for record in buffer:
                        try:
                            self._file_handler.handle(record)
                            self._processed_count += 1
                        except Exception as e:
                            import traceback
                            print(f"Error handling log record: {e}")
                            traceback.print_exc()
                    
                    # 清空缓冲区
                    buffer = []
                    buffer_size = 0
                    
                    # 刷新文件缓冲
                    try:
                        if hasattr(self._file_handler, 'flush'):
                            self._file_handler.flush()
                    except Exception as e:
                        import traceback
                        print(f"Error flushing file handler: {e}")
                        traceback.print_exc()
            except Exception as e:
                # 记录错误但继续运行
                import traceback
                print(f"Error processing log: {e}")
                traceback.print_exc()
    
    def _process_batch(self, batch):
        """
        处理批处理日志
        """
        for record in batch:
            try:
                self._file_handler.handle(record)
                self._processed_count += 1
            except Exception as e:
                import traceback
                print(f"Error handling log record: {e}")
                traceback.print_exc()
        
        # 刷新文件缓冲
        try:
            if hasattr(self._file_handler, 'flush'):
                self._file_handler.flush()
        except Exception as e:
            import traceback
            print(f"Error flushing file handler: {e}")
            traceback.print_exc()

    def handle(self, record: LogRecord) -> None:
        self.enqueue(record)

    def enqueue(self, record: LogRecord) -> None:
        """
        确保日志不被丢弃，使用阻塞方式入队
        """
        # 使用阻塞方式入队，确保日志不被丢弃
        self.queue.put(record)

    def get_queue_size(self) -> int:
        """
        获取当前队列大小
        """
        return self.queue.qsize()

    def get_processing_speed(self) -> float:
        """
        获取日志处理速度（条/秒）
        """
        elapsed = time.time() - self._start_time
        if elapsed == 0:
            return 0
        return self._processed_count / elapsed



def get_uvicorn_log_config(settings) -> dict:
    """返回 uvicorn 的 ``log_config``，统一记录 fastapi 程序的所有日志。

    通过 ``root`` logger 配置 ``AsyncFileHandler``，使业务日志
    （``master.main``、``aiosqlite`` 等）与 uvicorn 的 access/error 日志
    都写入 ``settings.log_dir``。``uvicorn.access`` / ``uvicorn.error``
    保留各自的 ``StreamHandler``（终端输出）并 ``propagate=True``，因此
    同一条日志会同时落地终端与文件，且每个通道仅写一次。

    访问日志格式在 ``settings.log_format`` 基础上，将 ``%(message)s``
    替换为 ``%(client_addr)s - "%(request_line)s" %(status_code)s``，
    由 ``uvicorn.logging.AccessFormatter`` 注入这些字段。
    """
    # 用访问日志专用字段替换 %(message)s，保持前缀与业务日志一致
    if "%(message)s" in settings.log_format:
        access_fmt = settings.log_format.replace(
            "%(message)s",
            '%(client_addr)s - "%(request_line)s" %(status_code)s',
        )
    else:
        access_fmt = (
            settings.log_format
            + ' - %(client_addr)s - "%(request_line)s" %(status_code)s'
        )

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": settings.log_format,
                "use_colors": False,
            },
            "access": {
                "()": "uvicorn.logging.AccessFormatter",
                "fmt": access_fmt,
                "use_colors": False,
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
            "access": {
                "formatter": "access",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
            "file": {
                "class": "logging.handlers.TimedRotatingFileHandler",
                "filename": settings.log_dir,
                "when": "midnight",                 # 每天午夜轮转
                "interval": 1,                      # 轮转间隔为 1 天
                "backupCount": 60,                  # 保留最近 30 天的日志文件
                "encoding": "utf-8",
                "formatter": "default",
            },
        },
        "root": {
            "handlers": ["file"],
            "level": settings.log_level,
        },
        "loggers": {
            "uvicorn.error": {
                "handlers": ["default"],
                "level": "INFO",
                "propagate": True,
            },
            "uvicorn.access": {
                "handlers": ["access"],
                "level": "INFO",
                "propagate": True,
            },
            "uvicorn.asgi": {"level": "WARNING"},
        },
    }