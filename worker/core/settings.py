import os
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

    # Master 端 HTTP 地址（供未来 REST/WebSocket 上报使用）；
    # gRPC 客户端不直接读取它，而是使用下方 grpc_server_address。
    central_servers: List[str] = ["http://localhost:5500"]
    central_timeout: int = 10
    central_retry_times: int = 3

    # gRPC 配置
    grpc_enabled: bool = False  # 是否启用 gRPC
    # gRPC 服务器地址（host:port 形式，不要带 http:// 前缀）。
    # 可以是逗号分隔的多个地址，第一个为主地址，其他为故障转移候选。
    grpc_server_address: str = "localhost:50051"
    # 也可用列表形式提供故障转移候选
    grpc_server_addresses: List[str] = ["localhost:50051"]
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


settings = Settings()
