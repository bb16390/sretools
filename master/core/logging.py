from logging import FileHandler, LogRecord, WARNING
from logging.handlers import QueueHandler
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