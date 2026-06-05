import os
import sys
import time
import logging
from logging import FileHandler

from worker.core.settings import settings
from worker.core.logging import AsyncFileHandler
from worker.metrics.metric_converter import MetricConverter
from worker.communicator.central_client import CentralClient
from worker.scheduler.task_scheduler import TaskScheduler
from worker.scheduler.trade_day_cache import TradeDayCache
from worker.scheduler.tasks import LogCollectorTask, MetricConverterTask, DatabaseCollectorTask, KafkaCollectorTask

# 配置日志系统
log_dir = os.path.dirname(settings.log_dir)
if not os.path.exists(log_dir):
    os.makedirs(log_dir, exist_ok=True)

# 创建 FileHandler
file_handler = FileHandler(settings.log_dir, encoding='utf-8')
file_handler.setLevel(getattr(logging, settings.log_level))

# 创建 AsyncFileHandler
async_file_handler = AsyncFileHandler(file_handler)

# 配置日志格式
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# 添加处理器到根日志器
root_logger = logging.getLogger()
root_logger.setLevel(getattr(logging, settings.log_level))
root_logger.addHandler(async_file_handler)

# 创建应用专用日志器
app_logger = logging.getLogger(__name__)


class Worker:
    def __init__(self):
        app_logger.info("Initializing worker...")
        
        try:
            # 初始化中心端客户端
            self.central_client = CentralClient()
            app_logger.info(f"Central client initialized with servers: {settings.central_servers}")
            
            # 初始化 gRPC 客户端
            from worker.grpc.client import CentralGrpcClient
            self.grpc_client = CentralGrpcClient()
            if self.grpc_client.health_check():
                self.grpc_client.register()
                self.grpc_client.start_communicate_stream()
                app_logger.info("gRPC client initialized and connected")
            
            # 初始化任务调度器
            self.scheduler = TaskScheduler(central_client=self.central_client, grpc_client=self.grpc_client)
            app_logger.info("TaskScheduler created")

            # 初始化交易日缓存
            self.trade_day_cache = TradeDayCache(self.central_client)
            app_logger.info("TradeDayCache initialized")

            # 设置交易日缓存到中心端客户端
            self.central_client.set_trade_day_cache(self.trade_day_cache)
            app_logger.info("TradeDayCache set on central client")

            # 将交易日缓存传递给调度器
            self.scheduler._trade_day_cache = self.trade_day_cache
            app_logger.info("TradeDayCache set on scheduler")
            
            # 注册调度器到中心端客户端
            self.central_client.register_task_scheduler(self.scheduler)
            app_logger.info("TaskScheduler registered with central client")
            
            # 注册任务类型到调度器工厂
            self.scheduler.register_task_type("log_collector", LogCollectorTask)
            self.scheduler.register_task_type("metric_converter", MetricConverterTask)
            self.scheduler.register_task_type("database_collector", DatabaseCollectorTask)
            self.scheduler.register_task_type("kafka_collector", KafkaCollectorTask)
            app_logger.info("Task types registered with scheduler factory")
            
            # 设置 worker_id
            self.scheduler._worker_id = settings.worker_id
            app_logger.info(f"Scheduler worker_id set to: {settings.worker_id}")
            
            # 启动进程监控
            self.scheduler._start_monitor()
            app_logger.info("Process monitor started")
            
            # 初始化指标转换器
            self.metric_converter = MetricConverter()
            app_logger.info("Metric converter initialized")
            
            app_logger.info("Worker initialized successfully")
        except Exception as e:
            app_logger.error(f"Worker initialization failed: {e}")
            raise
    
    def run(self):
        app_logger.info("Starting worker...")
        
        # 主循环
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            app_logger.info("Worker stopped by user")
            self.scheduler.shutdown()
        except Exception as e:
            app_logger.error(f"Worker error: {e}")
            self.scheduler.shutdown()
            raise


if __name__ == "__main__":
    worker = Worker()
    worker.run()
