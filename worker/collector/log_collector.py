
import os
import json
import time
import threading
from queue import Queue
from typing import List, Dict, Any, Optional

from worker.core.settings import settings
from worker.adapter.kafka_adapter import KafkaAdapter


class LogCollector:
    def __init__(
        self, central_client=None):
        self.log_queue = Queue(maxsize=settings.log_queue_size)
        self.batch_size = settings.log_batch_size
        self.collect_interval = settings.log_collect_interval
        self.local_storage_path = settings.local_storage_path
        self.max_local_storage_size = settings.max_local_storage_size
        self.offset_file_path = os.path.join(
            self.local_storage_path,
            settings.kafka_offset_file_path
        )
        
        # 确保存储路径
        os.makedirs(self.local_storage_path, exist_ok=True)
        
        # 初始化 Kafka 适配器（如果启用）
        self.kafka_adapter: Optional[KafkaAdapter] = None
        if settings.kafka_enabled:
            self.kafka_adapter = KafkaAdapter(
                brokers=settings.kafka_brokers,
                group_id=settings.kafka_group_id,
                topics=settings.kafka_topics,
                auto_offset_reset=settings.kafka_auto_offset_reset,
                enable_auto_commit=settings.kafka_enable_auto_commit,
                consumer_config=settings.kafka_consumer_config
            )
        
        self.central_client = central_client
        
        # 当前消费进度
        self.current_offsets: Dict[str, Dict[int, int]] = {}
        self.last_report_time = 0
        self.offset_report_interval = settings.kafka_offset_report_interval
        
        # 加载保存的消费进度
        self._load_offsets()
        
        # 如果有 Kafka 适配器，设置消费进度
        if self.kafka_adapter and self.current_offsets:
            try:
                self.kafka_adapter.seek(self.current_offsets)
            except Exception as e:
                print(f"Error seeking to saved offsets: {e}")
        
        # 启动收集线程
        self.collect_thread = threading.Thread(target=self.collect_logs, daemon=True)
        self.collect_thread.start()
        
        # 启动本地存储线程
        self.storage_thread = threading.Thread(target=self.store_logs, daemon=True)
        self.storage_thread.start()
    
    def _load_offsets(self):
        """从本地文件或 Master 端加载消费进度
        """
        try:
            # 先从本地加载
            if os.path.exists(self.offset_file_path):
                try:
                    with open(self.offset_file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self.current_offsets = data.get('offsets', {})
                        print(f"Loaded offsets from local file: {self.current_offsets}")
                except Exception as e:
                    self.current_offsets = {}
            else:
                self.current_offsets = {}
            
            # 如果本地没有，尝试从 Master 加载
            if not self.current_offsets and self.central_client:
                try:
                    master_offsets = self.central_client.get_kafka_offsets()
                    if master_offsets and 'offsets' in master_offsets:
                        self.current_offsets = master_offsets['offsets']
                        print(f"Loaded offsets from master: {self.current_offsets}")
                        # 保存到本地
                        self._save_offsets()
                except Exception as e:
                    print(f"Error loading offsets from master: {e}")
        except Exception as e:
            self.current_offsets = {}
    
    def _save_offsets(self):
        """保存消费进度到本地文件
        """
        try:
            data = {
                'offsets': self.current_offsets,
                'timestamp': time.time()
            }
            with open(self.offset_file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving offsets to local file: {e}")
    
    def _report_offsets_to_master(self):
        """上报消费进度到 Master 端
        """
        if not self.central_client:
            return
        
        try:
            self.central_client.report_kafka_offsets(self.current_offsets)
            print(f"Reported offsets to master: {self.current_offsets}")
        except Exception as e:
            print(f"Error reporting offsets to master: {e}")
    
    def collect_logs(self):
        """收集日志的主循环
        """
        while True:
            try:
                if self.kafka_adapter:
                    # 使用 Kafka 收集
                    msg = self.kafka_adapter.poll(timeout=1.0)
                    if msg:
                        self.log_queue.put(msg)
                        # 更新消费进度
                        topic = msg['topic']
                        partition = msg['partition']
                        offset = msg['offset']
                        if topic not in self.current_offsets:
                            self.current_offsets[topic] = {}
                        self.current_offsets[topic][partition] = offset + 1
                        
                        # 定期保存和上报
                        now = time.time()
                        if now - self.last_report_time >= self.offset_report_interval:
                            self._save_offsets()
                            self._report_offsets_to_master()
                            self.last_report_time = now
                else:
                    # 模拟收集（向后兼容）
                    self.simulate_log_collection()
                    time.sleep(self.collect_interval)
            except Exception as e:
                print(f"Error collecting logs: {e}")
                time.sleep(1)
    
    def store_logs(self):
        """存储日志到本地
        """
        while True:
            try:
                batch = []
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
        """将日志保存到本地文件
        """
        from datetime import datetime
        date_str = datetime.now().strftime("%Y-%m-%d")
        file_path = os.path.join(self.local_storage_path, f"logs_{date_str}.jsonl")
        
        with open(file_path, 'a', encoding='utf-8') as f:
            for log in logs:
                f.write(json.dumps(log, ensure_ascii=False) + '\n')
        
        self.check_storage_size()
    
    def check_storage_size(self):
        """检查本地存储大小，清理旧文件
        """
        total_size = 0
        files = []
        
        for file_name in os.listdir(self.local_storage_path):
            if file_name.startswith('logs_') and file_name.endswith('.jsonl'):
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
    
    def simulate_log_collection(self):
        """模拟日志收集
        """
        from datetime import datetime
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
        """添加日志到队列
        """
        self.log_queue.put(log)
    
    def get_queue_size(self) -> int:
        """获取当前队列大小
        """
        return self.log_queue.qsize()
