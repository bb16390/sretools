# Worker 模块

Worker模块是SRE Tools平台的分布式工作端程序，负责在各个机房执行日志收集、指标转换和与中心端的通信等任务。

## 功能特性

- **分布式日志落地**：收集和存储本地日志
- **分布式日志转指标**：将日志转换为可监控的指标
- **与中心端通信**：向中心端发送日志和指标数据
- **跨机房中心端互备自动切换**：当中心端故障时自动切换到备用中心端

## 目录结构

```
worker/
├── adapter/          # 数据适配器模块
│   ├── base.py               # 适配器基类
│   ├── clickhouse_adapter.py      # ClickHouse 适配器
│   ├── http_adapter.py          # HTTP 适配器
│   ├── influxdb_adapter.py      # InfluxDB 适配器
│   ├── kafka_adapter.py       # Kafka 适配器
│   ├── redis_adapter.py         # Redis 适配器
│   └── sql_adapter.py          # SQL 适配器
├── core/             # 核心模块
│   ├── __init__.py
│   ├── auth.py       # 认证模块
│   ├── logging.py    # 日志模块
│   └── settings.py   # 配置管理
├── grpc/             # gRPC 通信模块
│   ├── __init__.py
│   ├── client.py     # gRPC 客户端
│   ├── worker_pb2.py         # gRPC 消息定义
│   └── worker_pb2_grpc.py    # gRPC 服务定义
├── scheduler/        # 任务调度模块
│   ├── __init__.py
│   ├── base_task.py         # 任务基类
│   ├── task_scheduler.py   # 任务调度器
│   ├── trade_day_cache.py # 交易日缓存
│   └── tasks/              # 任务实现
│       ├── database_collector_task.py  # 数据库收集任务
│       ├── kafka_collector_task.py   # Kafka 收集任务
│       ├── log_collector_task.py    # 日志收集任务
│       └── metric_converter_task.py  # 指标转换任务
├── transformer/      # 数据转换模块
│   ├── __init__.py
│   ├── base.py       # 转换器基类
│   ├── executor.py   # 转换执行器
│   ├── loader.py     # 转换器加载器
│   ├── registry.py # 转换器注册表
│   └── scripts/        # 转换脚本
│       ├── aggregator.py       # 聚合脚本
│       ├── filter.py         # 过滤脚本
│       ├── formatter.py    # 格式化脚本
│       ├── json_parser.py   # JSON 解析脚本
│       └── metric_converter.py  # 指标转换脚本
├── scripts/        # 工具脚本
│   └── __init__.py
├── main.py           # 主入口
└── run.sh            # 启动脚本
```

## 配置说明

配置文件位于 `worker/core/settings.py`，主要配置项包括：

- **基本配置**：host、port、debug、version、worker_id
- **中心端配置**：central_servers、central_timeout、central_retry_times
- **日志配置**：log_level、log_dir、error_log_dir
- **日志收集配置**：log_collect_interval、log_batch_size、log_queue_size
- **指标配置**：metric_collect_interval、metric_batch_size
- **存储配置**：local_storage_path、max_local_storage_size
- **网络配置**：allow_origins
- **安全配置**：api_key、secret_key

## 启动方法

1. 进入worker目录：
   ```bash
   cd worker
   ```

2. 运行启动脚本：
   ```bash
   ./run.sh
   ```

3. 或者直接运行main.py：
   ```bash
   python3 main.py
   ```

## 测试

测试文件位于 `tests/worker/` 目录下，运行测试：

```bash
python -m pytest tests/worker/
```

## 监控

Worker模块会定期向中心端发送心跳和指标数据，中心端可以通过这些数据监控Worker的运行状态。

## 故障处理

- **中心端故障**：Worker会自动检测中心端健康状态，当中心端故障时会自动切换到备用中心端
- **网络故障**：当网络故障时，Worker会将日志和指标数据存储在本地，待网络恢复后再发送到中心端
- **存储不足**：当本地存储不足时，Worker会自动清理旧的日志文件
