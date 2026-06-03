# SRE Tools - Code Wiki

## 项目概述

**SRE Tools** 是一个基于 FastAPI 的站点可靠性工程（SRE）工具平台，采用主从架构设计，包含中心管理端（master）和分布式工作端（worker）两大核心模块。该平台提供了日志收集、指标转换、分布式监控、后台管理等功能。

### 技术栈

- **语言**: Python 3.12+
- **Web框架**: FastAPI 0.111.0
- **管理后台**: fastapi-amis-admin 0.7.3
- **用户认证**: fastapi-user-auth 0.7.3
- **数据库**: SQLModel 0.0.19 + SQLite/PostgreSQL
- **异步支持**: aiosqlite、greenlet
- **通信协议**: HTTP、WebSocket
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
│  ┌──────────────────────┐      ┌──────────────────────┐    │
│  │   Master (中心端)     │◄────►│   Worker (工作端)     │    │
│  │                      │      │                      │    │
│  │  - FastAPI服务        │      │  - 日志收集器         │    │
│  │  - 管理后台           │      │  - 指标转换器         │    │
│  │  - 用户认证           │      │  - 中心端客户端       │    │
│  │  - 页面管理           │      │  - 本地存储           │    │
│  │  - Worker路由         │      │  - WebSocket连接      │    │
│  └──────────────────────┘      └──────────────────────┘    │
│           │                              │                  │
│           ▼                              ▼                  │
│  ┌──────────────────────┐      ┌──────────────────────┐    │
│  │   数据库 (SQLite/PG)  │      │   本地存储 (JSON)     │    │
│  └──────────────────────┘      └──────────────────────┘    │
│                                                               │
└─────────────────────────────────────────────────────────────┘
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
│   ├── index/                 # 页面管理模块
│   │   ├── __init__.py
│   │   ├── admin.py          # 页面管理后台
│   │   ├── file_upload_admin.py  # 文件上传管理
│   │   ├── models.py         # 数据模型
│   │   └── utils.py          # 工具函数
│   ├── static/                # 静态资源
│   │   ├── amis/             # Amis SDK
│   │   ├── swagger/          # Swagger UI
│   │   └── ...
│   ├── templates/             # 模板文件
│   ├── worker/                # Worker路由模块
│   │   ├── __init__.py
│   │   └── routes.py         # Worker API路由
│   ├── main.py               # 主入口文件
│   ├── alembic.ini           # 数据库迁移配置
│   └── amisadmin.db          # SQLite数据库
│
├── worker/                    # 分布式工作端
│   ├── core/                  # 核心模块
│   │   ├── __init__.py
│   │   ├── auth.py           # 认证工具
│   │   ├── logging.py        # 日志处理
│   │   └── settings.py       # 配置管理
│   ├── collector/             # 日志收集模块
│   │   ├── __init__.py
│   │   └── log_collector.py  # 日志收集器
│   ├── communicator/          # 通信模块
│   │   ├── __init__.py
│   │   └── central_client.py # 中心端客户端
│   ├── metrics/               # 指标模块
│   │   ├── __init__.py
│   │   └── metric_converter.py  # 指标转换器
│   ├── main.py               # 主入口文件
│   └── run.sh                # 启动脚本
│
├── tests/                     # 测试目录
│   ├── dashboard/
│   ├── worker/
│   └── test_server.py
│
├── .trae/                     # Trae配置
│   ├── documents/            # 文档
│   └── skills/               # 技能配置
│
├── pyproject.toml            # 项目配置
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

#### 1.3 Worker路由模块 (master/worker/)

##### Worker Routes
- **文件**: [master/worker/routes.py](file:///workspace/master/worker/routes.py)
- **职责**: 提供Worker管理的API接口
- **主要端点**:
  - `POST /api/worker/register`: Worker注册
  - `POST /api/worker/heartbeat`: 接收心跳
  - `GET /api/worker/config`: 获取配置
  - `POST /api/worker/logs`: 接收日志
  - `POST /api/worker/metrics`: 接收指标
  - `GET /api/worker/list`: 获取Worker列表
  - `GET /api/worker/health`: 健康检查
  - `WebSocket /api/worker/ws/{worker_id}`: WebSocket连接
  - `POST /api/worker/update-config`: 更新配置
  - `POST /api/worker/update-task`: 更新任务

##### ConnectionManager WebSocket连接管理
- **职责**: 管理Worker的WebSocket连接
- **关键方法**:
  - `connect()`: 建立连接
  - `disconnect()`: 断开连接
  - `send_personal_message()`: 发送个人消息
  - `broadcast()`: 广播消息

#### 1.4 主入口 (master/main.py)

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
  - 中心端配置: central_servers（支持多个中心端）、central_timeout、central_retry_times
  - 日志配置: log_level、log_dir、error_log_dir
  - 日志收集配置: log_collect_interval、log_batch_size、log_queue_size
  - 指标配置: metric_collect_interval、metric_batch_size
  - 存储配置: local_storage_path、max_local_storage_size
  - 安全配置: api_key、secret_key

##### Auth 认证工具
- **文件**: [worker/core/auth.py](file:///workspace/worker/core/auth.py)
- **职责**: 提供请求签名生成功能
- **关键函数**: `generate_signature()` - 生成HMAC-SHA256签名

#### 2.2 日志收集模块 (worker/collector/)

##### LogCollector 日志收集器
- **文件**: [worker/collector/log_collector.py](file:///workspace/worker/collector/log_collector.py)
- **职责**: 收集和存储本地日志
- **关键特性**:
  - 使用队列缓冲日志
  - 支持批量存储
  - 按日期分文件存储
  - 自动清理旧文件（基于存储大小限制）
  - 多线程处理

#### 2.3 通信模块 (worker/communicator/)

##### CentralClient 中心端客户端
- **文件**: [worker/communicator/central_client.py](file:///workspace/worker/communicator/central_client.py)
- **职责**: 与中心端通信，支持故障切换
- **关键特性**:
  - 支持多个中心端服务器
  - 自动健康检查
  - 自动故障切换
  - WebSocket实时通信
  - 指数退避重连策略
  - 心跳保活
  - 本地配置缓存

##### 关键方法:
  - `register()`: 注册Worker到中心端
  - `send_heartbeat()`: 发送心跳
  - `send_logs()`: 发送日志到中心端
  - `send_metrics()`: 发送指标到中心端
  - `get_config()`: 获取配置（支持本地缓存）
  - `_switch_server()`: 切换中心端服务器
  - `_start_websocket()`: 启动WebSocket连接
  - `register_message_handler()`: 注册消息处理器

#### 2.4 指标模块 (worker/metrics/)

##### MetricConverter 指标转换器
- **文件**: [worker/metrics/metric_converter.py](file:///workspace/worker/metrics/metric_converter.py)
- **职责**: 将日志转换为监控指标
- **关键特性**:
  - 支持日志到指标的转换
  - 支持指标聚合
  - 按指标名称和标签分组存储
  - 多线程处理

#### 2.5 主入口 (worker/main.py)

- **文件**: [worker/main.py](file:///workspace/worker/main.py)
- **职责**: Worker的主入口
- **关键类**: `Worker`
  - 初始化中心端客户端
  - 初始化日志收集器
  - 初始化指标转换器
  - 运行主循环

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

### 2. LogCollector（日志收集器）

**位置**: [worker/collector/log_collector.py](file:///workspace/worker/collector/log_collector.py#L12-L133)

**功能**: 收集和存储本地日志

**关键特性**:
- 队列缓冲
- 批量存储
- 按日期分文件
- 自动清理旧文件

**关键方法**:

```python
def collect_logs(self)  # 收集日志的主循环
```

```python
def store_logs(self)  # 存储日志到本地
```

```python
def save_to_local(self, logs: List[Dict[str, Any]])  # 保存日志到文件
```

```python
def check_storage_size(self)  # 检查并清理存储
```

---

### 3. CentralClient（中心端客户端）

**位置**: [worker/communicator/central_client.py](file:///workspace/worker/communicator/central_client.py#L15-L416)

**功能**: 与中心端通信，支持故障切换和WebSocket实时通信

**关键特性**:
- 多中心端支持
- 自动健康检查
- 自动故障切换
- WebSocket实时通信
- 指数退避重连
- 本地配置缓存

**关键方法**:

```python
def register(self)  # 注册Worker到中心端
```

```python
def send_heartbeat(self)  # 发送心跳
```

```python
def _switch_server(self)  # 切换中心端服务器
```

```python
async def _connect_websocket(self)  # 连接WebSocket
```

```python
def _send_request(self, endpoint: str, data: Optional[Dict[str, Any]] = None, 
                  method: str = "POST")  # 发送请求（支持自动切换）
```

---

### 4. MetricConverter（指标转换器）

**位置**: [worker/metrics/metric_converter.py](file:///workspace/worker/metrics/metric_converter.py#L10-L122)

**功能**: 将日志转换为监控指标

**关键特性**:
- 日志到指标转换
- 指标聚合
- 按名称和标签分组

**关键方法**:

```python
def convert_logs_to_metrics(self)  # 转换日志为指标
```

```python
def aggregate_metrics(self)  # 聚合指标
```

```python
def add_metric(self, metric: Dict[str, Any])  # 添加指标
```

---

### 5. NavPageAdmin（页面管理后台）

**位置**: [master/index/admin.py](file:///workspace/master/index/admin.py#L17-L171)

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

### 6. AmisPageManager（页面管理器）

**位置**: [master/index/utils.py](file:///workspace/master/index/utils.py#L11-L178)

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

### 7. ConnectionManager（WebSocket连接管理）

**位置**: [master/worker/routes.py](file:///workspace/master/worker/routes.py#L32-L67)

**功能**: 管理Worker的WebSocket连接

**关键方法**:

```python
async def connect(self, worker_id: str, websocket: WebSocket)  # 建立连接
```

```python
async def send_personal_message(self, message: Dict[str, Any], worker_id: str)  # 发送消息
```

```python
async def broadcast(self, message: Dict[str, Any])  # 广播消息
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

---

## API接口说明

### Master API

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
│   └── core/
│       └── test_settings.py          # 配置测试
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
