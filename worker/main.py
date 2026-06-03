import os
import sys
import logging
from logging import FileHandler

from worker.core.settings import settings
from worker.core.logging import AsyncFileHandler
from worker.collector.log_collector import LogCollector
from worker.metrics.metric_converter import MetricConverter
from worker.communicator.central_client import CentralClient

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
            
            # 初始化日志收集器
            self.log_collector = LogCollector()
            app_logger.info("Log collector initialized")
            
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
                # 这里可以添加定期任务
                # 例如：发送日志和指标到中心端
                import time
                time.sleep(10)
        except KeyboardInterrupt:
            app_logger.info("Worker stopped by user")
        except Exception as e:
            app_logger.error(f"Worker error: {e}")


if __name__ == "__main__":
    worker = Worker()
    worker.run()
