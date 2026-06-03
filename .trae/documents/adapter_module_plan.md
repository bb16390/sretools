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
│   ├── sql_adapter.py       # SQL 查询适配器
│   └── redis_adapter.py     # Redis 查询适配器
└── ...
```

### 2.2 核心设计原则

#### 单例模式实现
- 使用工厂模式+字典缓存，根据连接参数生成唯一键
- 相同连接地址和参数的适配器只实例化一次
- 线程安全的单例管理

#### 优雅停机
- 统一的 `close()` 接口（支持同步和异步）
- 使用 `atexit` 注册清理函数
- 确保所有连接正确关闭

#### 异步优先
- HTTP 适配器使用异步实现（aiohttp）
- SQL 适配器同时支持同步和异步
- Redis 适配器同时支持同步和异步

---

## 3. 详细设计

### 3.1 base.py - 基础模块

**功能：**
- 定义基础适配器抽象类（支持同步和异步）
- 实现单例管理器
- 统一注册优雅停机钩子

**核心类：**
- `BaseAdapter` - 所有适配器的抽象基类
- `AsyncBaseAdapter` - 异步适配器的抽象基类
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

### 3.3 sql_adapter.py - SQL适配器

**功能：**
- 支持多种数据库后端（SQLite、PostgreSQL、MySQL 等）
- 连接池管理
- 支持同步和异步操作
- SQL 执行和结果处理
- 支持事务管理

**依赖：**
- sqlmodel（已有）
- aiosqlite（已有）
- asyncpg（可选，用于 PostgreSQL）
- aiomysql（可选，用于 MySQL）

### 3.4 redis_adapter.py - Redis适配器

**功能：**
- 支持连接池
- 支持常见 Redis 命令（get、set、del、hget、hset 等）
- 支持管道操作
- 支持订阅/发布
- 同时支持同步和异步

**依赖：**
- redis>=5.0.0（需要新增）

---

## 4. 文件修改清单

### 新增文件
1. `/workspace/worker/adapter/__init__.py` - 模块入口
2. `/workspace/worker/adapter/base.py` - 基础适配器和单例管理
3. `/workspace/worker/adapter/http_adapter.py` - 异步 HTTP 适配器
4. `/workspace/worker/adapter/sql_adapter.py` - SQL 适配器
5. `/workspace/worker/adapter/redis_adapter.py` - Redis 适配器

### 修改文件
1. `/workspace/pyproject.toml` - 添加 aiohttp 和 redis 依赖

---

## 5. 实现步骤

### 步骤 1：基础模块实现
- 实现 BaseAdapter 和 AsyncBaseAdapter 抽象类
- 实现 AdapterManager 单例管理器
- 实现优雅停机钩子注册

### 步骤 2：HTTP适配器实现
- 使用 aiohttp 实现异步 HTTP 适配器类
- 实现连接池管理
- 实现常用 HTTP 方法
- 实现重试机制

### 步骤 3：SQL适配器实现
- 实现 SQL 适配器类
- 实现连接池管理
- 实现查询执行和结果处理
- 支持同步和异步

### 步骤 4：Redis适配器实现
- 实现 Redis 适配器类
- 实现连接池管理
- 实现常用 Redis 命令
- 支持同步和异步

### 步骤 5：测试和集成
- 更新 pyproject.toml 添加依赖
- 编写基本测试用例
- 验证单例模式和优雅停机

---

## 6. 风险和注意事项

### 风险点
1. **单例模式线程安全** - 需要确保多线程环境下单例创建的线程安全
2. **连接泄漏** - 确保所有连接在关闭时正确清理
3. **依赖版本兼容性** - 新增 aiohttp 和 redis 依赖需要与现有依赖兼容
4. **异步适配** - 需要正确处理同步和异步代码的混合使用

### 解决方案
1. 使用 threading.Lock 确保单例创建线程安全
2. 完善 close() 方法，使用 try-finally 确保资源释放
3. 选择稳定版本（aiohttp>=3.9.0, redis>=5.0.0）并测试兼容性
4. 使用 asyncio.run() 或提供同步包装器

---

## 7. 技术选型

| 功能 | 技术选型 | 说明 |
|------|---------|------|
| HTTP 请求 | aiohttp | 异步 HTTP 客户端，高性能 |
| SQL 操作 | sqlmodel + aiosqlite | 项目已有依赖，支持同步和异步 |
| Redis | redis-py 5.x | 官方推荐，支持同步和异步 |
| 单例模式 | 工厂模式+字典缓存 | 灵活且易于扩展 |
| 优雅停机 | atexit + asyncio | Python 标准库，支持异步清理 |
