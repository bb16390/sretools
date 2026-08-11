import os
import logging
from logging import FileHandler, LogRecord, WARNING
from logging.handlers import QueueHandler, TimedRotatingFileHandler
from queue import Queue, Empty
from threading import Thread, Event
import atexit
import time
from time import sleep

class AsyncFileHandler(QueueHandler):
    def __init__(self, base_handler: logging.Handler, max_queue_size: int = 10000, drop_threshold: float = 0.8, batch_size: int = 500, flush_interval: float = 0.2) -> None:
        queue = Queue(maxsize=max_queue_size)
        super().__init__(queue)
        self.shutdown_event = Event()
        self._file_handler = base_handler
        self._exit = False
        self._max_size = max_queue_size
        self._drop_size = int(max_queue_size * drop_threshold)
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._processed_count = 0
        self._start_time = time.time()
        self._write_thread = Thread(target=self.write, daemon=True)
        self._write_thread.start()
        atexit.register(self.close)

    def close(self) -> None:
        super().close()
        if self.shutdown_event.is_set():
            return

        self.shutdown_event.set()
        self._write_thread.join()

        while True:
            try:
                record = self.queue.get_nowait()
                self._file_handler.handle(record)
            except Empty:
                break
            except Exception as e:
                import traceback
                print(f"Error during queue cleanup: {e}")
                traceback.print_exc()
                break

    def write(self):
        buffer = []
        buffer_size = 0
        max_buffer_size = self._batch_size
        
        while not self.shutdown_event.is_set():
            try:
                for _ in range(100):
                    try:
                        record = self.queue.get(timeout=0.01)
                        buffer.append(record)
                        buffer_size += 1
                        if buffer_size >= max_buffer_size:
                            break
                    except Empty:
                        break
                
                if buffer:
                    for record in buffer:
                        try:
                            self._file_handler.handle(record)
                            self._processed_count += 1
                        except Exception as e:
                            import traceback
                            print(f"Error handling log record: {e}")
                            traceback.print_exc()
                    
                    buffer = []
                    buffer_size = 0
                    
                    try:
                        if hasattr(self._file_handler, 'flush'):
                            self._file_handler.flush()
                    except Exception as e:
                        import traceback
                        print(f"Error flushing file handler: {e}")
                        traceback.print_exc()
            except Exception as e:
                import traceback
                print(f"Error processing log: {e}")
                traceback.print_exc()
    
    def _process_batch(self, batch):
        for record in batch:
            try:
                self._file_handler.handle(record)
                self._processed_count += 1
            except Exception as e:
                import traceback
                print(f"Error handling log record: {e}")
                traceback.print_exc()
        
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
        self.queue.put(record)

    def get_queue_size(self) -> int:
        return self.queue.qsize()

    def get_processing_speed(self) -> float:
        elapsed = time.time() - self._start_time
        if elapsed == 0:
            return 0
        return self._processed_count / elapsed


def _create_rotating_handler(file_path: str, formatter: logging.Formatter, log_level_str: str, settings) -> AsyncFileHandler:
    log_dir = os.path.dirname(file_path)
    os.makedirs(log_dir, exist_ok=True)

    timed_handler = TimedRotatingFileHandler(
        filename=file_path,
        when=settings.log_rotation_when,
        interval=settings.log_rotation_interval,
        backupCount=settings.log_backup_count,
        encoding=settings.log_rotation_encoding,
        delay=True,
    )
    timed_handler.setLevel(getattr(logging, log_level_str))
    timed_handler.setFormatter(formatter)

    async_handler = AsyncFileHandler(base_handler=timed_handler)
    async_handler.setLevel(getattr(logging, log_level_str))

    return async_handler


def setup_logging(settings) -> None:
    logger_names = ["", "uvicorn", "uvicorn.error", "uvicorn.access"]
    for name in logger_names:
        logger = logging.getLogger(name)
        for h in list(logger.handlers):
            if isinstance(h, AsyncFileHandler):
                logger.removeHandler(h)

    main_formatter = logging.Formatter(settings.log_format)
    access_formatter = logging.Formatter(settings.access_log_format)

    main_handler = _create_rotating_handler(settings.log_file, main_formatter, settings.log_level, settings)
    error_handler = _create_rotating_handler(settings.error_log_file, main_formatter, "WARNING", settings)

    log_level = getattr(logging, settings.log_level)

    root_logger = logging.getLogger("")
    root_logger.setLevel(log_level)
    root_logger.addHandler(main_handler)
    root_logger.addHandler(error_handler)

    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.setLevel(log_level)
    uvicorn_logger.addHandler(main_handler)
    uvicorn_logger.addHandler(error_handler)
    uvicorn_logger.propagate = False

    uvicorn_error_logger = logging.getLogger("uvicorn.error")
    uvicorn_error_logger.setLevel(log_level)
    uvicorn_error_logger.addHandler(main_handler)
    uvicorn_error_logger.addHandler(error_handler)
    uvicorn_error_logger.propagate = False

    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    uvicorn_access_logger.setLevel(log_level)
    uvicorn_access_logger.addHandler(main_handler)
    uvicorn_access_logger.propagate = False


def get_uvicorn_log_config(settings) -> dict:
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {},
        "handlers": {},
        "loggers": {},
    }
