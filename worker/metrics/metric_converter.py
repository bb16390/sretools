import time
import threading
from queue import Queue
from datetime import datetime
from typing import List, Dict, Any

from worker.core.settings import settings


class MetricConverter:
    def __init__(self):
        self.metric_queue = Queue()
        self.batch_size = settings.metric_batch_size
        self.collect_interval = settings.metric_collect_interval
        
        # 指标存储
        self.metrics = {}
        
        # 启动指标转换线程
        self.convert_thread = threading.Thread(target=self.convert_logs_to_metrics, daemon=True)
        self.convert_thread.start()
        
        # 启动指标聚合线程
        self.aggregate_thread = threading.Thread(target=self.aggregate_metrics, daemon=True)
        self.aggregate_thread.start()
    
    def convert_logs_to_metrics(self):
        """
        将日志转换为指标的主循环
        """
        while True:
            try:
                # 这里可以添加从日志队列获取日志的逻辑
                # 暂时模拟日志转换
                self.simulate_log_conversion()
                time.sleep(self.collect_interval)
            except Exception as e:
                print(f"Error converting logs to metrics: {e}")
                time.sleep(1)
    
    def aggregate_metrics(self):
        """
        聚合指标的主循环
        """
        while True:
            try:
                # 每间隔一段时间聚合一次指标
                time.sleep(self.collect_interval)
                self.calculate_aggregates()
            except Exception as e:
                print(f"Error aggregating metrics: {e}")
                time.sleep(1)
    
    def calculate_aggregates(self):
        """
        计算指标聚合值
        """
        # 这里可以添加各种指标的聚合逻辑
        # 例如：计数、平均值、最大值、最小值等
        pass
    
    def simulate_log_conversion(self):
        """
        模拟日志转换为指标
        """
        # 模拟从日志中提取指标
        metrics = [
            {
                "name": "log_count",
                "value": 1,
                "labels": {"level": "INFO", "source": "simulation"},
                "timestamp": datetime.now().timestamp()
            },
            {
                "name": "log_count",
                "value": 1,
                "labels": {"level": "ERROR", "source": "simulation"},
                "timestamp": datetime.now().timestamp()
            },
            {
                "name": "processing_time",
                "value": 0.1,
                "labels": {"operation": "log_processing"},
                "timestamp": datetime.now().timestamp()
            }
        ]
        
        for metric in metrics:
            self.add_metric(metric)
    
    def add_metric(self, metric: Dict[str, Any]):
        """
        添加指标到队列
        """
        self.metric_queue.put(metric)
        
        # 同时更新本地指标存储
        metric_name = metric["name"]
        labels = metric.get("labels", {})
        value = metric["value"]
        
        # 按指标名称和标签分组存储
        key = (metric_name, tuple(sorted(labels.items())))
        if key not in self.metrics:
            self.metrics[key] = []
        
        self.metrics[key].append({
            "value": value,
            "timestamp": metric.get("timestamp", datetime.now().timestamp())
        })
    
    def get_metrics(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取当前所有指标
        """
        return self.metrics
    
    def get_queue_size(self) -> int:
        """
        获取当前指标队列大小
        """
        return self.metric_queue.qsize()
