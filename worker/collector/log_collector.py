import os
import json
import time
import threading
from queue import Queue
from datetime import datetime
from typing import List, Dict, Any

from worker.core.settings import settings


class LogCollector:
    def __init__(self):
        self.log_queue = Queue(maxsize=settings.log_queue_size)
        self.batch_size = settings.log_batch_size
        self.collect_interval = settings.log_collect_interval
        self.local_storage_path = settings.local_storage_path
        self.max_local_storage_size = settings.max_local_storage_size
        
        # 初始化本地存储目录
        os.makedirs(self.local_storage_path, exist_ok=True)
        
        # 启动日志收集线程
        self.collect_thread = threading.Thread(target=self.collect_logs, daemon=True)
        self.collect_thread.start()
        
        # 启动本地存储线程
        self.storage_thread = threading.Thread(target=self.store_logs, daemon=True)
        self.storage_thread.start()
    
    def collect_logs(self):
        """
        收集日志的主循环
        """
        while True:
            try:
                # 这里可以添加从各种来源收集日志的逻辑
                # 例如：从文件、网络、消息队列等收集日志
                # 暂时模拟收集日志
                self.simulate_log_collection()
                time.sleep(self.collect_interval)
            except Exception as e:
                print(f"Error collecting logs: {e}")
                time.sleep(1)
    
    def store_logs(self):
        """
        存储日志到本地
        """
        while True:
            try:
                batch = []
                # 批量获取日志
                while len(batch) < self.batch_size:
                    try:
                        log = self.log_queue.get(timeout=1)
                        batch.append(log)
                    except Exception:
                        break
                
                if batch:
                    self.save_to_local(batch)
            except Exception as e:
                print(f"Error storing logs: {e}")
                time.sleep(1)
    
    def save_to_local(self, logs: List[Dict[str, Any]]):
        """
        将日志保存到本地文件
        """
        # 按日期分文件存储
        date_str = datetime.now().strftime("%Y-%m-%d")
        file_path = os.path.join(self.local_storage_path, f"logs_{date_str}.jsonl")
        
        # 写入日志文件
        with open(file_path, 'a', encoding='utf-8') as f:
            for log in logs:
                f.write(json.dumps(log, ensure_ascii=False) + '\n')
        
        # 检查存储大小，清理旧文件
        self.check_storage_size()
    
    def check_storage_size(self):
        """
        检查本地存储大小，清理旧文件
        """
        total_size = 0
        files = []
        
        # 计算总存储大小
        for file_name in os.listdir(self.local_storage_path):
            file_path = os.path.join(self.local_storage_path, file_name)
            if os.path.isfile(file_path):
                file_size = os.path.getsize(file_path) / (1024 * 1024)  # 转换为MB
                total_size += file_size
                files.append((file_path, os.path.getmtime(file_path)))
        
        # 清理旧文件
        if total_size > self.max_local_storage_size:
            # 按修改时间排序，删除最旧的文件
            files.sort(key=lambda x: x[1])
            while total_size > self.max_local_storage_size and files:
                file_path, _ = files.pop(0)
                file_size = os.path.getsize(file_path) / (1024 * 1024)
                total_size -= file_size
                os.remove(file_path)
    
    def simulate_log_collection(self):
        """
        模拟日志收集
        """
        # 模拟生成日志
        for i in range(10):
            log = {
                "timestamp": datetime.now().isoformat(),
                "level": "INFO",
                "message": f"Simulated log message {i}",
                "source": "simulation",
                "worker_id": settings.worker_id
            }
            self.log_queue.put(log)
    
    def add_log(self, log: Dict[str, Any]):
        """
        添加日志到队列
        """
        self.log_queue.put(log)
    
    def get_queue_size(self) -> int:
        """
        获取当前队列大小
        """
        return self.log_queue.qsize()
