# Worker端适配器模块设计方案

## 1. 项目现状分析

### 现有架构
- 项目分为 master 和 worker 两部分
- worker 端当前已包含核心模块（settings、logging、auth）、collector、communicator、metrics 等
- 使用 Python 3.12+，依赖管理采用 uv
- 已有日志系统支持优雅停机（AsyncFileHandler）
- 已有 HTTP 客户端（CentralClient）

### 现有依赖
- requests>=2.33.1 - 用于 HTTP 请求（同步）
- sqlmodel==0.0.19 和 sqlmodelx==0.0.12 - 用于 SQL 操作
- aiosqlite>=0.22.1 - 用于异步 SQLite
- 缺少 Redis 支持
- 缺少异步 HTTP 支持
- 缺少时序数据库支持

---

## 2. 设计方案

### 2.1 模块结构

在 `/workspace/worker/` 目录下创建新模块 `adapter/`，结构如下：

```
worker/
├── adapter/
│   ├── __init__.py
│   ├── base.py              # 基础适配器类和单例管理
│   ├── http_adapter.py      # 异步 HTTP 请求适配器
│   ├── sql_adapter.py       # 异步 SQL 查询适配器（关系型数据库）
│   ├── clickhouse_adapter.py  # 异步 ClickHouse 适配器
│   ├── influxdb_adapter.py    # 异步 InfluxDB 适配器
│   └── redis_adapter.py     # 异步 Redis 查询适配器
└── ...
```

### 2.2 核心设计原则

#### 单例模式实现
- 使用工厂模式+字典缓存，根据连接参数生成唯一键
- 相同连接地址和参数的适配器只实例化一次
- 线程安全的单例管理

#### 优雅停机
- 统一的异步 `close()` 接口
- 使用 `atexit` 注册清理函数
- 确保所有连接正确关闭

#### 全异步实现
- 所有适配器均采用异步实现
- HTTP 适配器使用 aiohttp
- SQL 适配器使用 sqlmodel + aiosqlite/asyncpg/aiomysql
- ClickHouse 适配器使用 clickhouse-connect 或 asynch
- InfluxDB 适配器使用 influxdb-client-python
- Redis 适配器使用 redis-py 异步 API

---

## 3. 详细设计

### 3.1 base.py - 基础模块

**功能：**
- 定义异步基础适配器抽象类
- 实现单例管理器
- 统一注册优雅停机钩子

**核心类：**
- `AsyncBaseAdapter` - 所有异步适配器的抽象基类
- `AdapterManager` - 单例管理器

### 3.2 http_adapter.py - HTTP适配器

**功能：**
- 异步实现（使用 aiohttp）
- 支持 GET、POST、PUT、DELETE 等常见 HTTP 方法
- 支持连接池
- 支持超时、重试配置
- 支持自定义 headers、cookies
- 支持流式响应

**依赖：**
- aiohttp>=3.9.0（需要新增）

### 3.3 sql_adapter.py - SQL适配器（关系型数据库）

**功能：**
- 支持多种关系型数据库后端（SQLite、PostgreSQL、MySQL 等）
- 异步连接池管理
- 异步 SQL 执行和结果处理
- 支持事务管理

**依赖：**
- sqlmodel（已有）
- aiosqlite（已有）
- asyncpg（可选，用于 PostgreSQL）
- aiomysql（可选，用于 MySQL）

### 3.4 clickhouse_adapter.py - ClickHouse 适配器

**功能：**
- 异步连接池
- 支持 ClickHouse 查询
- 支持批量插入
- 支持数据格式转换

**依赖：**
- asynch>=0.2.0（需要新增）或 clickhouse-connect>=0.7.0

### 3.5 influxdb_adapter.py - InfluxDB 适配器

**功能：**
- 异步连接池
- 支持 InfluxDB 查询（Flux 和 InfluxQL）
- 支持数据写入
- 支持批量操作

**依赖：**
- influxdb-client>=1.40.0（需要新增）

### 3.6 redis_adapter.py - Redis适配器

**功能：**
- 异步连接池
- 支持常见 Redis 命令（get、set、del、hget、hset 等）
- 支持管道操作
- 支持订阅/发布

**依赖：**
- redis>=5.0.0（需要新增）

---

## 4. 文件修改清单

### 新增文件
1. `/workspace/worker/adapter/__init__.py` - 模块入口
2. `/workspace/worker/adapter/base.py` - 基础适配器和单例管理
3. `/workspace/worker/adapter/http_adapter.py` - 异步 HTTP 适配器
4. `/workspace/worker/adapter/sql_adapter.py` - 异步 SQL 适配器
5. `/workspace/worker/adapter/clickhouse_adapter.py` - 异步 ClickHouse 适配器
6. `/workspace/worker/adapter/influxdb_adapter.py` - 异步 InfluxDB 适配器
7. `/workspace/worker/adapter/redis_adapter.py` - 异步 Redis 适配器

### 修改文件
1. `/workspace/pyproject.toml` - 添加 aiohttp、redis、asynch（或 clickhouse-connect）、influxdb-client 依赖

---

## 5. 实现步骤

### 步骤 1：基础模块实现
- 实现 AsyncBaseAdapter 抽象类
- 实现 AdapterManager 单例管理器
- 实现优雅停机钩子注册

### 步骤 2：HTTP适配器实现
- 使用 aiohttp 实现异步 HTTP 适配器类
- 实现连接池管理
- 实现常用 HTTP 方法
- 实现重试机制

### 步骤 3：SQL适配器实现
- 实现异步 SQL 适配器类
- 实现异步连接池管理
- 实现异步查询执行和结果处理

### 步骤 4：ClickHouse 适配器实现
- 实现异步 ClickHouse 适配器类
- 实现异步连接池管理
- 实现查询和写入操作

### 步骤 5：InfluxDB 适配器实现
- 实现异步 InfluxDB 适配器类
- 实现异步连接池管理
- 实现查询和写入操作

### 步骤 6：Redis适配器实现
- 实现异步 Redis 适配器类
- 实现异步连接池管理
- 实现常用 Redis 命令

### 步骤 7：测试和集成
- 更新 pyproject.toml 添加依赖
- 编写基本测试用例
- 验证单例模式和优雅停机

---

## 6. 风险和注意事项

### 风险点
1. **单例模式线程安全** - 需要确保多线程环境下单例创建的线程安全
2. **连接泄漏** - 确保所有连接在关闭时正确清理
3. **依赖版本兼容性** - 新增多个依赖需要与现有依赖兼容
4. **异步上下文管理** - 需要正确处理 asyncio 事件循环
5. **多类型数据库适配** - 需要统一不同数据库的 API 差异

### 解决方案
1. 使用 threading.Lock 确保单例创建线程安全
2. 完善 async close() 方法，使用 try-finally 确保资源释放
3. 选择稳定版本并测试兼容性
4. 统一管理事件循环，提供便捷的获取方式
5. 提供统一的查询接口，内部处理不同数据库的差异

---

## 7. 技术选型

| 功能 | 技术选型 | 说明 |
|------|---------|------|
| HTTP 请求 | aiohttp | 异步 HTTP 客户端，高性能 |
| 关系型数据库 | sqlmodel + aiosqlite/asyncpg | 异步 SQL 操作 |
| ClickHouse | asynch | 异步 ClickHouse 客户端 |
| InfluxDB | influxdb-client | 官方异步客户端 |
| Redis | redis-py 5.x | 官方推荐，支持异步 API |
| 单例模式 | 工厂模式+字典缓存 | 灵活且易于扩展 |
| 优雅停机 | atexit + asyncio | Python 标准库，支持异步清理 |
