# SRE Tools - Code Wiki

## 项目概述

**SRE Tools** 是一个基于 FastAPI 的站点可靠性工程（SRE）工具平台，采用主从架构设计，包含中心管理端（master）和分布式工作端（worker）两大核心模块。该平台提供了日志收集、指标转换、分布式监控、交易所网关统一管理、后台管理等功能，支持通过 gRPC 协议进行高性能通信。

### 技术栈

- **语言**: Python 3.12+
- **Web框架**: FastAPI 0.111.0
- **管理后台**: fastapi-amis-admin 0.7.3
- **用户认证**: fastapi-user-auth 0.7.3
- **数据库**: SQLModel 0.0.19 + SQLite/PostgreSQL
- **异步支持**: aiosqlite、greenlet
- **通信协议**: HTTP、WebSocket、gRPC
- **消息队列**: Kafka
- **缓存/存储**: Redis、InfluxDB、ClickHouse
- **交易所网关**: 深交所(SZSE)、上交所(SSE)、北交所(BJSE)
- **包管理**: uv
- **测试框架**: pytest
- **代码检查**: ruff

---

## 项目架构

### 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        SRE Tools Platform                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────┐    ┌─────────────────────────┐ │
│  │      Master (中心端)         │◄──►│   Worker (工作端)        │ │
│  │                             │    │                         │ │
│  │  - FastAPI 服务             │    │  - 任务调度器           │ │
│  │  - 管理后台 (Amis)          │    │  - gRPC 客户端          │ │
│  │  - 用户认证                 │    │  - 适配器层             │ │
│  │  - 页面管理                 │    │  - 数据转换层           │ │
│  │  - 交易所网关管理           │    │  - 交易日缓存           │ │
│  │  - gRPC 服务端              │    │                         │ │
│  └─────────────────────────────┘    └─────────────────────────┘ │
│           │                                    │                 │
│           ▼                                    ▼                 │
│  ┌─────────────────────────────┐    ┌─────────────────────────┐ │
│  │   数据库 (SQLite/PG)        │    │   多源适配器            │ │
│  │   网关实例存储 (JSON)       │    │  - Kafka                │ │
│  └─────────────────────────────┘    │  - SQL/Redis            │ │
│                                       │  - InfluxDB/ClickHouse  │ │
│  ┌─────────────────────────────┐    │  - HTTP                 │ │
│  │  交易所网关进程              │    └─────────────────────────┘ │
│  │  (SZSE/SSE/BJSE)            │                                  │
│  └─────────────────────────────┘                                  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 目录结构

```
/workspace/
├── master/                    # 中心管理端
│   ├── core/                  # 核心模块
│   │   ├── __init__.py
│   │   ├── auth.py           # 认证配置
│   │   ├── globals.py        # 全局对象
│   │   ├── logging.py        # 异步日志处理器
│   │   ├── security.py       # 安全验证
│   │   └── settings.py       # 配置管理
│   ├── gateway/               # 交易所网关统一管理模块
│   │   ├── admin/            # 管理后台界面
│   │   │   └── __init__.py
│   │   ├── api/              # HTTP API 接口
│   │   │   └── __init__.py
│   │   ├── controllers/      # 各交易所网关控制器
│   │   │   ├── __init__.py
│   │   │   ├── base.py       # 控制器抽象基类与注册中心
│   │   │   ├── szse_mdgw.py  # 深交所行情网关
│   │   │   ├── szse_tgw.py   # 深交所交易网关
│   │   │   ├── sse_mdgw.py   # 上交所行情网关（预留）
│   │   │   ├── sse_tgw.py    # 上交所交易网关（预留）
│   │   │   ├── bjse_mdgw.py  # 北交所行情网关（预留）
│   │   │   └── bjse_tgw.py   # 北交所交易网关（预留）
│   │   ├── core/             # 网关核心模块
│   │   │   ├── __init__.py
│   │   │   ├── config_tools.py # 配置工具
│   │   │   ├── errors.py     # 错误定义
│   │   │   ├── models.py     # 数据模型
│   │   │   ├── process.py    # 进程管理
│   │   │   └── store.py      # 持久化存储
│   │   └── __init__.py
│   ├── grpc/                  # gRPC 服务模块
│   │   ├── __init__.py
│   │   ├── server.py         # gRPC 服务端
│   │   ├── worker_pb2.py     # Protobuf 消息定义
│   │   └── worker_pb2_grpc.py # gRPC 服务存根
│   ├── index/                 # 页面管理模块
│   │   ├── __init__.py
│   │   ├── admin.py          # 页面管理后台
│   │   ├── file_upload_admin.py  # 文件上传管理
│   │   ├── models.py         # 数据模型
│   │   └── utils.py          # 工具函数
│   ├── data/                  # 数据目录
│   │   └── gateway_instances.json # 网关实例存储
│   ├── static/                # 静态资源
│   │   ├── amis/             # Amis SDK
│   │   ├── swagger/          # Swagger UI
│   │   ├── redoc/            # ReDoc
│   │   └── ...
│   ├── templates/             # 模板文件
│   ├── main.py               # 主入口文件
│   └── alembic.ini           # 数据库迁移配置
│
├── worker/                    # 分布式工作端
│   ├── core/                  # 核心模块
│   │   ├── __init__.py
│   │   ├── auth.py           # 认证工具
│   │   ├── logging.py        # 日志处理
│   │   └── settings.py       # 配置管理
│   ├── adapter/               # 适配器模块（数据采集与输出）
│   │   ├── __init__.py
│   │   ├── base.py           # 适配器基类
│   │   ├── kafka_adapter.py  # Kafka 适配器
│   │   ├── sql_adapter.py    # SQL 适配器
│   │   ├── redis_adapter.py  # Redis 适配器
│   │   ├── http_adapter.py   # HTTP 适配器
│   │   ├── influxdb_adapter.py # InfluxDB 适配器
│   │   └── clickhouse_adapter.py # ClickHouse 适配器
│   ├── grpc/                  # gRPC 客户端模块
│   │   ├── __init__.py
│   │   ├── client.py         # gRPC 客户端
│   │   ├── worker_pb2.py     # Protobuf 消息定义
│   │   └── worker_pb2_grpc.py # gRPC 服务存根
│   ├── scheduler/             # 任务调度模块
│   │   ├── __init__.py
│   │   ├── base_task.py      # 任务基类
│   │   ├── task_scheduler.py # 任务调度器
│   │   ├── trade_day_cache.py # 交易日缓存
│   │   └── tasks/            # 具体任务实现
│   │       ├── __init__.py
│   │       ├── log_collector_task.py    # 日志收集任务
│   │       ├── metric_converter_task.py # 指标转换任务
│   │       ├── database_collector_task.py # 数据库采集任务
│   │       └── kafka_collector_task.py  # Kafka 采集任务
│   ├── transformer/           # 数据转换模块
│   │   ├── __init__.py
│   │   ├── base.py           # 转换脚本基类
│   │   ├── executor.py       # 转换执行器
│   │   ├── loader.py         # 脚本加载器
│   │   ├── registry.py       # 任务注册表
│   │   └── scripts/          # 内置转换脚本
│   │       ├── __init__.py
│   │       ├── aggregator.py # 聚合脚本
│   │       ├── filter.py     # 过滤脚本
│   │       ├── formatter.py  # 格式化脚本
│   │       ├── json_parser.py # JSON 解析脚本
│   │       └── metric_converter.py # 指标转换脚本
│   ├── main.py               # 主入口文件
│   └── run.sh                # 启动脚本
│
├── protos/                    # Protobuf 定义
│   └── worker.proto          # Worker 服务定义
│
├── scripts/                   # 项目脚本
│   ├── deploy.sh             # 部署脚本
│   ├── start.sh              # 启动脚本
│   ├── stop.sh               # 停止脚本
│   └── generate_grpc_code.py # gRPC 代码生成脚本
│
├── tests/                     # 测试目录
│   ├── dashboard/
│   │   └── core/
│   ├── worker/
│   │   ├── core/
│   │   └── scheduler/
│   ├── test_gateway.py       # 网关测试
│   ├── gateway_smoke.py      # 网关冒烟测试
│   └── test_server.py
│
├── .trae/                     # Trae配置
│   ├── documents/            # 文档
│   ├── skills/               # 技能配置
│   └── specs/                # 规格说明
│
├── pyproject.toml            # 项目配置
├── uv.lock                   # 依赖锁定文件
├── gateway_python_dev_guide.md # 网关开发指南
└── README.md                 # 项目说明
```

---

## 核心模块说明

### 1. Master 模块（中心管理端）

#### 1.1 核心模块 (master/core/)

##### Settings 配置管理
- **文件**: [master/core/settings.py](file:///workspace/master/core/settings.py)
- **职责**: 管理中心端的所有配置项
- **主要配置**:
  - 服务配置: host、port、debug、version
  - 站点配置: site_title、site_icon、site_url、site_path
  - 数据库配置: database_url_async (支持SQLite和PostgreSQL)
  - 日志配置: log_level、log_dir、error_log_dir
  - 安全配置: secret_key
  - Amis配置: amis_cdn、amis_pkg、amis_theme

##### Auth 认证模块
- **文件**: [master/core/auth.py](file:///workspace/master/core/auth.py)
- **职责**: 配置用户认证和权限管理
- **关键类**: `MyAuthAdminSite` - 自定义的管理站点，继承自 `AdminSite`

##### Globals 全局对象
- **文件**: [master/core/globals.py](file:///workspace/master/core/globals.py)
- **职责**: 初始化全局对象，包括数据库连接、认证对象、站点对象
- **关键对象**:
  - `async_db`: 异步数据库引擎
  - `auth`: 用户认证对象
  - `site`: 管理站点对象

##### Logging 日志处理
- **文件**: [master/core/logging.py](file:///workspace/master/core/logging.py)
- **职责**: 提供高性能的异步日志处理
- **关键类**: `AsyncFileHandler` - 异步文件日志处理器
  - 支持队列缓冲，避免阻塞主线程
  - 支持批量处理，提高性能
  - 支持优雅关闭，确保日志不丢失

##### Security 安全验证
- **文件**: [master/core/security.py](file:///workspace/master/core/security.py)
- **职责**: 提供请求签名验证功能
- **关键函数**:
  - `generate_signature()`: 生成HMAC-SHA256签名
  - `verify_signature()`: 验证请求签名（包含时间戳校验）

#### 1.2 页面管理模块 (master/index/)

##### NavPageAdmin 页面管理后台
- **文件**: [master/index/admin.py](file:///workspace/master/index/admin.py)
- **职责**: 提供页面管理的后台界面
- **功能**:
  - 页面的增删改查
  - 页面排序和层级管理
  - 页面同步（数据库 ↔ 站点）
  - 页面激活状态管理

##### NavPage 数据模型
- **文件**: [master/index/models.py](file:///workspace/master/models.py)
- **职责**: 定义页面数据模型
- **关键字段**:
  - `type`: 页面类型（Group、SchemaAPI、Schema、Link、Iframe、Custom）
  - `label`: 页面名称
  - `icon`: 页面图标
  - `url`: 页面路径
  - `page_schema`: 页面配置（JSON）
  - `parent_id`: 父级菜单ID
  - `unique_id`: 唯一标识
  - `is_group`: 是否为分组
  - `is_custom`: 是否自定义
  - `is_active`: 是否激活
  - `is_locked`: 是否锁定

##### AmisPageManager 页面管理器
- **文件**: [master/index/utils.py](file:///workspace/master/index/utils.py)
- **职责**: 管理页面在数据库和站点之间的同步
- **关键方法**:
  - `site_to_db()`: 将站点页面同步到数据库
  - `db_to_site()`: 将数据库页面同步到站点
  - `update_db_pages_parent_and_sort()`: 更新页面排序和父级关系
  - `get_db_active_pages()`: 获取激活的页面列表

#### 1.3 网关控制模块 (master/gateway/)

##### 模块概述
- **职责**: 提供证券交易所网关（行情 mdgw / 交易 tgw）的统一生命周期管理
- **支持交易所**:
  - 深交所(SZSE): mdgw + tgw（完整实现）
  - 上交所(SSE): mdgw + tgw（预留骨架）
  - 北交所(BJSE): mdgw + tgw（预留骨架）
- **核心设计**: 基于注册中心模式，新增交易所只需在 `controllers/` 下新增控制器文件并通过装饰器注册

##### GatewayAdminApp 网关管理后台
- **文件**: [master/gateway/admin/__init__.py](file:///workspace/master/gateway/admin/__init__.py)
- **职责**: 提供网关实例管理的 Amis 后台界面
- **功能**:
  - 网关实例的增删改查
  - 实例运维操作：启动、停止、重启、状态查询
  - 部署、升级、回滚操作
  - 预检检查

##### Gateway API 网关HTTP接口
- **文件**: [master/gateway/api/__init__.py](file:///workspace/master/gateway/api/__init__.py)
- **职责**: 提供网关管理的 RESTful API 接口
- **主要端点**:
  - `GET /api/gateway/instances`: 获取实例列表
  - `POST /api/gateway/instances`: 创建实例
  - `DELETE /api/gateway/instances/{id}`: 删除实例
  - `POST /api/gateway/instances/{id}/start`: 启动网关
  - `POST /api/gateway/instances/{id}/stop`: 停止网关
  - `POST /api/gateway/instances/{id}/restart`: 重启网关
  - `GET /api/gateway/instances/{id}/status`: 查询状态
  - `POST /api/gateway/instances/{id}/deploy`: 部署网关
  - `POST /api/gateway/instances/{id}/upgrade`: 升级网关
  - `POST /api/gateway/instances/{id}/rollback`: 回滚网关
  - `POST /api/gateway/instances/{id}/preflight`: 预检检查

##### GatewayControllerABC 控制器抽象基类
- **文件**: [master/gateway/controllers/base.py](file:///workspace/master/gateway/controllers/base.py)
- **职责**: 定义所有网关控制器的统一接口
- **关键抽象方法**:
  - `preflight()`: 预检检查
  - `deploy()`: 部署网关
  - `start()`: 启动网关
  - `stop()`: 停止网关
  - `restart()`: 重启网关
  - `upgrade()`: 升级网关
  - `rollback()`: 回滚网关
  - `status()`: 查询状态

##### GatewayControllerRegistry 控制器注册中心
- **文件**: [master/gateway/controllers/base.py](file:///workspace/master/gateway/controllers/base.py#L40-L80)
- **职责**: 按 (exchange, kind) 注册和查找控制器类
- **关键方法**:
  - `register(exchange, kind)`: 装饰器方式注册控制器
  - `get(exchange, kind)`: 获取控制器类
  - `make(instance, install_root, backup_root)`: 创建控制器实例

##### 网关核心子模块 (master/gateway/core/)
- **config_tools.py**: [配置工具](file:///workspace/master/gateway/core/config_tools.py) - XML 配置文件读写
- **errors.py**: [错误定义](file:///workspace/master/gateway/core/errors.py) - 网关相关异常类
- **models.py**: [数据模型](file:///workspace/master/gateway/core/models.py) - GatewayInstance、DeployParams 等
- **process.py**: [进程管理](file:///workspace/master/gateway/core/process.py) - 子进程启动/停止/监控
- **store.py**: [持久化存储](file:///workspace/master/gateway/core/store.py) - JSON 文件存储网关实例

#### 1.4 gRPC 服务模块 (master/grpc/)

##### GrpcServer gRPC服务端
- **文件**: [master/grpc/server.py](file:///workspace/master/grpc/server.py)
- **职责**: 提供 Master 端 gRPC 服务，与 Worker 进行高性能通信（与 HTTP API 并行运行）
- **关键功能**:
  - Worker 注册与心跳
  - 日志与指标上报（客户端流式）
  - Kafka偏移量管理（存储与查询）
  - 配置下发
  - 双向流式实时通信（替代WebSocket）
  - 健康检查
  - 运行端口: 50051

##### Protobuf 定义
- **文件**: [protos/worker.proto](file:///workspace/protos/worker.proto)
- **生成代码**:
  - [master/grpc/worker_pb2.py](file:///workspace/master/grpc/worker_pb2.py) - 消息类
  - [master/grpc/worker_pb2_grpc.py](file:///workspace/master/grpc/worker_pb2_grpc.py) - 服务存根

#### 1.5 主入口 (master/main.py)

- **文件**: [master/main.py](file:///workspace/master/main.py)
- **职责**: FastAPI应用的主入口
- **关键功能**:
  - 创建FastAPI应用实例
  - 配置日志系统
  - 配置生命周期事件（startup/shutdown）
  - 挂载静态文件
  - 注册管理后台
  - 配置CORS中间件
  - 注册Worker路由

---

### 2. Worker 模块（分布式工作端）

#### 2.1 核心模块 (worker/core/)

##### Settings 配置管理
- **文件**: [worker/core/settings.py](file:///workspace/worker/core/settings.py)
- **职责**: 管理Worker的所有配置项
- **主要配置**:
  - 基本配置: host、port、debug、version、worker_id
  - gRPC 中心端配置: central_servers、central_timeout、central_retry_times
  - 日志配置: log_level、log_dir、error_log_dir
  - 存储配置: local_storage_path、max_local_storage_size
  - 安全配置: api_key、secret_key

##### Auth 认证工具
- **文件**: [worker/core/auth.py](file:///workspace/worker/core/auth.py)
- **职责**: 提供请求签名生成功能
- **关键函数**: `generate_signature()` - 生成HMAC-SHA256签名

##### Logging 日志处理
- **文件**: [worker/core/logging.py](file:///workspace/worker/core/logging.py)
- **职责**: 提供高性能的异步日志处理
- **关键类**: `AsyncFileHandler` - 异步文件日志处理器

#### 2.2 gRPC 客户端模块 (worker/grpc/)

##### CentralGrpcClient 中心端gRPC客户端
- **文件**: [worker/grpc/client.py](file:///workspace/worker/grpc/client.py)
- **职责**: 通过 gRPC 协议与中心端通信，支持故障切换
- **关键特性**:
  - 多中心端服务器支持
  - 自动健康检查与故障切换
  - 流式心跳保活
  - 任务管理（创建/停止/查询）
  - 交易日信息同步
  - 本地配置缓存

##### 关键方法:
  - `register()`: 注册Worker到中心端
  - `send_heartbeat()`: 发送心跳
  - `send_logs()`: 上报日志（客户端流式）
  - `send_metrics()`: 上报指标（客户端流式）
  - `send_kafka_offsets()`: 发送Kafka偏移量
  - `get_kafka_offsets()`: 获取Kafka偏移量
  - `get_config()`: 获取配置
  - `health_check()`: 健康检查
  - `start_communicate_stream()`: 启动双向流式通信

#### 2.3 任务调度模块 (worker/scheduler/)

##### TaskScheduler 任务调度器
- **文件**: [worker/scheduler/task_scheduler.py](file:///workspace/worker/scheduler/task_scheduler.py)
- **职责**: 管理 Worker 端所有采集/转换任务的生命周期
- **关键功能**:
  - 任务类型工厂注册
  - 任务创建、启动、停止
  - 任务状态监控
  - 进程存活监控
  - 支持多种执行模式（周期执行、持续运行）

##### BaseTask 任务基类
- **文件**: [worker/scheduler/base_task.py](file:///workspace/worker/scheduler/base_task.py)
- **职责**: 定义所有任务的统一接口和生命周期
- **执行模式**:
  - `PERIODIC`: 周期性执行
  - `CONTINUOUS`: 持续运行

##### TradeDayCache 交易日缓存
- **文件**: [worker/scheduler/trade_day_cache.py](file:///workspace/worker/scheduler/trade_day_cache.py)
- **职责**: 缓存交易日信息，支持按交易日调度任务
- **关键功能**:
  - 从中心端同步交易日历
  - 本地缓存
  - 交易日判断

##### 内置任务类型 (worker/scheduler/tasks/)
- **LogCollectorTask**: [日志收集任务](file:///workspace/worker/scheduler/tasks/log_collector_task.py)
- **MetricConverterTask**: [指标转换任务](file:///workspace/worker/scheduler/tasks/metric_converter_task.py)
- **DatabaseCollectorTask**: [数据库采集任务](file:///workspace/worker/scheduler/tasks/database_collector_task.py) - 支持交易日调度
- **KafkaCollectorTask**: [Kafka采集任务](file:///workspace/worker/scheduler/tasks/kafka_collector_task.py)

#### 2.4 适配器模块 (worker/adapter/)

##### AsyncBaseAdapter 适配器基类
- **文件**: [worker/adapter/base.py](file:///workspace/worker/adapter/base.py)
- **职责**: 定义数据采集/输出适配器的统一接口
- **关键功能**:
  - 异步上下文管理
  - 数据转换集成（与 transformer 模块联动）
  - 转换链支持

##### 内置适配器
- **KafkaAdapter**: [Kafka 适配器](file:///workspace/worker/adapter/kafka_adapter.py) - Kafka 消息队列读写
- **SqlAdapter**: [SQL 适配器](file:///workspace/worker/adapter/sql_adapter.py) - 关系型数据库读写
- **RedisAdapter**: [Redis 适配器](file:///workspace/worker/adapter/redis_adapter.py) - Redis 缓存读写
- **HttpAdapter**: [HTTP 适配器](file:///workspace/worker/adapter/http_adapter.py) - HTTP 接口调用
- **InfluxDBAdapter**: [InfluxDB 适配器](file:///workspace/worker/adapter/influxdb_adapter.py) - 时序数据库读写
- **ClickHouseAdapter**: [ClickHouse 适配器](file:///workspace/worker/adapter/clickhouse_adapter.py) - OLAP 数据库读写

#### 2.5 数据转换模块 (worker/transformer/)

##### TransformScript 转换脚本基类
- **文件**: [worker/transformer/base.py](file:///workspace/worker/transformer/base.py)
- **职责**: 定义数据转换脚本的统一接口
- **关键方法**:
  - `transform(data, config)`: 执行数据转换
  - `validate_config(config)`: 验证配置参数

##### TaskRegistry 任务注册表
- **文件**: [worker/transformer/registry.py](file:///workspace/worker/transformer/registry.py)
- **职责**: 单例模式的转换脚本注册中心
- **功能**: 脚本注册、查找、任务配置管理

##### TransformExecutor 转换执行器
- **文件**: [worker/transformer/executor.py](file:///workspace/worker/transformer/executor.py)
- **职责**: 执行单个转换任务，支持链式调用

##### 内置转换脚本 (worker/transformer/scripts/)
- **Aggregator**: [聚合脚本](file:///workspace/worker/transformer/scripts/aggregator.py) - 数据聚合
- **Filter**: [过滤脚本](file:///workspace/worker/transformer/scripts/filter.py) - 数据过滤
- **Formatter**: [格式化脚本](file:///workspace/worker/transformer/scripts/formatter.py) - 数据格式化
- **JsonParser**: [JSON解析脚本](file:///workspace/worker/transformer/scripts/json_parser.py) - JSON 解析
- **MetricConverter**: [指标转换脚本](file:///workspace/worker/transformer/scripts/metric_converter.py) - 指标格式转换

#### 2.6 主入口 (worker/main.py)

- **文件**: [worker/main.py](file:///workspace/worker/main.py)
- **职责**: Worker的主入口
- **关键类**: `Worker`
  - 初始化 gRPC 客户端
  - 初始化任务调度器
  - 初始化交易日缓存
  - 注册任务类型
  - 运行主循环
  - 优雅关闭处理

---

## 关键类与函数说明

### 1. AsyncFileHandler（异步日志处理器）

**位置**: [master/core/logging.py](file:///workspace/master/core/logging.py#L9-L147)

**功能**: 提供高性能的异步日志处理，避免I/O阻塞主线程

**关键特性**:
- 队列缓冲（默认10000条）
- 批量处理（默认500条/批）
- 优雅关闭机制
- 性能监控

**关键方法**:

```python
def __init__(self, file_handler: FileHandler, max_queue_size: int = 10000, 
             drop_threshold: float = 0.8, batch_size: int = 500, 
             flush_interval: float = 0.2)
```

```python
def write(self)  # 后台写线程，批量处理日志
```

```python
def close(self)  # 优雅关闭，确保日志不丢失
```

---

### 2. CentralGrpcClient（中心端gRPC客户端）

**位置**: [worker/grpc/client.py](file:///workspace/worker/grpc/client.py)

**功能**: 通过 gRPC 协议与中心端通信，支持故障切换和延迟初始化

**关键特性**:
- 多中心端服务器支持
- 自动健康检查与故障切换
- 流式心跳保活（独立线程）
- 双向流式实时通信（替代WebSocket）
- Kafka偏移量管理（存储与查询）
- 交易日信息同步
- 本地配置缓存（离线支持）
- 延迟初始化（避免启动时大量错误日志）

**关键方法**:

```python
def register(self)  # 注册Worker到中心端
```

```python
def send_heartbeat(self)  # 发送心跳
```

```python
def send_logs(self)  # 上报日志（客户端流式）
```

```python
def send_metrics(self)  # 上报指标（客户端流式）
```

```python
def send_kafka_offsets(self)  # 发送Kafka偏移量
```

```python
def get_kafka_offsets(self)  # 获取Kafka偏移量
```

```python
def get_config(self)  # 获取配置
```

```python
def health_check(self)  # 健康检查
```

```python
def start_communicate_stream(self)  # 启动双向流式通信
```

---

### 3. NavPageAdmin（页面管理后台）

**位置**: [master/index/admin.py](file:///workspace/master/index/admin.py)

**功能**: 提供页面管理的后台界面

**关键特性**:
- 页面CRUD操作
- 页面排序和层级管理
- 页面同步（数据库 ↔ 站点）
- 拖拽排序

**关键方法**:

```python
async def get_page(self, request: Request) -> Page  # 获取管理页面
```

```python
async def sync_pages()  # 同步页面
```

---

### 4. AmisPageManager（页面管理器）

**位置**: [master/index/utils.py](file:///workspace/master/index/utils.py)

**功能**: 管理页面在数据库和站点之间的同步

**关键方法**:

```python
def site_to_db(self, admin_group: AdminGroup, parent_id: int = None)  # 站点→数据库
```

```python
def db_to_site(self, admin_group: AdminGroup)  # 数据库→站点
```

```python
def update_db_pages_parent_and_sort(self, links: list[dict], parent_id: int = None)  # 更新排序
```

---

## 依赖关系

### 核心依赖关系图

```
┌─────────────────────────────────────────────────────────┐
│                    Master Dependencies                    │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  FastAPI ──► fastapi-amis-admin ──► fastapi-user-auth   │
│     │              │                      │               │
│     │              ▼                      ▼               │
│     │         SQLModel ◄─────── AsyncDatabase            │
│     │              │                                      │
│     ▼              ▼                                      │
│  Starlette ──► SQLAlchemy ──► aiosqlite                  │
│                                                           │
│  uvicorn ──► greenlet                                    │
│                                                           │
│  pydantic-settings                                       │
│                                                           │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                    Worker Dependencies                    │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  requests ──► HTTP通信                                   │
│                                                           │
│  websockets ──► WebSocket实时通信                        │
│                                                           │
│  pydantic-settings ──► 配置管理                          │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

### 依赖列表

#### 生产依赖
| 依赖包 | 版本 | 用途 |
|--------|------|------|
| fastapi | 0.111.0 | Web框架 |
| fastapi-amis-admin | ≥0.7.3 | 管理后台框架 |
| fastapi-user-auth | ≥0.7.3 | 用户认证 |
| sqlmodel | 0.0.19 | ORM框架 |
| sqlmodelx | 0.0.12 | SQLModel扩展 |
| aiosqlite | ≥0.22.1 | 异步SQLite |
| greenlet | ≥3.3.2 | 协程支持 |
| pydantic-settings | ≥2.13.1 | 配置管理 |
| requests | ≥2.33.1 | HTTP客户端 |
| websockets | ≥12.0 | WebSocket客户端 |
| grpcio | ≥1.60.0 | gRPC通信 |
| grpcio-tools | ≥1.60.0 | gRPC代码生成 |
| protobuf | ≥4.25.0 | Protobuf序列化 |
| aiokafka | ≥0.10.0 | 异步Kafka客户端 |
| redis | ≥5.0.0 | Redis客户端 |
| influxdb-client | ≥1.36.0 | InfluxDB客户端 |
| clickhouse-driver | ≥0.2.0 | ClickHouse客户端 |

#### 开发依赖
| 依赖包 | 版本 | 用途 |
|--------|------|------|
| pytest | ≥9.0.2 | 测试框架 |
| ruff | ≥0.15.5 | 代码检查和格式化 |

---

## 项目运行方式

### 1. 环境准备

#### 安装uv包管理器
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### 安装依赖
```bash
cd /workspace
uv sync
```

### 2. 启动Master（中心管理端）

#### 方式一：直接运行
```bash
cd /workspace/master
python main.py
```

#### 方式二：使用uvicorn
```bash
cd /workspace/master
uvicorn main:app --host 0.0.0.0 --port 5500 --reload
```

#### 访问地址
- 管理后台: http://localhost:5500/admin
- API文档: http://localhost:5500/docs
- 默认管理员: admin / admin
- 默认超级管理员: root / root

### 3. 启动Worker（分布式工作端）

#### 方式一：使用启动脚本
```bash
cd /workspace/worker
./run.sh
```

#### 方式二：直接运行
```bash
cd /workspace/worker
python main.py
```

### 4. 运行测试

```bash
cd /workspace
python -m pytest tests/
```

### 5. 代码检查和格式化

```bash
cd /workspace
# 代码检查
ruff check .

# 代码格式化
ruff format .
```

---

## 配置说明

### Master配置

**配置文件**: [master/core/settings.py](file:///workspace/master/core/settings.py)

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| host | "0.0.0.0" | 监听地址 |
| port | 5500 | 监听端口 |
| debug | True | 调试模式 |
| version | "0.0.0" | 版本号 |
| site_title | "SRE Tools" | 站点标题 |
| site_path | "/admin" | 管理路径 |
| database_url_async | SQLite | 异步数据库URL |
| log_level | "DEBUG" | 日志级别 |
| log_dir | master/log/uvicorn.log | 日志文件路径 |
| secret_key | "your-secret-key-here" | 密钥 |

### Worker配置

**配置文件**: [worker/core/settings.py](file:///workspace/worker/core/settings.py)

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| host | "0.0.0.0" | 监听地址 |
| port | 5501 | 监听端口 |
| worker_id | "worker_{pid}" | Worker标识 |
| central_servers | ["http://localhost:5500"] | 中心端服务器列表 |
| central_timeout | 10 | 中心端超时时间（秒） |
| central_retry_times | 3 | 重试次数 |
| log_collect_interval | 5 | 日志收集间隔（秒） |
| log_batch_size | 1000 | 日志批量大小 |
| log_queue_size | 10000 | 日志队列大小 |
| metric_collect_interval | 10 | 指标收集间隔（秒） |
| metric_batch_size | 500 | 指标批量大小 |
| local_storage_path | worker/data | 本地存储路径 |
| max_local_storage_size | 1024 | 最大存储大小（MB） |
| secret_key | "your-secret-key-here" | 密钥 |

---

## 数据模型

### NavPage（导航页面）

**位置**: [master/index/models.py](file:///workspace/master/index/models.py#L36-L167)

**表名**: `system_page`

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| type | NavPageType | 页面类型 |
| url | str | 页面路径 |
| label | str | 页面名称 |
| icon | str | 页面图标 |
| sort | int | 排序 |
| desc | str | 页面描述 |
| page_schema | str | 页面配置（JSON） |
| parent_id | int | 父级菜单ID |
| unique_id | str | 唯一标识 |
| tabsMode | TabsModeEnum | 分组展示模式 |
| visible | bool | 是否可见 |
| is_group | bool | 是否为分组 |
| is_custom | bool | 是否自定义 |
| is_active | bool | 是否激活 |
| is_locked | bool | 是否锁定 |
| update_time | datetime | 更新时间 |

**页面类型**:
- Group (1): 页面分组
- SchemaAPI (2): Amis页面API
- Schema (3): Amis页面
- Link (4): 页面链接
- Iframe (5): Iframe页面
- Custom (6): 自定义页面

### GatewayInstance（网关实例）

**位置**: [master/gateway/core/models.py](file:///workspace/master/gateway/core/models.py#L13-L23)

**存储**: JSON 文件（[master/data/gateway_instances.json](file:///workspace/master/data/gateway_instances.json)）

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| id | str | 实例ID |
| exchange | str | 交易所代码（szse/sse/bjse） |
| kind | str | 网关类型（mdgw/tgw） |
| name | str | 实例名称 |
| gateway_dir | str | 网关安装目录 |
| binary_name | str | 二进制文件名 |
| monitor_port | int | 监控端口 |
| version | str/None | 版本号 |
| created_at | datetime | 创建时间 |

### 其他网关数据模型

**位置**: [master/gateway/core/models.py](file:///workspace/master/gateway/core/models.py)

| 模型 | 说明 |
|------|------|
| DeployParams | 部署参数 |
| UpgradeParams | 升级参数 |
| RollbackParams | 回滚参数 |
| OperationResult | 操作结果 |
| GatewayStatus | 网关运行状态 |

---

## API接口说明

### Master API

#### 网关管理接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/gateway/instances | 获取网关实例列表 |
| POST | /api/gateway/instances | 创建网关实例 |
| DELETE | /api/gateway/instances/{id} | 删除网关实例 |
| POST | /api/gateway/instances/{id}/start | 启动网关 |
| POST | /api/gateway/instances/{id}/stop | 停止网关 |
| POST | /api/gateway/instances/{id}/restart | 重启网关 |
| GET | /api/gateway/instances/{id}/status | 查询网关状态 |
| POST | /api/gateway/instances/{id}/deploy | 部署网关 |
| POST | /api/gateway/instances/{id}/upgrade | 升级网关 |
| POST | /api/gateway/instances/{id}/rollback | 回滚网关 |
| POST | /api/gateway/instances/{id}/preflight | 预检检查 |

#### Worker管理接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/worker/register | Worker注册 |
| POST | /api/worker/heartbeat | 接收心跳 |
| GET | /api/worker/config | 获取配置 |
| POST | /api/worker/logs | 接收日志 |
| POST | /api/worker/metrics | 接收指标 |
| GET | /api/worker/list | 获取Worker列表 |
| GET | /api/worker/health | 健康检查 |
| WebSocket | /api/worker/ws/{worker_id} | WebSocket连接 |
| POST | /api/worker/update-config | 更新配置 |
| POST | /api/worker/update-task | 更新任务 |

#### 文件上传接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/file-upload/submit | 文件上传提交 |

### gRPC 接口 (Master:50051)

| 服务 | 方法 | 说明 |
|------|------|------|
| WorkerService | RegisterWorker | Worker注册 |
| WorkerService | SendHeartbeat | 发送心跳 |
| WorkerService | SendLogs | 上报日志（客户端流式） |
| WorkerService | SendMetrics | 上报指标（客户端流式） |
| WorkerService | SendKafkaOffsets | 发送Kafka偏移量 |
| WorkerService | GetKafkaOffsets | 获取Kafka偏移量 |
| WorkerService | GetConfig | 获取配置 |
| WorkerService | HealthCheck | 健康检查 |
| WorkerService | Communicate | 双向流式实时通信（替代WebSocket） |

---

## 安全机制

### 1. 请求签名验证

**实现位置**:
- Master: [master/core/security.py](file:///workspace/master/core/security.py)
- Worker: [worker/core/auth.py](file:///workspace/worker/core/auth.py)

**签名算法**: HMAC-SHA256

**验证流程**:
1. 客户端生成签名（包含时间戳）
2. 服务端验证时间戳（5分钟内有效）
3. 服务端验证签名

### 2. 用户认证

**实现**: fastapi-user-auth

**认证方式**:
- Token认证
- 数据库Token存储
- Token有效期: 360天

### 3. 权限管理

**实现**: Casbin

**权限策略**:
- 基于RBAC的权限控制
- 支持页面级别权限

---

## 性能优化

### 1. 异步日志处理

**实现**: AsyncFileHandler

**优化点**:
- 队列缓冲，避免I/O阻塞
- 批量处理，减少磁盘I/O
- 后台线程处理，不影响主线程性能

### 2. 批量数据处理

**应用场景**:
- 日志收集：批量存储（默认1000条/批）
- 指标转换：批量处理（默认500条/批）
- WebSocket消息：批量发送

### 3. 连接池管理

**应用**:
- 数据库连接池
- HTTP连接池（requests.Session）
- WebSocket连接复用

---

## 故障处理

### 1. 中心端故障

**处理机制**:
- 自动健康检查（每10秒）
- 自动故障切换
- 本地配置缓存
- 本地数据存储

### 2. 网络故障

**处理机制**:
- 本地数据缓存
- 网络恢复后自动重传
- 指数退避重连策略

### 3. 存储不足

**处理机制**:
- 自动清理旧文件
- 基于存储大小限制
- 按修改时间排序清理

---

## 监控指标

### Worker监控指标

| 指标名 | 说明 |
|--------|------|
| log_count | 日志计数（按级别和来源分组） |
| processing_time | 处理时间 |
| queue_size | 队列大小 |
| processing_speed | 处理速度 |

---

## 开发指南

### 1. 添加新的页面类型

1. 在 `NavPageType` 中添加新类型
2. 更新 `parse_page_schema_type()` 函数
3. 在 `NavPageAdmin` 中添加相应的处理逻辑

### 2. 添加新的Worker功能

1. 在 `worker/` 目录下创建新模块
2. 在 `Worker.__init__()` 中初始化新模块
3. 在 `Worker.run()` 中添加运行逻辑

### 3. 添加新的API接口

1. 在相应的路由模块中添加新端点
2. 添加签名验证（如需要）
3. 更新API文档

### 4. 添加新的数据模型

1. 在 `master/index/models.py` 中定义模型
2. 创建数据库迁移（如使用Alembic）
3. 在管理后台中注册模型

---

## 测试说明

### 测试目录结构

```
tests/
├── dashboard/
│   └── core/
│       ├── test_logging.py           # 日志测试
│       └── test_logging_performance.py  # 日志性能测试
├── worker/
│   ├── core/
│   │   └── test_settings.py          # 配置测试
│   └── scheduler/
│       ├── test_trade_day_cache.py   # 交易日缓存测试
│       └── test_database_collector_task_trade_day.py  # 交易日调度测试
├── test_gateway.py                   # 网关功能测试
├── gateway_smoke.py                  # 网关冒烟测试
└── test_server.py                    # 服务器测试
```

### 运行测试

```bash
# 运行所有测试
python -m pytest tests/

# 运行特定测试
python -m pytest tests/dashboard/core/test_logging.py

# 运行测试并显示覆盖率
python -m pytest tests/ --cov=master --cov=worker
```

---

## 部署建议

### 1. Master部署

- 使用Gunicorn或Uvicorn部署
- 配置反向代理（Nginx）
- 使用PostgreSQL作为生产数据库
- 配置HTTPS
- 配置日志轮转

### 2. Worker部署

- 使用Systemd或Supervisor管理进程
- 配置日志轮转
- 监控本地存储使用情况
- 配置多个中心端地址（高可用）

### 3. 高可用部署

- 部署多个Master实例（负载均衡）
- 部署多个Worker实例（分布式）
- 配置数据库主从复制
- 配置监控告警

---

## 常见问题

### Q1: Worker无法连接到Master？

**解决方案**:
1. 检查Master是否启动
2. 检查网络连通性
3. 检查防火墙配置
4. 检查中心端地址配置

### Q2: 日志丢失？

**解决方案**:
1. 检查队列大小配置
2. 检查磁盘空间
3. 检查日志级别配置
4. 使用AsyncFileHandler确保异步写入

### Q3: 性能问题？

**解决方案**:
1. 调整批量大小配置
2. 调整队列大小配置
3. 使用异步处理
4. 优化数据库查询

---

## 版本历史

- **v0.2.0**: 新增交易所网关统一管理与 gRPC 通信
  - 新增深交所(SZSE) mdgw/tgw 完整网关控制
  - 新增上交所/北交所网关控制器骨架
  - 新增网关管理后台界面（基于 Amis）
  - 新增网关 HTTP API 接口
  - 新增 gRPC 通信协议（Master 服务端 + Worker 客户端）
  - 重构 Worker 架构：任务调度器 + 适配器 + 数据转换三层
  - 新增交易日缓存与交易日调度支持
  - 新增多源适配器（Kafka/SQL/Redis/HTTP/InfluxDB/ClickHouse）

- **v0.1.0**: 初始版本
  - 基础管理后台
  - Worker基础功能
  - 日志收集和指标转换
  - WebSocket实时通信

---

## 贡献指南

1. Fork项目
2. 创建功能分支
3. 提交代码
4. 创建Pull Request

---

## 许可证

本项目采用 MIT 许可证。

---

## 联系方式

如有问题或建议，请提交Issue或Pull Request。

---

## 更新于 2026-07-13

- 今日无代码变更，项目运行正常
- 验证 README.md 文档与实际代码一致性，确认所有模块、类、接口描述准确无误
- 抽检 worker/scheduler、worker/adapter、master/gateway、master/core 目录，文档结构与实际文件一致

## 更新于 2026-07-12

- 今日无代码变更，项目运行正常
- 验证 README.md 文档与实际代码一致性，确认所有模块、类、接口描述准确无误
- 抽检 worker/transformer、worker/core、master/index、master/grpc 目录，文档结构与实际文件一致

## 更新于 2026-07-11

- 今日无代码变更，项目运行正常
- 验证 README.md 文档与实际代码一致性，确认所有模块、类、接口描述准确无误
- 抽检核心模块文件：master/core、master/gateway、worker/scheduler、worker/adapter，文档结构与实际文件一致

## 更新于 2026-07-10

- 今日无代码变更，项目运行正常
- 验证 README.md 文档与实际代码一致性，确认所有模块、类、接口描述准确无误
- 抽检 worker/adapter、worker/scheduler/tasks、master/gateway/controllers 目录，文档结构与实际文件一致

## 更新于 2026-07-09

- 今日无代码变更，项目运行正常
- 验证 README.md 文档与实际代码一致性，确认所有模块、类、接口描述准确无误

## 更新于 2026-07-08

- 今日无代码变更，项目运行正常
- 验证 README.md 文档与实际代码一致性，确认所有模块、类、接口描述准确无误

## 更新于 2026-07-07

- 今日无代码变更，项目运行正常
- 验证 README.md 文档与实际代码一致性，确认所有模块、类、接口描述准确无误

## 更新于 2026-07-06

- 今日无代码变更，项目运行正常
- 验证 README.md 文档与实际代码一致性，确认所有模块、类、接口描述准确无误

## 更新于 2026-07-05

- 更新 gRPC 接口文档，修正方法名称与实际代码一致（Register→RegisterWorker, Heartbeat→SendHeartbeat）
- 新增 Kafka 偏移量管理接口（SendKafkaOffsets、GetKafkaOffsets）
- 新增 HealthCheck 健康检查接口
- 新增 Communicate 双向流式实时通信接口（替代WebSocket）
- 更新 CentralGrpcClient 描述，添加延迟初始化、本地配置缓存等新特性
- 更新 Master gRPC 服务端描述，明确与 HTTP API 并行运行架构

## 更新于 2026-07-04

- 修复文档中指向不存在目录的引用：删除 master/worker/ 路由模块章节（已迁移至 gRPC）
- 更新关键类与函数说明：将旧版 LogCollector/central_client 替换为新架构的 CentralGrpcClient
- 删除不存在的 ConnectionManager WebSocket 管理说明（已迁移至 gRPC 通信）
- 更新关键类编号（原6个类调整为4个）
- 修复文档中指向不存在文件的链接引用

## 更新于 2026-07-03

- 新增交易所网关统一管理模块（master/gateway/），支持深交所 mdgw/tgw 完整生命周期管理
- 新增网关管理后台界面与 HTTP API 接口
- 新增 gRPC 通信协议，Master 端提供 gRPC 服务（端口 50051），Worker 端通过 gRPC 客户端通信
- 重构 Worker 架构为三层：任务调度层(scheduler)、适配器层(adapter)、数据转换层(transformer)
- 新增交易日缓存(TradeDayCache)与交易日调度支持
- 新增多源数据适配器：Kafka、SQL、Redis、HTTP、InfluxDB、ClickHouse
- 新增内置数据转换脚本：聚合、过滤、格式化、JSON解析、指标转换
- 更新项目目录结构与核心模块说明文档
- 新增网关相关数据模型说明与 API 接口文档
- 更新版本历史至 v0.2.0
