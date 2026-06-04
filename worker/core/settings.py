import os
import json
from typing import List, Literal

# 获取当前文件所在目录的绝对路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 向上一级到worker目录
BASE_DIR = os.path.dirname(BASE_DIR)


class Settings:
    # 基本配置
    host: str = "0.0.0.0"
    port: int = 5501
    debug: bool = True
    version: str = "0.0.0"
    worker_id: str = f"worker_{os.getpid()}"
    
    # 中心端配置
    central_servers: List[str] = ["http://localhost:5500"]
    central_timeout: int = 10
    central_retry_times: int = 3
    
    # gRPC 配置
    grpc_enabled: bool = False  # 是否启用 gRPC
    grpc_server_address: str = "localhost:50051"  # gRPC 服务地址
    grpc_only: bool = False  # 是否只使用 gRPC（禁用 HTTP）
    
    # 日志配置
    log_level: str = "DEBUG"
    log_dir: str = os.path.join(BASE_DIR, "log", "worker.log")
    error_log_dir: str = os.path.join(BASE_DIR, "log", "worker-error.log")
    
    # 日志收集配置
    log_collect_interval: int = 5  # 秒
    log_batch_size: int = 1000
    log_queue_size: int = 10000
    
    # 指标配置
    metric_collect_interval: int = 10  # 秒
    metric_batch_size: int = 500
    
    # 存储配置
    local_storage_path: str = os.path.join(BASE_DIR, "data")
    max_local_storage_size: int = 1024  # MB
    
    # 网络配置
    allow_origins: List[str] = ["*"]
    
    # 安全配置
    api_key: str = ""
    secret_key: str = "your-secret-key-here"
    
    # Kafka 配置（可动态更新
    kafka_enabled: bool = False
    kafka_brokers: str = "localhost:9092"
    kafka_group_id: str = "log-collector-group"
    kafka_topics: list = ["logs"]
    kafka_auto_offset_reset: str = "earliest"
    kafka_enable_auto_commit: bool = False
    kafka_consumer_config: dict = {}
    
    # 消费进度配置
    kafka_offset_report_interval: int = 30  # 秒
    kafka_offset_file_path: str = "kafka_offsets.json"
    
    # 配置更新回调
    _config_update_callbacks: list = []
    
    def update_from_dict(self, config_dict: dict):
        """从字典更新配置"""
        for key, value in config_dict.items():
            # 类型转换
            if hasattr(self, key):
                try:
                    current_value = getattr(self, key)
                    if isinstance(current_value, bool):
                        # 处理布尔值
                        new_val = value.lower() in ("true", "1", "yes", "t", "y") if isinstance(value, str) else bool(value)
                        setattr(self, key, new_val)
                    elif isinstance(current_value, int):
                        setattr(self, key, int(value))
                    elif isinstance(current_value, float):
                        setattr(self, key, float(value))
                    elif isinstance(current_value, list):
                        # kafka_topics 是列表
                        if key == "kafka_topics":
                            setattr(self, key, [t.strip() for t in value.split(",")] if isinstance(value, str) else value)
                        else:
                            setattr(self, key, value)
                    elif isinstance(current_value, dict):
                        # 处理字典类型
                        if isinstance(value, str):
                            try:
                                setattr(self, key, json.loads(value))
                            except:
                                pass
                        else:
                            setattr(self, key, value)
                    else:
                        setattr(self, key, value)
                except Exception as e:
                    print(f"[Settings] Error updating config {key} = {value}: {e}")
        
        # 触发更新回调
        for callback in self._config_update_callbacks:
            try:
                callback()
            except Exception as e:
                print(f"[Settings] Error calling config update callback: {e}")
    
    def register_config_update_callback(self, callback):
        """注册配置更新回调函数"""
        if callback not in self._config_update_callbacks:
            self._config_update_callbacks.append(callback)
    
    def unregister_config_update_callback(self, callback):
        """取消注册配置更新回调函数"""
        if callback in self._config_update_callbacks:
            self._config_update_callbacks.remove(callback)


settings = Settings()
