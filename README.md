# SRE Tools - Code Wiki

**SRE Tools** 是一个基于 FastAPI 的站点可靠性工程（SRE）工具平台，采用主从架构设计，包含中心管理端（master）和分布式工作端（worker）两大核心模块。平台提供了日志收集、指标转换、分布式监控、后台管理、证券交易所网关统一控制（新增）等功能。

### 技术栈

- **语言**: Python 3.12+
- **Web 框架**: FastAPI 0.111.0
- **管理后台**: fastapi-amis-admin 0.7.3
- **用户认证**: fastapi-user-auth 0.7.3
- **数据库**: SQLModel 0.0.19 + SQLite/PostgreSQL
- **异步支持**: aiohttp、aiosqlite、greenlet、asynch
- **通信协议**: gRPC（Master ↔ Worker）、HTTP、WebSocket
- **数据采集与适配**: confluent-kafka、influxdb-client、redis、SQLAlchemy（ClickHouse/MySQL/PostgreSQL）
- **任务调度**: croniter
- **包管理**: uv
- **测试框架**: pytest
- **代码检查**: ruff

---

## 项目架构

### 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        SRE Tools Platform                    │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────────┐         gRPC 50051          ┌──────┐
│  │   Master (中心端)     │ ◄─────────────────────────►│ Worker │
│  │                      │                             │ (工作端) │
│  │  - FastAPI 服务        │                             │  - 任务调度器  │
│  │  - 管理后台           │                             │  - 日志/指标/Kafka/DB采集器 │
│  │  - 用户认证           │                             │  - gRPC 客户端      │
│  │  - 页面管理           │                             │  - 数据转换流水线    │
│  │  - 网关控制模块      │                             │  - 多适配器 (Redis/Kafka/InfluxDB/HTTP/SQL/ClickHouse) │
│  │  - gRPC 服务端       │                             │                      │
│  └──────────────────────┘                             └──────────────────────┘
│           │                                                   │
│           ▼                                                   ▼
│  ┌──────────────────────┐                             ┌──────────────────────┐
│  │  数据库 (SQLite/PG)  │                             │  本地存储 (JSON)     │
│  └──────────────────────┘                             └──────────────────────┘
│                                                               │
│  ┌──────────────────────┐                                     │
│  │  交易所网关控制     │ ◄─── HTTP API / amis-admin            │
│  │  (部署/启停/升级/回滚)│                                     │
│  └──────────────────────┘                                     │
└─────────────────────────────────────────────────────────────┘
```

### 目录结构

```
/workspace/
├── master/                    # 中心管理端
│   ├── core/                  # 核心模块
│   │   ├── __init__.py
│   │   ├── auth.py            # 认证配置（fastapi-user-auth 集成）
│   │   ├── globals.py         # 全局对象：site、auth、数据库连接
│   │   ├── logging.py         # AsyncFileHandler 异步日志处理器
│   │   ├── security.py        # 请求签名验证（HMAC-SHA256）
│   │   └── settings.py        # 配置管理（Pydantic Settings）
│   ├── index/                 # 页面管理模块
│   │   ├── __init__.py
│   │   ├── admin.py           # NavPageAdmin 页面管理后台
│   │   ├── file_upload_admin.py  # 文件上传管理
│   │   ├── models.py          # 页面数据模型（NavPage）
│   │   └── utils.py           # 页面同步与管理工具
│   ├── gateway/               # 交易所网关控制模块（新增）
│   │   ├── __init__.py
│   │   ├── admin/             # amis-admin 管理界面
│   │   │   └── __init__.py    # GatewayInstanceAdmin、GatewayOpsAdmin、GatewayAdminApp
│   │   ├── api/               # HTTP API 路由
│   │   │   └── __init__.py    # /api/gateway/* 路由、实例 CRUD、部署/升级/回滚/启停
│   │   ├── controllers/       # 各交易所控制器（可插拔）
│   │   │   ├── __init__.py    # 控制器注册入口
│   │   │   ├── base.py        # GatewayControllerABC 抽象基类 + GatewayControllerRegistry
│   │   │   ├── szse_mdgw.py   # 深交所行情网关（完整实现）
│   │   │   ├── szse_tgw.py    # 深交所交易网关（完整实现）
│   │   │   ├── sse_mdgw.py    # 上交所行情网关骨架（待实现）
│   │   │   ├── sse_tgw.py     # 上交所交易网关骨架（待实现）
│   │   │   ├── bjse_mdgw.py   # 北交所行情网关骨架（待实现）
│   │   │   └── bjse_tgw.py    # 北交所交易网关骨架（待实现）
│   │   └── core/              # 网关内部核心
│   │       ├── __init__.py
│   │       ├── config_tools.py # 部署模板选择、变量替换、server_list.xml 生成、版本解析
│   │       ├── errors.py      # GatewayError、ConfigError、ProcessError 统一异常
│   │       ├── models.py      # GatewayInstance、DeployParams、UpgradeParams、RollbackParams 等
│   │       ├── process.py     # GatewayProcess：进程生命周期管理（PID 文件、监控端口、启停/重启）
│   │       └── store.py       # InstanceStore：JSON 文件持久化，线程安全
│   ├── grpc/                  # Master 端 gRPC 服务
│   │   ├── __init__.py
│   │   ├── server.py          # gRPC 服务端（端口 50051），Worker 注册/心跳/任务/配置
│   │   ├── worker_pb2.py      # Protocol Buffers 自动生成的消息类
│   │   └── worker_pb2_grpc.py # Protocol Buffers 自动生成的 gRPC 服务/客户端桩
│   ├── data/                  # 本地数据
│   │   └── gateway_instances.json  # 网关实例持久化文件
│   ├── templates/             # 模板文件
│   ├── main.py               # 主入口：FastAPI 应用、日志系统、gRPC 服务启动、网关路由挂载、CORS
│   └── alembic.ini           # 数据库迁移配置
│
├── worker/                    # 分布式工作端
│   ├── core/                  # 核心模块
│   │   ├── __init__.py
│   │   ├── auth.py            # 认证工具（请求签名生成）
│   │   ├── logging.py         # AsyncFileHandler 异步日志处理器
│   │   └── settings.py        # 配置管理（Pydantic Settings）
│   ├── adapter/               # 外部数据适配器（统一可插拔）
│   │   ├── __init__.py
│   │   ├── base.py            # AsyncBaseAdapter 抽象基类 + AdapterManager 单例缓存
│   │   ├── http_adapter.py    # HTTP 适配器（aiohttp）
│   │   ├── kafka_adapter.py   # Kafka 消费者/生产者适配器（confluent-kafka）
│   │   ├── redis_adapter.py   # Redis 适配器（redis-py 异步）
│   │   ├── influxdb_adapter.py # InfluxDB 读写适配器（influxdb-client）
│   │   ├── sql_adapter.py     # 通用 SQL 适配器（SQLAlchemy + asynch）
│   │   └── clickhouse_adapter.py # ClickHouse 适配器
│   ├── scheduler/             # 任务调度模块
│   │   ├── __init__.py
│   │   ├── base_task.py       # BaseTask 基类（THREAD、PROCESS、SCHEDULED 三种执行模式）
│   │   ├── task_scheduler.py  # TaskScheduler：任务工厂、生命周期管理、进程存活监控
│   │   ├── trade_day_cache.py # TradeDayCache：交易日数据缓存，支持 gRPC 回源
│   │   └── tasks/             # 具体任务实现
│   │       ├── __init__.py
│   │       ├── log_collector_task.py    # 日志采集任务
│   │       ├── metric_converter_task.py # 指标转换任务
│   │       ├── database_collector_task.py # DB 采集任务（依赖 TradeDayCache）
│   │       └── kafka_collector_task.py  # Kafka 采集任务（依赖 gRPC 客户端）
│   ├── transformer/           # 数据转换流水线
│   │   ├── __init__.py
│   │   ├── base.py            # TransformScript 抽象基类 + TaskRegistry 单例注册
│   │   ├── executor.py        # TransformExecutor：按 task_id 链式执行转换脚本
│   │   ├── loader.py          # 脚本加载器（动态注册脚本）
│   │   ├── registry.py        # 注册表（任务 ↔ 脚本映射）
│   │   └── scripts/           # 内置转换脚本
│   │       ├── __init__.py
│   │       ├── aggregator.py   # 聚合脚本
│   │       ├── filter.py       # 过滤脚本
│   │       ├── formatter.py    # 格式化脚本
│   │       ├── json_parser.py  # JSON 解析脚本
│   │       └── metric_converter.py # 指标转换脚本
│   ├── grpc/                  # Worker 端 gRPC 客户端
│   │   ├── __init__.py
│   │   ├── client.py          # CentralGrpcClient：注册、心跳、任务下发、配置同步、交易日缓存
│   │   ├── worker_pb2.py      # Protocol Buffers 消息
│   │   └── worker_pb2_grpc.py # Protocol Buffers 客户端桩
│   ├── main.py               # Worker 主入口：sys.path 清理、日志、gRPC 客户端、调度器、交易日缓存
│   └── run.sh                # Worker 启动脚本
│
├── protos/                    # Protocol Buffers 定义
│   └── worker.proto           # Master ↔ Worker gRPC 服务定义（Register/Heartbeat/Task/Config/TradeDay）
│
├── scripts/                   # 辅助脚本
│   ├── deploy.sh             # 一键部署
│   ├── generate_grpc_code.py # 根据 worker.proto 生成 Python gRPC 代码
│   ├── start.sh              # 启动 Master+Worker
│   └── stop.sh               # 停止 Master+Worker
│
├── tests/                     # 测试目录
│   ├── dashboard/
│   │   └── core/
│   │       ├── test_logging.py            # 日志模块测试
│   │       └── test_logging_performance.py # 日志性能测试
│   ├── worker/
│   │   ├── core/test_settings.py          # Worker 配置测试
│   │   └── scheduler/
│   │       ├── test_database_collector_task_trade_day.py # 交易日缓存集成测试
│   │       └── test_trade_day_cache.py    # TradeDayCache 单元测试
│   ├── gateway_smoke.py     # 网关模块冒烟测试
│   ├── test_gateway.py      # 网关控制器与 HTTP API 测试
│   └── test_server.py       # Master 服务测试
│
├── .trae/                     # Trae IDE 配置
│   ├── documents/            # 设计文档
│   │   ├── adapter_module_plan.md
│   │   ├── data_transformation_plan.md
│   │   ├── logging_implementation_plan.md
│   │   ├── logging_optimization_plan.md
│   │   └── 清理worker-collector目录计划.md
│   └── specs/                # 规格说明
│       ├── gateway-control/
│       ├── grpc-migration-feasibility/
│       ├── kafka-adapter/
│       ├── log_collector_split/
│       ├── project-scripts/
│       ├── remove_metrics_directory/
│       └── worker-task-scheduler/
│
├── gateway_python_dev_guide.md # 网关模块 Python 开发指南
├── pyproject.toml            # 项目配置（uv、ruff、依赖）
├── uv.lock                   # 依赖锁定文件
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
  - 数据库配置: database_url_async（支持 SQLite 和 PostgreSQL）
  - 日志配置: log_dir、log_level
  - 安全配置: secret_key
  - amis 配置: amis_cdn、amis_pkg、amis_theme

##### Auth 认证模块
- **文件**: [master/core/auth.py](file:///workspace/master/core/auth.py)
- **职责**: 配置用户认证与权限（fastapi-user-auth + Casbin RBAC）

##### Globals 全局对象
- **文件**: [master/core/globals.py](file:///workspace/master/core/globals.py)
- **职责**: 提供全局 site / auth / 数据库连接实例

##### Logging 日志处理
- **文件**: [master/core/logging.py](file:///workspace/master/core/logging.py)
- **职责**: `AsyncFileHandler` 异步文件日志处理器
  - 使用后台线程批量写入，避免阻塞主循环
  - 优雅关闭，确保日志不落盘丢失
  - 可配置批大小、刷盘间隔、最大队列长度

##### Security 安全验证
- **文件**: [master/core/security.py](file:///workspace/master/core/security.py)
- **职责**: 请求签名验证（HMAC-SHA256 + 时间戳窗口）

#### 1.2 页面管理模块 (master/index/)

- **NavPageAdmin**（页面管理后台）: [master/index/admin.py](file:///workspace/master/index/admin.py)
- **NavPage 数据模型**: [master/index/models.py](file:///workspace/master/index/models.py)
- **AmisPageManager**（数据库 ↔ 站点同步）: [master/index/utils.py](file:///workspace/master/index/utils.py)
- **FileUploadAdmin**（文件上传管理）: [master/index/file_upload_admin.py](file:///workspace/master/index/file_upload_admin.py)

#### 1.3 网关控制模块 (master/gateway/)

**设计目标**: 为多家证券交易所的行情网关（mdgw）与交易网关（tgw）提供统一的部署、启停、升级、回滚与状态管理能力。采用「控制器注册」模式，新增交易所只需在 `controllers/` 下新增一个文件并使用 `@registry.register(exchange, kind)` 装饰器注册，无需修改 `core / api / admin`。

##### 控制器抽象层（controllers/base.py）
- **文件**: [master/gateway/controllers/base.py](file:///workspace/master/gateway/controllers/base.py)
- **GatewayControllerABC**: 定义 `preflight / deploy / start / stop / restart / upgrade / rollback / status` 八个抽象接口
- **GatewayControllerRegistry**: 按 `(exchange, kind)` 键注册控制器类；支持 `make()` 从实例配置直接构造控制器对象
- 内置辅助：`_ensure_executable`、`_merge_zip_contents`、`_current_version_hint`

##### 交易所控制器（controllers/szse_*.py、sse_*.py、bjse_*.py）
- **深交所（完整实现）**: [szse_mdgw.py](file:///workspace/master/gateway/controllers/szse_mdgw.py)、[szse_tgw.py](file:///workspace/master/gateway/controllers/szse_tgw.py)
  - 支持按环境/接入模式/Level/线路选择配置模板
  - 支持 `server_list.xml` 生成（适配 tgw 新版本）
  - 支持部署前预检查（preflight）
  - 支持版本解析（从 zip 文件名/内部 changelog 读取 YYYYMMDD）
- **上交所 / 北交所**: 仅骨架实现，后续按需填充

##### 核心工具（gateway/core/）
- **config_tools.py**: 模板选择、变量替换、`server_list.xml` 生成、版本解析
- **errors.py**: 统一异常模型（GatewayError / ConfigError / ProcessError），包含 code/message/details
- **models.py**: `GatewayInstance`、`DeployParams`、`UpgradeParams`、`RollbackParams`、`GatewayStatus`、`OperationResult`
- **process.py**: `GatewayProcess` 负责二进制进程生命周期：PID 文件、监控端口就绪检测、优雅停止/强制停止、重启
- **store.py**: `InstanceStore` 基于 JSON 文件的线程安全持久化（默认路径 `master/data/gateway_instances.json`）

##### HTTP API（gateway/api/）
- **文件**: [master/gateway/api/__init__.py](file:///workspace/master/gateway/api/__init__.py)
- 统一前缀: `/api/gateway`
- **主要端点**:
  - `GET  /api/gateway/controllers` 已注册控制器清单
  - `GET  /api/gateway/instances` 列出实例
  - `POST /api/gateway/instances` 创建新实例
  - `GET  /api/gateway/instances/{id}` 实例详情
  - `DELETE /api/gateway/instances/{id}` 删除实例
  - `POST /api/gateway/instances/{id}/start` 启动
  - `POST /api/gateway/instances/{id}/stop` 停止
  - `POST /api/gateway/instances/{id}/restart` 重启
  - `GET  /api/gateway/instances/{id}/status` 状态查询
  - `POST /api/gateway/instances/{id}/deploy` 上传 zip 部署包部署
  - `POST /api/gateway/instances/{id}/upgrade` 上传 zip 升级
  - `POST /api/gateway/instances/{id}/rollback` 根据 manifest.json 回滚

##### amis-admin 管理界面（gateway/admin/）
- **文件**: [master/gateway/admin/__init__.py](file:///workspace/master/gateway/admin/__init__.py)
- **GatewayInstanceAdmin**: 实例管理页面（创建表单 + 实例表格 + 单实例启停/删除）
- **GatewayOpsAdmin**: 网关运维面板（选择实例后启停/重启/状态/部署/升级/回滚；已注册控制器展示）
- **GatewayAdminApp**: 在 `master/main.py` 中通过 `site.register_admin(GatewayAdminApp)` 注册到主菜单

#### 1.4 gRPC 服务端（master/grpc/）
- **文件**: [master/grpc/server.py](file:///workspace/master/grpc/server.py)
- **端口**: 50051（默认）
- **作用**: 为分布式 Worker 提供注册、心跳、任务下发、配置同步、交易日数据等 gRPC 接口
- Master 启动时在 `lifespan` 中以守护线程启动 gRPC 服务，失败时降级为纯 HTTP 模式

#### 1.5 主入口 (master/main.py)
- **文件**: [master/main.py](file:///workspace/master/main.py)
- **职责**:
  - 创建 FastAPI 应用
  - 配置 `AsyncFileHandler` 日志系统
  - 启动 gRPC 服务端（守护线程，端口 50051）
  - 挂载静态文件、注册 NavPageAdmin / GatewayAdminApp / FileUploadApp
  - 挂载网关 HTTP API 路由（`/api/gateway/*`）
  - 配置 CORS 中间件
  - 提供 `POST /api/file-upload/submit` 文件上传接口

---

### 2. Worker 模块（分布式工作端）

#### 2.1 核心模块 (worker/core/)
- **settings.py**: Worker 配置（host、port、worker_id、日志、任务、中心端地址等）
- **auth.py**: 请求签名生成工具
- **logging.py**: 与 Master 相同的 `AsyncFileHandler`

#### 2.2 适配器模块 (worker/adapter/)
统一抽象：`AsyncBaseAdapter`（`async close()`、`transform()`、`transform_chain()`），所有适配器均为异步实现。
- **base.py**: 抽象基类 + `AdapterManager`（按配置哈希缓存实例，`atexit` 自动清理）
- **http_adapter.py**: aiohttp HTTP 客户端
- **kafka_adapter.py**: confluent-kafka 消费者/生产者
- **redis_adapter.py**: redis-py 异步客户端
- **influxdb_adapter.py**: InfluxDB 2.x 读写
- **sql_adapter.py**: 通用 SQL 适配器（SQLAlchemy async）
- **clickhouse_adapter.py**: ClickHouse 适配器

#### 2.3 任务调度模块 (worker/scheduler/)
- **base_task.py**: `BaseTask`，支持 THREAD / PROCESS / SCHEDULED 三种执行模式
- **task_scheduler.py**: `TaskScheduler`，任务工厂、生命周期管理、进程存活监控、任务状态上报
- **trade_day_cache.py**: `TradeDayCache`，交易日数据缓存，通过 gRPC 客户端回源 Master
- **tasks/log_collector_task.py**: 日志采集
- **tasks/metric_converter_task.py**: 指标转换
- **tasks/database_collector_task.py**: DB 采集（依赖 TradeDayCache）
- **tasks/kafka_collector_task.py**: Kafka 采集（依赖 gRPC 客户端上报）

#### 2.4 数据转换流水线 (worker/transformer/)
- **base.py**: `TransformScript` 抽象基类 + `TaskRegistry`（单例，任务 ↔ 脚本映射）
- **executor.py**: `TransformExecutor`，按 task_id 解析脚本，支持链式执行
- **loader.py**: 脚本加载器，便于动态注册
- **registry.py**: 任务与脚本映射注册表
- **scripts/**: 内置转换脚本（聚合、过滤、格式化、JSON 解析、指标转换）

#### 2.5 gRPC 客户端 (worker/grpc/)
- **client.py**: `CentralGrpcClient`，Worker 与 Master 通信的主通道
  - `register()`: 注册 Worker
  - `heartbeat()`: 心跳保活
  - `get_config()`: 获取/同步配置
  - `get_task()`: 获取任务指令
  - `get_trade_day()`: 交易日数据（驱动 `TradeDayCache`）
  - `set_trade_day_cache()`: 将缓存注入 gRPC 客户端，形成闭环
  - `register_task_scheduler()`: 与 `TaskScheduler` 联动，实现任务下发/上报
- **worker_pb2.py / worker_pb2_grpc.py**: 由 `scripts/generate_grpc_code.py` 基于 `protos/worker.proto` 自动生成

#### 2.6 主入口 (worker/main.py)
- **文件**: [worker/main.py](file:///workspace/worker/main.py)
- **关键特性**:
  - **sys.path 清理**: 自动从 `sys.path` 中移除 `worker/` 目录，避免本地的 `worker/grpc/` 与第三方 `grpcio` 发生包名冲突
  - 自动发现项目根目录（向上寻找 `pyproject.toml`）
  - 初始化日志系统、gRPC 客户端、调度器、交易日缓存
  - 注册 4 种任务类型：log_collector / metric_converter / database_collector / kafka_collector
  - 主循环 + 优雅关闭

---

## 关键类与函数说明

### 1. AsyncFileHandler（异步日志处理器）

**位置**: [master/core/logging.py](file:///workspace/master/core/logging.py#L9-L147)、[worker/core/logging.py](file:///workspace/worker/core/logging.py)

**功能**: 提供高性能的异步日志处理，避免 I/O 阻塞主线程。

**关键特性**:
- 队列缓冲（默认 10000 条）
- 批量处理（默认 500 条/批）
- 优雅关闭机制
- 性能监控

**关键方法**:
```python
def __init__(self, file_handler, max_queue_size, drop_threshold, batch_size, flush_interval)
def write()          # 后台写线程，批量处理日志
def close()          # 优雅关闭，确保日志不丢失
```

---

### 2. GatewayControllerABC + GatewayControllerRegistry（网关控制器抽象与注册中心）

**位置**: [master/gateway/controllers/base.py](file:///workspace/master/gateway/controllers/base.py)

**关键特性**:
- 统一 8 个操作接口：preflight / deploy / start / stop / restart / upgrade / rollback / status
- `@registry.register(exchange, kind)` 装饰器：新增交易所控制器无需修改核心代码
- `registry.list_all()`: 列出所有已注册控制器（供 HTTP API / Admin 页面使用）
- `registry.make(instance, install_root, backup_root)`: 根据实例配置构造控制器

**扩展方式**:
```python
from master.gateway.controllers.base import GatewayControllerABC, registry

@registry.register("foo_exchange", "mdgw")
class FooMdgwController(GatewayControllerABC):
    # 实现八个抽象方法
```

---

### 3. GatewayProcess（网关二进制进程管理器）

**位置**: [master/gateway/core/process.py](file:///workspace/master/gateway/core/process.py)

**关键特性**:
- PID 文件持久化，支持进程退出后重新 attach
- 启动后自动等待监控端口就绪（`socket.create_connection` 轮询）
- 优雅停止（SIGTERM）/ 强制停止（SIGKILL），psutil 可用时优先使用
- 可自定义启动/停止超时

**关键方法**:
```python
def start()          # 启动进程，等待监控端口就绪
def stop(force=False)
def restart()
def is_running() -> bool
def get_pid() -> int | None
def wait_for_monitor(max_wait)
```

---

### 4. InstanceStore（网关实例 JSON 持久化）

**位置**: [master/gateway/core/store.py](file:///workspace/master/gateway/core/store.py)

**关键方法**:
```python
def upsert(instance: GatewayInstance)
def get(instance_id: str) -> GatewayInstance | None
def list() -> list[GatewayInstance]
def delete(instance_id: str) -> bool
```

---

### 5. TaskScheduler（Worker 任务调度器）

**位置**: [worker/scheduler/task_scheduler.py](file:///workspace/worker/scheduler/task_scheduler.py)

**关键特性**:
- 任务工厂：按类型字符串（`log_collector` 等）创建任务
- 支持 THREAD / PROCESS / SCHEDULED 三种执行模式
- 进程存活监控线程（5 秒周期，检测 PROCESS 模式任务异常退出并上报 FAILED）
- 任务状态通过 gRPC 客户端上报 Master

**关键方法**:
```python
def register_task_type(task_type, task_cls)   # 注册任务类型到工厂
def create_task(task_type, config) -> task_id
def stop_task(task_id)
def pause_task(task_id) / resume_task(task_id)
def get_task(task_id) / list_tasks()
def shutdown()                                 # 优雅关闭所有任务
```

---

### 6. TradeDayCache（交易日缓存）

**位置**: [worker/scheduler/trade_day_cache.py](file:///workspace/worker/scheduler/trade_day_cache.py)

**功能**: 缓存交易日历数据，供 `DatabaseCollectorTask` 等业务任务使用，通过 gRPC 客户端回源 Master。

---

### 7. AsyncBaseAdapter + AdapterManager（统一适配器抽象）

**位置**: [worker/adapter/base.py](file:///workspace/master/../../worker/adapter/base.py)

**功能**: 为 HTTP / Kafka / Redis / InfluxDB / SQL / ClickHouse 等外部数据源提供统一的异步访问层，并通过 AdapterManager 按配置哈希复用实例，避免频繁重建连接。

---

## 依赖关系

### 核心依赖关系图

```
┌─────────────────────────────────────────────────────────┐
│                    Master 依赖                              │
├─────────────────────────────────────────────────────────┤
│                                                             │
│  FastAPI ──► fastapi-amis-admin ──► fastapi-user-auth    │
│     │                │                       │              │
│     │                ▼                       ▼              │
│     │          SQLModel ◄─────── AsyncDatabase             │
│     │                │                                      │
│     ▼                ▼                                      │
│  Starlette ──► SQLAlchemy ──► aiosqlite / asynch            │
│                                                             │
│  uvicorn ──► greenlet ──► grpcio (gRPC 服务端)              │
│                                                             │
│  pydantic-settings                                          │
│  croniter                                                   │
│                                                             │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                    Worker 依赖                              │
├─────────────────────────────────────────────────────────┤
│                                                             │
│  grpcio (gRPC 客户端) ◄── protos/worker.proto             │
│                                                             │
│  aiohttp / confluent-kafka / redis / influxdb-client       │
│  ──► worker/adapter/* 适配器家族                            │
│                                                             │
│  croniter ──► TaskScheduler（定时任务）                    │
│                                                             │
│  pydantic-settings                                          │
│                                                             │
└─────────────────────────────────────────────────────────┘
```

### 依赖列表

#### 生产依赖
| 依赖包 | 版本 | 用途 |
|--------|------|------|
| fastapi | 0.111.0 | Web 框架 |
| fastapi-amis-admin | ≥0.7.3 | 管理后台框架 |
| fastapi-user-auth | ≥0.7.3 | 用户认证 |
| sqlmodel | 0.0.19 | ORM 框架 |
| sqlmodelx | 0.0.12 | SQLModel 扩展 |
| aiosqlite | ≥0.22.1 | 异步 SQLite |
| asynch | ≥0.2.0 | 异步数据库支持（ClickHouse/MySQL/PG） |
| greenlet | ≥3.3.2 | 协程支持 |
| pydantic-settings | ≥2.13.1 | 配置管理 |
| grpcio | ≥1.60.0 | gRPC 运行时 |
| grpcio-tools | ≥1.60.0 | gRPC 代码生成 |
| protobuf | ≥4.25.0 | Protocol Buffers |
| requests | ≥2.33.1 | HTTP 客户端 |
| aiohttp | ≥3.9.0 | 异步 HTTP |
| websockets | ≥12.0 | WebSocket 实时通信 |
| confluent-kafka | ≥2.3.0 | Kafka 消费者/生产者 |
| redis | ≥5.0.0 | Redis 客户端 |
| influxdb-client | ≥1.40.0 | InfluxDB 客户端 |
| croniter | ≥2.0.0 | Cron 表达式解析 |
| sqlalchemy | ≥2.0.0 | SQL 抽象层 |

#### 开发依赖
| 依赖包 | 版本 | 用途 |
|--------|------|------|
| pytest | ≥9.0.2 | 测试框架 |
| ruff | ≥0.15.5 | 代码检查和格式化 |

---

## 项目运行方式

### 1. 环境准备

#### 安装 uv 包管理器
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### 安装依赖
```bash
cd /workspace
uv sync
```

### 2. 启动 Master（中心管理端）

#### 方式一：直接运行
```bash
cd /workspace/master
python main.py
```

#### 方式二：使用脚本
```bash
cd /workspace
./scripts/start.sh
```

#### 访问地址
- 管理后台: http://localhost:5500/admin
- API 文档: http://localhost:5500/docs
- 网关控制菜单: 「网关控制」（GatewayAdminApp）
- 默认管理员: admin / admin
- 默认超级管理员: root / root
- gRPC 端口: 50051

### 3. 启动 Worker（分布式工作端）

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

### 4. 启动 Master + Worker（推荐）

```bash
cd /workspace
./scripts/start.sh
```

停止：
```bash
cd /workspace
./scripts/stop.sh
```

### 5. 重新生成 gRPC 代码

```bash
cd /workspace
python scripts/generate_grpc_code.py
```

脚本会读取 `protos/worker.proto`，并分别输出到：
- `master/grpc/worker_pb2.py`、`master/grpc/worker_pb2_grpc.py`
- `worker/grpc/worker_pb2.py`、`worker/grpc/worker_pb2_grpc.py`

### 6. 运行测试

```bash
cd /workspace
python -m pytest tests/
```

### 7. 代码检查和格式化

```bash
cd /workspace
# 代码检查
ruff check .

# 代码格式化
ruff format .
```

---

## 配置说明

### Master 配置

**配置文件**: [master/core/settings.py](file:///workspace/master/core/settings.py)

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| host | "0.0.0.0" | 监听地址 |
| port | 5500 | HTTP 监听端口 |
| grpc_port | 50051 | gRPC 监听端口 |
| debug | True | 调试模式 |
| version | "0.1.0" | 版本号 |
| site_title | "SRE Tools" | 站点标题 |
| site_path | "/admin" | 管理路径 |
| database_url_async | SQLite | 异步数据库 URL |
| log_level | "DEBUG" | 日志级别 |
| log_dir | master/log/uvicorn.log | 日志文件路径 |
| secret_key | "your-secret-key-here" | 密钥 |
| gateway_store_path | master/data/gateway_instances.json | 网关实例 JSON 持久化路径 |
| gateway_install_root | master/data/gateways | 网关二进制安装根目录 |
| gateway_backup_root | master/data/gateways/backup | 网关版本备份根目录 |

### Worker 配置

**配置文件**: [worker/core/settings.py](file:///workspace/worker/core/settings.py)

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| host | "0.0.0.0" | 监听地址 |
| port | 5501 | 监听端口 |
| worker_id | "worker_{pid}" | Worker 标识 |
| central_servers | ["http://localhost:50051"] | Master gRPC 地址 |
| central_timeout | 10 | 中心端超时（秒） |
| central_retry_times | 3 | 重试次数 |
| log_collect_interval | 5 | 日志采集间隔（秒） |
| log_batch_size | 1000 | 日志批量大小 |
| metric_collect_interval | 10 | 指标采集间隔（秒） |
| local_storage_path | worker/data | 本地存储路径 |
| max_local_storage_size | 1024 | 最大存储（MB） |
| secret_key | "your-secret-key-here" | 密钥 |

---

## 数据模型

### NavPage（导航页面）

**位置**: [master/index/models.py](file:///workspace/master/index/models.py#L36-L167)

**字段说明**（略）：id、type、url、label、icon、sort、desc、page_schema、parent_id、unique_id、tabsMode、visible、is_group、is_custom、is_active、is_locked、update_time。

### GatewayInstance（网关实例）

**位置**: [master/gateway/core/models.py](file:///workspace/master/gateway/core/models.py)

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| id | str | 实例唯一 ID |
| exchange | str | 交易所编码（如 szse、sse、bjse） |
| kind | str | 网关类型（mdgw 行情、tgw 交易） |
| name | str | 显示名称 |
| gateway_dir | str | 网关根目录 |
| binary_name | str | 可执行文件名 |
| monitor_port | int | 监控端口（用于等待就绪） |
| version | str \| None | 当前版本（YYYYMMDD） |
| config | dict | 附加配置（环境 / 接入模式 / Level / 线路 等） |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

### 其它模型

- `DeployParams`、`UpgradeParams`、`RollbackParams`: 部署/升级/回滚参数对象
- `OperationResult`: 操作结果（success / message / details / manifest_path）
- `GatewayStatus`: 运行状态（running、pid、monitor_port、gateway_dir、version、memory_mb、uptime_seconds）

---

## API 接口说明

### Master HTTP API

#### Worker 管理 / 通用

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/file-upload/submit | 文件上传提交 |
| GET | /docs / /openapi.json | Swagger / OpenAPI |

#### 网关控制接口（/api/gateway/*）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/gateway/controllers | 已注册控制器清单 |
| GET | /api/gateway/instances | 实例列表 |
| POST | /api/gateway/instances | 新增实例 |
| GET | /api/gateway/instances/{id} | 实例详情 |
| DELETE | /api/gateway/instances/{id} | 删除实例 |
| POST | /api/gateway/instances/{id}/start | 启动实例 |
| POST | /api/gateway/instances/{id}/stop | 停止实例 |
| POST | /api/gateway/instances/{id}/restart | 重启实例 |
| GET | /api/gateway/instances/{id}/status | 查询状态 |
| POST | /api/gateway/instances/{id}/deploy | 上传 zip 部署 |
| POST | /api/gateway/instances/{id}/upgrade | 上传 zip 升级 |
| POST | /api/gateway/instances/{id}/rollback | 根据 manifest 回滚 |

### Master gRPC API（/protos/worker.proto）

| RPC | 说明 |
|-----|------|
| RegisterWorker | Worker 注册到 Master |
| SendHeartbeat | Worker 心跳保活 |
| GetConfig | Worker 拉取配置 |
| GetTask | Worker 拉取任务指令 |
| SubmitTaskResult | Worker 上报任务结果 |
| GetTradeDay | Worker 拉取交易日数据 |
| GetInstances | （管理）获取网关实例列表 |

### Worker 接口

Worker 不对外提供 HTTP 服务；Worker 通过 gRPC 客户端主动与 Master 通信，并通过 `worker/adapter/*` 家族访问外部数据源。

---

## 安全机制

### 1. 请求签名验证

**实现位置**:
- Master: [master/core/security.py](file:///workspace/master/core/security.py)
- Worker: [worker/core/auth.py](file:///workspace/worker/core/auth.py)

**签名算法**: HMAC-SHA256

**验证流程**:
1. 客户端生成签名（包含时间戳）
2. 服务端验证时间戳（5 分钟内有效）
3. 服务端验证签名

### 2. 用户认证

**实现**: fastapi-user-auth

**认证方式**:
- Token 认证
- 数据库 Token 存储
- Token 有效期: 360 天

### 3. 权限管理

**实现**: Casbin（RBAC）

**权限策略**:
- 基于角色的权限控制（admin / root）
- 支持页面级别权限

---

## 性能优化

### 1. 异步日志处理

`AsyncFileHandler`: 队列缓冲 + 批量写入 + 后台线程，避免阻塞主线程。

### 2. 批量数据处理

- 日志采集：批量存储（默认 1000 条/批）
- 指标转换：批量处理（默认 500 条/批）
- gRPC 消息：批量上报

### 3. 连接池管理

- 数据库连接池（SQLAlchemy async）
- HTTP 连接池（aiohttp / requests.Session）
- gRPC 通道复用
- Redis / Kafka / InfluxDB 连接由 `AdapterManager` 按配置哈希复用

### 4. 网关进程监控端口就绪检测

启动网关后，使用 `socket.create_connection` 轮询监控端口，就绪才视为启动成功，避免误判。

---

## 故障处理

### 1. Master 故障

- Worker 通过 gRPC keepalive + 重试检测 Master 不可用
- Worker 缓存配置/数据至本地 JSON，恢复后自动重连并补齐上报

### 2. Worker 进程异常

- `TaskScheduler._check_process_health`: 周期检查 PROCESS 模式任务存活
- 异常进程自动标记 FAILED，并通过 gRPC 上报 Master
- Worker 主入口 `KeyboardInterrupt` / `Exception` 走统一 `shutdown()` 路径

### 3. 网关二进制故障

- `GatewayProcess`: 优雅停止失败 → SIGKILL 兜底
- 启动等待监控端口超时 → 标记失败并清理 PID 文件
- Controller `deploy/upgrade/rollback` 统一返回 `OperationResult(success=False, ...)`，由 HTTP API 转成 400/500 响应

### 4. 网络故障

- gRPC 自带重试/断线重连
- 指数退避重连策略
- 本地数据缓存，恢复后回补

### 5. 存储不足

- 自动清理旧文件
- 按修改时间排序清理

---

## 监控指标

### Worker 监控指标

| 指标名 | 说明 |
|--------|------|
| log_count | 日志计数（按级别和来源分组） |
| processing_time | 处理时间 |
| queue_size | 队列大小 |
| processing_speed | 处理速度 |

### 网关监控指标（内置）

- 运行状态 / PID / 监控端口
- 内存占用（MB）
- 启动时长（uptime_seconds）
- 版本号

---

## 开发指南

### 1. 添加新的页面类型

1. 在 `NavPageType` 中添加新类型
2. 更新 `parse_page_schema_type()` 函数
3. 在 `NavPageAdmin` 中添加相应的处理逻辑

### 2. 添加新的交易所网关控制器

1. 在 `master/gateway/controllers/` 下新建文件，例如 `foo_mdgw.py`
2. 继承 `GatewayControllerABC` 并使用 `@registry.register("foo", "mdgw")` 装饰
3. 实现 `preflight / deploy / start / stop / restart / upgrade / rollback / status` 八个方法
4. 在 `master/gateway/controllers/__init__.py` 中 import 新控制器以触发注册
5. 无需修改 `core/`、`api/`、`admin/` 即可被 HTTP API 和 amis-admin 页面自动识别

### 3. 添加新的 Worker 任务类型

1. 在 `worker/scheduler/tasks/` 下新建模块，继承 `BaseTask`，实现 `run()`
2. 在 `worker/main.py` 中通过 `scheduler.register_task_type("new_task", NewTask)` 注册

### 4. 添加新的外部数据源适配器

1. 在 `worker/adapter/` 下新建模块，继承 `AsyncBaseAdapter`
2. 实现 `async close()`，并可选地在 `transform()` / `transform_chain()` 中加入业务逻辑
3. 通过 `AdapterManager.get_or_create()` 在任务中使用

### 5. 修改 Protocol Buffers 协议

1. 编辑 `protos/worker.proto`
2. 运行 `python scripts/generate_grpc_code.py` 重新生成两端代码
3. 在 `master/grpc/server.py` 中实现新 RPC；在 `worker/grpc/client.py` 中封装调用

---

## 测试说明

### 测试目录结构

```
tests/
├── dashboard/
│   └── core/
│       ├── test_logging.py            # 日志模块测试
│       └── test_logging_performance.py # 日志性能测试
├── worker/
│   ├── core/test_settings.py          # Worker 配置测试
│   └── scheduler/
│       ├── test_database_collector_task_trade_day.py # 交易日缓存集成
│       └── test_trade_day_cache.py    # TradeDayCache 单元测试
├── gateway_smoke.py     # 网关模块冒烟测试
├── test_gateway.py      # 网关控制器与 HTTP API 测试
└── test_server.py       # Master 服务测试
```

### 运行测试

```bash
# 运行所有测试
python -m pytest tests/

# 运行特定测试
python -m pytest tests/test_gateway.py

# 运行测试并显示覆盖率
python -m pytest tests/ --cov=master --cov=worker
```

---

## 部署建议

### 1. Master 部署

- 使用 uvicorn + systemd 部署（`scripts/start.sh` 可直接扩展）
- 配置反向代理（Nginx）
- 使用 PostgreSQL 作为生产数据库
- 配置 HTTPS
- 配置日志轮转

### 2. Worker 部署

- 使用 Systemd / Supervisor 管理进程
- 配置日志轮转
- 监控本地存储使用情况
- 配置多个 Master gRPC 地址（高可用）

### 3. 网关控制部署

- 将 `master/gateway/` 随 Master 一并部署
- `gateway_install_root` / `gateway_backup_root` 使用独立磁盘卷，避免污染 Master 代码
- 网关二进制需要系统可执行权限（部署时自动赋予）
- 可选地将网关控制暴露给独立运维面板（`/api/gateway/*`）

### 4. 高可用部署

- 部署多个 Master 实例（负载均衡）
- 部署多个 Worker 实例（分布式）
- 配置数据库主从复制
- 配置监控告警

---

## 常见问题

### Q1: Worker 无法连接到 Master？

**解决方案**:
1. 检查 Master 是否启动（`netstat -lnp | grep 50051` 验证 gRPC 端口）
2. 检查网络连通性（`telnet <master-host> 50051`）
3. 检查防火墙配置
4. 检查 `worker/core/settings.py` 中 `central_servers` 配置

### Q2: 日志丢失？

**解决方案**:
1. 检查队列大小配置
2. 检查磁盘空间
3. 使用 `AsyncFileHandler` 确保异步写入
4. 优雅关闭 Master/Worker（Ctrl+C 触发 `shutdown`）

### Q3: 性能问题？

**解决方案**:
1. 调整批量大小配置
2. 调整队列大小配置
3. 使用异步处理
4. 优化数据库查询

### Q4: 新增交易所网关控制器后 API 不识别？

**解决方案**:
1. 确保在 `master/gateway/controllers/__init__.py` 中 `import` 新控制器（触发装饰器注册）
2. 重启 Master，或访问 `GET /api/gateway/controllers` 确认是否列出

### Q5: 网关进程 `start()` 超时？

**解决方案**:
1. 确认 `monitor_port` 与网关二进制实际监听端口匹配
2. 确认网关二进制可执行且 config 完整
3. 通过 `GET /api/gateway/instances/{id}/status` 观察状态
4. 可在 `GatewayProcess` 中调整 `start_timeout`

### Q6: Worker 运行时报 `no module named grpc`？

**解决方案**:
`worker/main.py` 已实现 sys.path 清理逻辑，避免本地 `worker/grpc/` 被 Python 当作第三方 `grpcio`。请使用 `python worker/main.py` 或 `./worker/run.sh`，而不是在 `worker/` 目录内直接 `python main.py`（虽然也已做兼容，但推荐从项目根启动）。

---

## 版本历史

- **v0.1.0**: 初始版本
  - 基础管理后台（NavPageAdmin、FileUploadApp）
  - Worker 基础功能：日志采集、指标转换、异步日志
  - gRPC Master ↔ Worker 通信
  - HTTP/WebSocket 通信与签名验证

- **v0.2.0**: 新增交易所网关统一管理模块
  - 网关控制器抽象层（GatewayControllerABC + GatewayControllerRegistry）
  - 深交所 mdgw / tgw 完整实现
  - 上交所 / 北交所 mdgw / tgw 骨架实现
  - 网关 HTTP API（/api/gateway/*，完整 CRUD + 部署/升级/回滚/启停）
  - amis-admin 管理界面（GatewayInstanceAdmin、GatewayOpsAdmin、GatewayAdminApp）
  - 核心工具：GatewayProcess、InstanceStore、ConfigTools、Errors、Models
  - scripts/start.sh、scripts/stop.sh、scripts/deploy.sh、scripts/generate_grpc_code.py
  - Worker 重构：adapter/（HTTP/Kafka/Redis/InfluxDB/SQL/ClickHouse）
  - Worker 重构：scheduler/（TaskScheduler、BaseTask、TradeDayCache、4 种任务类型）
  - Worker 重构：transformer/（TaskRegistry、TransformExecutor、内置脚本）
  - Worker 重构：grpc/（CentralGrpcClient + 自动生成的 protobuf 代码）
  - 完整测试套件（tests/ 目录，覆盖日志、网关、调度、交易日缓存）
  - 新增 protos/worker.proto 定义 Master ↔ Worker gRPC 协议
  - 新依赖: grpcio、grpcio-tools、protobuf、aiohttp、confluent-kafka、redis、influxdb-client、croniter、asynch、sqlalchemy

---

## 贡献指南

1. Fork 项目
2. 创建功能分支
3. 提交代码
4. 创建 Pull Request

---

## 许可证

本项目采用 MIT 许可证。

---

## 联系方式

如有问题或建议，请提交 Issue 或 Pull Request。

---

## 更新于 2026-06-12

- 新增网关控制模块（`master/gateway/*`）：支持深交所 mdgw / tgw 完整部署/启停/升级/回滚，以及上交所/北交所骨架
- 新增网关 HTTP API 路由（`/api/gateway/*`），提供实例 CRUD 与运维操作
- 新增网关 amis-admin 管理界面（GatewayInstanceAdmin、GatewayOpsAdmin、GatewayAdminApp）
- 新增 Master gRPC 服务端（`master/grpc/server.py`，端口 50051）
- 新增 Worker gRPC 客户端（`worker/grpc/client.py`）
- 新增 Protocol Buffers 定义（`protos/worker.proto`）与代码生成脚本（`scripts/generate_grpc_code.py`）
- Worker 新增 adapter 模块：HTTP / Kafka / Redis / InfluxDB / SQL / ClickHouse 统一异步适配器
- Worker 新增 scheduler 模块：TaskScheduler、BaseTask、TradeDayCache，4 种任务类型
- Worker 新增 transformer 模块：TaskRegistry、TransformExecutor、内置转换脚本
- 新增辅助脚本：`scripts/deploy.sh`、`scripts/start.sh`、`scripts/stop.sh`
- 新增完整测试套件（`tests/gateway_smoke.py`、`tests/test_gateway.py`、`tests/test_server.py`、Worker scheduler/交易日缓存测试）
- 更新依赖：增加 grpcio、grpcio-tools、protobuf、aiohttp、confluent-kafka、redis、influxdb-client、croniter、asynch、sqlalchemy
- 更新 README.md，同步项目架构、API、配置项、开发指南、版本历史
